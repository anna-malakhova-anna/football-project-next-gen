-- depends_on: {{ ref('privacy_params') }}
-- Quality over time with statistical process control: is a change a real shift or noise? One row per entity (a source, or an organization) x season x purpose, on the PURPOSE_SCORE.
--   prior_mean   the record-weighted mean of the entity's earlier seasons          (NULL in the first season: nothing to compare with)
--   P-chart      lcl / ucl = prior mean +/- 3 sqrt(p (1 - p) / n), p the prior mean as a proportion and n this season's record count (the organization's mean record count when it sent no
--                file, so a dark season is judged on what its normal size would be). The right limits for a proportion: a small organization's limits are wide, a big source's narrow.
--   mean +/- 3 sd  (lcl_sd / ucl_sd) the classical limits from the prior seasons' spread, given only from three prior seasons on; shown beside the P-chart, never instead.
--   OUT_OF_CONTROL the season's score is outside the P-chart limits: a shift worth a question (direction says which way). Decided on the limits AS PUBLISHED (rounded to the score's two
--                decimals), so the flag always agrees with the numbers shown: compared with the unrounded limit, a score equal to the shown limit could be flagged, or a
--                weighted mean of identical scores that lands a hair off in floating point could put a score just past a zero-width limit.
-- With five seasons a trend is short; the flag says "unusual against its own history", not "caused by anything".
with series as (

    select 'SOURCE' as entity_type, source_system as entity_id, source_system, cast(null as varchar) as org_name, season_year, purpose, score, record_count, grade
    from {{ ref('dq_scorecard_source') }} where dimension = 'PURPOSE_SCORE'
    union all
    select 'ORG', org_id, source_system, org_name, season_year, purpose, score, record_count, grade
    from {{ ref('dq_scorecard_org') }} where dimension = 'PURPOSE_SCORE'

),

prior as (

    select
        *,
        sum(score * record_count) over w / nullif(sum(record_count) over w, 0)      as prior_mean,
        stddev_samp(score) over w                                                   as prior_sd,
        count(*) over w                                                             as prior_seasons,
        avg(nullif(record_count, 0)) over w                                         as prior_avg_n
    from series
    window w as (partition by entity_type, entity_id, purpose order by season_year rows between unbounded preceding and 1 preceding)

),

limits as (

    select
        *,
        coalesce(nullif(record_count, 0), prior_avg_n) as n_for_limits,
        prior_mean / 100.0 as p
    from prior

),

published as (

    select
        *,
        round(greatest(100 * (p - 3 * sqrt(p * (1 - p) / n_for_limits)), 0), 2) as lcl,
        round(least(100 * (p + 3 * sqrt(p * (1 - p) / n_for_limits)), 100), 2)  as ucl
    from limits

)

select
    entity_type, entity_id, source_system, org_name, season_year, purpose,
    score, grade, record_count,
    round(prior_mean, 2)                                                    as prior_mean,
    prior_seasons,
    'P_CHART'                                                               as limit_method,
    lcl,
    ucl,
    round(case when prior_seasons >= 3 then greatest(prior_mean - 3 * prior_sd, 0) end, 2) as lcl_sd,
    round(case when prior_seasons >= 3 then least(prior_mean + 3 * prior_sd, 100) end, 2)  as ucl_sd,
    prior_seasons >= 1 and (score < lcl or score > ucl)                     as out_of_control,
    case when prior_seasons < 1 then null
         when score < lcl then 'BELOW'
         when score > ucl then 'ABOVE' end                                 as direction
from published
