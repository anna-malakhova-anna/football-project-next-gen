{{ config(tags=['phase5']) }}
-- GROUND TRUTH (evaluation only). Does each component of mart_uncertainty_decomposition land on the truth it is meant to bracket? Per year:
--   IDENTITY  the true number of people with a valid registration in the data  vs  the Phase 3 low / point / high
--   DQ        the lenient count (Phase 3) and the strict count vs the same truth: strict must not exceed it, lenient is the reported point
--   COVERAGE  the true number of participants of dark organizations who appear nowhere in the data that year (unreported_participation_truth, modelled sources, not registered elsewhere that
--             year)  vs  the coverage estimate and its 25th to 75th percentile interval. The question the spec asks: does the coverage estimate land near the true number of non-reported participants?
-- The answer key is never an input to the decomposition.
with truth_in_data as (

    select r.participation_year, count(distinct t.true_person_id) as true_people
    from {{ ref('fct_registration') }} r
    join {{ ref('eval_record_truth') }} t on t.match_record_id = r.registration_key
    where r.is_valid_registration
    group by 1

),

in_data_people as (

    select distinct r.participation_year, t.true_person_id
    from {{ ref('fct_registration') }} r join {{ ref('eval_record_truth') }} t on t.match_record_id = r.registration_key where r.is_valid_registration

),

unreported as (

    select u.season_year as participation_year, count(distinct u.true_person_id) as true_missing
    from {{ source('ground_truth', 'unreported_participation_truth') }} u
    where u.source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED')
      and not exists (select 1 from in_data_people p where p.participation_year = u.season_year and p.true_person_id = u.true_person_id)
    group by 1

),

c as (

    select participation_year, component, point, low, high, interval_low, interval_high from {{ ref('mart_uncertainty_decomposition') }}

)

select
    t.participation_year,
    t.true_people                                                           as true_participants_in_data,
    i.low as identity_low, i.point as identity_point, i.high as identity_high,
    i.interval_low <= t.true_people and t.true_people <= i.interval_high    as identity_interval_contains_truth,
    round(abs(i.point - t.true_people) / t.true_people, 4)                  as identity_point_error,
    d.low as dq_strict, d.high as dq_lenient,
    d.low <= t.true_people                                                  as strict_not_above_truth,
    coalesce(u.true_missing, 0)                                             as true_participants_missing_from_data,
    cv.low as coverage_low, cv.point as coverage_point, cv.high as coverage_high,
    cv.low <= coalesce(u.true_missing, 0) and coalesce(u.true_missing, 0) <= cv.high as coverage_interval_contains_truth,
    round((cv.point - coalesce(u.true_missing, 0)) / nullif(u.true_missing, 0), 4)    as coverage_point_error,
    t.true_people + coalesce(u.true_missing, 0)                             as true_total_participants,
    round(i.point + cv.point)                                               as estimated_total_participants
from truth_in_data t
join c i on i.participation_year = t.participation_year and i.component = 'IDENTITY'
join c d on d.participation_year = t.participation_year and d.component = 'DQ_EXCLUSIONS'
join c cv on cv.participation_year = t.participation_year and cv.component = 'COVERAGE'
left join unreported u on u.participation_year = t.participation_year
