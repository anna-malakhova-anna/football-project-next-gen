-- depends_on: {{ ref('privacy_params') }}
-- depends_on: {{ ref('dq_grade_bands') }}
-- depends_on: {{ ref('dq_severity_weights') }}
-- The organization scorecard: organization x season x purpose x dimension (ADR-014). Method:
--   dimension score  the severity-weighted mean pass rate (0 to 100) of the rules in the dimension that list the purpose, over the records (or organization-seasons) they could evaluate
--   PURPOSE_SCORE    the MINIMUM of the purpose's dimension scores. A chain is only as strong as its weakest link: an average would let a perfect uniqueness score hide a purpose that fails
--                    on completeness, and "good on average" is exactly what a family or a club cannot use. limiting_dimension names the weak link.
--   small samples    an organization-season with fewer scored records than privacy_params.dq_n_min carries a Wilson interval and is graded on its LOWER BOUND, so a 5-record league with one
--                    error is not graded like a 500-record league. A dark organization (no file) has no records: its timeliness score is 0 and so is its purpose score.
-- Grades come from the dq_grade_bands seed. Failing rules are listed worst first (shortfall x severity weight x records failing).
with scored as (

    select r.source_system, r.org_id, r.season_year, r.purpose, r.dimension, r.rule_id, r.severity, r.observed_value as pass_rate,
           r.n_evaluated, r.n_pass, r.pass, w.weight
    from {{ ref('dq_rule_results') }} r join {{ ref('dq_severity_weights') }} w using (severity)
    where r.org_id is not null and r.purpose is not null and w.weight > 0 and r.n_evaluated > 0

),

dim as (

    select source_system, org_id, season_year, purpose, dimension,
           (100 * sum(weight::decimal(18, 6) * pass_rate::decimal(18, 9)) / sum(weight::decimal(18, 6)))::double as score, count(*) as rules_scored
    from scored group by all

),

failing as (

    select source_system, org_id, season_year, purpose, dimension,
           list(rule_id order by round(weight * (1 - pass_rate) * n_evaluated, 6) desc, round(n_evaluated * (1 - pass_rate), 6) desc, rule_id) filter (where pass is false) as failing_rules
    from scored group by all

),

purpose_score as (

    select source_system, org_id, season_year, purpose, 'PURPOSE_SCORE' as dimension, min(score) as score, sum(rules_scored) as rules_scored,
           arg_min(dim.dimension, (round(dim.score, 6), pri.tie_priority)) as limiting_dimension
    from dim join {{ ref('dq_dimensions') }} pri on pri.dimension = dim.dimension group by 1, 2, 3, 4

),

combined as (

    select d.source_system, d.org_id, d.season_year, d.purpose, d.dimension, d.score, d.rules_scored, cast(null as varchar) as limiting_dimension, f.failing_rules
    from dim d left join failing f using (source_system, org_id, season_year, purpose, dimension)
    union all
    select p.source_system, p.org_id, p.season_year, p.purpose, p.dimension, p.score, p.rules_scored, p.limiting_dimension, f.failing_rules
    from purpose_score p left join failing f on f.source_system = p.source_system and f.org_id = p.org_id and f.season_year = p.season_year
                                              and f.purpose = p.purpose and f.dimension = p.limiting_dimension

),

sized as (

    select c.*, o.org_name, o.region_code, o.channel, o.reported, o.n_records,
           o.n_records < {{ privacy_param('dq_n_min') }} as interval_applied,
           {{ dq_wilson('c.score / 100.0', 'o.n_records', 'low') }} * 100 as wilson_low,
           {{ dq_wilson('c.score / 100.0', 'o.n_records', 'high') }} * 100 as wilson_high
    from combined c join {{ ref('dq_org_season_base') }} o using (source_system, org_id, season_year)

)

select
    source_system, org_id, org_name, region_code, channel, season_year, purpose, dimension,
    round(score, 2)                                                         as score,
    round(case when interval_applied then wilson_low end, 2)                as score_interval_low,
    round(case when interval_applied then wilson_high end, 2)               as score_interval_high,
    interval_applied,
    {{ dq_grade('round(case when interval_applied then coalesce(wilson_low, score) else score end, 2)') }} as grade,
    n_records                                                               as record_count,
    reported,
    rules_scored,
    limiting_dimension,
    list_slice(coalesce(failing_rules, []), 1, 3)                           as top_failing_rules
from sized
