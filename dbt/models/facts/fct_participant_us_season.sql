-- US seasonal view (rule C4): one row per participant x participation year x term (SPRING or FALL) with at least one
-- valid US registration. Never blended with annual sources. New / returning / reactivated are defined against the SAME
-- TERM in the prior year (spring vs spring, fall vs fall); the first year of data is CENSORED.
{% set youth_max = privacy_param('youth_max_age') %}
with v as (

    select * from {{ ref('fct_registration') }} where is_valid_registration and us_season_term is not null

),

ranked as (

    select
        *,
        row_number() over (partition by participant_id, participation_year, us_season_term
                           order by registered_at desc nulls last, registration_key)                   as recency_rank,
        count(*) over (partition by participant_id, participation_year, us_season_term, canonical_division) as division_regs
    from v

),

agg as (

    select
        participant_id,
        participation_year,
        us_season_term                                                      as season_term,
        count(*)                                                            as valid_registration_count,
        count(distinct organization_id)                                     as org_count,
        list_sort(list_distinct(list(canonical_division)))                  as all_divisions,
        (array_agg(canonical_division order by division_regs desc, recency_rank))[1] as primary_division
    from ranked
    group by participant_id, participation_year, us_season_term

),

first_term_year as (

    select participant_id, season_term, min(participation_year) as first_year from agg group by 1, 2

),

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
            when a.participation_year = {{ first_observed_year() }} then 'CENSORED'
            when a.participation_year = f.first_year then 'NEW'
            when exists (select 1 from agg p where p.participant_id = a.participant_id and p.season_term = a.season_term
                         and p.participation_year = a.participation_year - 1) then 'RETURNING'
            else 'REACTIVATED'
        end                                                                 as status
    from agg a
    join {{ ref('dim_participant') }} d using (participant_id)
    join first_term_year f on f.participant_id = a.participant_id and f.season_term = a.season_term

)

select
    participant_id || '|' || participation_year || '|' || season_term       as participant_season_key,
    participant_id,
    participation_year,
    season_term,
    valid_registration_count,
    org_count,
    org_count > 1                                                           as is_multi_org,
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
