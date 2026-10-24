-- RESTRICTED (schema `linkage`). One row per observed household: its contacts (the keys the fan-account linkage may use) and what the program
-- knows about it (country, region, years active, children). No names, no dates of birth.
with members as (

    select h.household_id, h.participant_id, h.is_adult_household, p.is_minor_current, p.first_season, p.last_season, p.home_country_code, p.home_region_code
    from {{ ref('int_household') }} h
    join {{ ref('dim_participant') }} p using (participant_id)

),

contacts as (

    select h.household_id,
           list_sort(list_distinct(list(u.contact_email) filter (where u.contact_email is not null))) as emails,
           list_sort(list_distinct(list(u.contact_phone) filter (where u.contact_phone is not null))) as phones
    from {{ ref('int_household') }} h
    join {{ ref('bridge_registration_participant') }} b on b.participant_id = h.participant_id
    join {{ ref('int_registrations_unioned') }} u on u.registration_key = b.registration_key
    group by 1

),

-- Ties are broken explicitly: DuckDB's mode() picks an arbitrary value on a tie, so a household with one child in each of two
-- countries or markets got a different country on different machines (CA 2,177 vs 2,180 households). Rule: most members or
-- registrations; then the most recent season; then the code, alphabetically. Same pattern as the ADR-023 tie-breaks.
markets as (

    select h.household_id, f.market_id
    from {{ ref('int_household') }} h
    join {{ ref('fct_registration') }} f on f.participant_id = h.participant_id
    where f.is_valid_registration and f.market_id is not null
    group by 1, 2
    qualify row_number() over (partition by h.household_id order by count(*) desc, max(f.participation_year) desc, f.market_id) = 1

),

home_country as (

    select household_id, home_country_code as country_code
    from members where home_country_code is not null
    group by 1, 2
    qualify row_number() over (partition by household_id order by count(*) desc, max(last_season) desc, home_country_code) = 1

),

home_region as (

    select household_id, home_region_code as region_code
    from members where home_region_code is not null
    group by 1, 2
    qualify row_number() over (partition by household_id order by count(*) desc, max(last_season) desc, home_region_code) = 1

),

agg as (

    select
        household_id,
        bool_or(is_adult_household)                                         as is_adult_household,
        count(*)                                                            as participants,
        count(*) filter (where is_minor_current)                            as children,
        min(first_season)                                                   as first_year,
        max(last_season)                                                    as last_year
    from members group by 1

)

select a.household_id, a.is_adult_household, a.participants, a.children, a.first_year, a.last_year, hc.country_code, hr.region_code,
       m.market_id, a.last_year - a.first_year + 1 as years_span, c.emails, c.phones
from agg a
left join home_country hc using (household_id)
left join home_region hr using (household_id)
left join contacts c using (household_id)
left join markets m using (household_id)
