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

markets as (

    select h.household_id, mode(f.market_id) as market_id
    from {{ ref('int_household') }} h
    join {{ ref('fct_registration') }} f on f.participant_id = h.participant_id
    where f.is_valid_registration and f.market_id is not null
    group by 1

),

agg as (

    select
        household_id,
        bool_or(is_adult_household)                                         as is_adult_household,
        count(*)                                                            as participants,
        count(*) filter (where is_minor_current)                            as children,
        min(first_season)                                                   as first_year,
        max(last_season)                                                    as last_year,
        mode(home_country_code)                                             as country_code,
        mode(home_region_code)                                              as region_code
    from members group by 1

)

select a.*, m.market_id, a.last_year - a.first_year + 1 as years_span, c.emails, c.phones
from agg a left join contacts c using (household_id) left join markets m using (household_id)
