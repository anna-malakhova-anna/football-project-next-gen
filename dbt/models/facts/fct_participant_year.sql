-- One row per participant x participation year with at least one valid registration. Implements the counting rules:
--   C5 org count / multi-org, C6 countries and attributed country, C7 age, C8 primary division, C9 sex (U stays U),
--   C10 youth, C11-C13 status, C14 open integrity issue flag.
-- "Most recent" = term order (SPRING < ANNUAL < FALL), then registration time, then key; see macro term_order.
{% set youth_max = privacy_param('youth_max_age') %}
with v as (

    select * from {{ ref('fct_registration') }} where is_valid_registration

),

ranked as (

    select
        *,
        row_number() over (partition by participant_id, participation_year
                           order by term_order desc, registered_at desc nulls last, registration_key)  as recency_rank,
        count(*) over (partition by participant_id, participation_year, canonical_division)            as division_regs
    from v

),

agg as (

    select
        participant_id,
        participation_year,
        count(*)                                                            as valid_registration_count,
        count(distinct organization_id)                                     as org_count,
        list_sort(list_distinct(list(country_code)))                        as countries_played,
        list_sort(list_distinct(list(canonical_division)))                  as all_divisions,
        max(country_code) filter (where recency_rank = 1)                   as attributed_country_code,
        -- primary division: the most registrations in the year; ties go to the most recent registration
        (array_agg(canonical_division order by division_regs desc, recency_rank))[1] as primary_division
    from ranked
    group by participant_id, participation_year

),

first_year as (

    select participant_id, min(participation_year) as first_valid_year from v group by participant_id

),

years as (select distinct participant_id, participation_year from v),

with_status as (

    select
        a.*,
        d.sex,
        d.resolution_confidence,
        d.has_open_integrity_issue,
        case
            when d.dob is not null then {{ age_at_cutoff('d.dob', 'a.participation_year') }}
            when d.birth_year is not null then {{ age_at_cutoff_from_birth_year('d.birth_year', 'a.participation_year') }}
        end                                                                 as age_at_cutoff,
        case
            when a.participation_year = (select min(participation_year) from years) then 'CENSORED'
            when a.participation_year = f.first_valid_year then 'NEW'
            when exists (select 1 from years y where y.participant_id = a.participant_id
                         and y.participation_year = a.participation_year - 1) then 'RETURNING'
            else 'REACTIVATED'
        end                                                                 as status
    from agg a
    join {{ ref('dim_participant') }} d using (participant_id)
    join first_year f using (participant_id)

)

select
    participant_id || '|' || participation_year                             as participant_year_key,
    participant_id,
    participation_year,
    valid_registration_count,
    org_count,
    org_count > 1                                                           as is_multi_org,
    countries_played,
    len(countries_played) > 1                                               as is_multi_country,
    attributed_country_code,
    age_at_cutoff,
    {{ age_band('age_at_cutoff') }}                                         as age_band,
    age_at_cutoff <= {{ youth_max }}                                        as is_youth,
    primary_division,
    all_divisions,
    sex,
    status,
    has_open_integrity_issue,
    resolution_confidence
from with_status
