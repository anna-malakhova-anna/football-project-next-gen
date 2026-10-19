-- depends_on: {{ ref('privacy_params') }}
-- depends_on: {{ ref('dq_grade_bands') }}
-- depends_on: {{ ref('dq_severity_weights') }}
-- depends_on: {{ ref('observation_window') }}
-- The source scorecard: source x season x purpose x dimension, by the same method as dq_scorecard_org (severity-weighted dimension score, purpose score = the minimum, Wilson interval below
-- dq_n_min). Record rules are pooled over the source's organizations (sum of passes over sum evaluated, so a big organization counts for what it is), the organization-reported rule becomes
-- the share of known organizations that sent a file, and a contract's quality rules (measured once over all seasons by the contract validation) count in every season of the source.
-- includes_contract_rules says so on every row, so nobody mistakes a source-level contract measure for a per-season one.
with rec as (

    select source_system, season_year, purpose, dimension, rule_id, severity, sum(n_pass) as n_pass, sum(n_evaluated) as n_evaluated,
           sum(n_pass)::double / nullif(sum(n_evaluated), 0) as pass_rate
    from {{ ref('dq_rule_results') }}
    where origin <> 'CONTRACT' and purpose is not null and season_year between {{ first_observed_year() }} and (select last_observed_year from {{ ref('observation_window') }})
    group by all

),

seasons as (select distinct source_system, season_year from rec),

ctr as (

    -- a contract rule is measured once by the contract validation: its pass rate is the observed one, not a count of passes
    select s.source_system, s.season_year, r.purpose, r.dimension, r.rule_id, r.severity, r.n_pass, r.n_evaluated, r.observed_value as pass_rate
    from {{ ref('dq_rule_results') }} r join seasons s using (source_system)
    where r.origin = 'CONTRACT' and r.purpose is not null

),

scored as (

    select u.*, w.weight, t.threshold
    from (select * from rec union all select * from ctr) u
    join {{ ref('dq_severity_weights') }} w using (severity)
    join (select distinct rule_id, purpose, threshold from {{ ref('dq_rule_results') }}) t using (rule_id, purpose)
    where w.weight > 0 and u.n_evaluated > 0

),

dim as (

    select source_system, season_year, purpose, dimension,
           100 * sum(weight * pass_rate) / sum(weight) as score, count(*) as rules_scored,
           bool_or(rule_id like 'DQ-CTR-%') as includes_contract_rules
    from scored group by all

),

failing as (

    select source_system, season_year, purpose, dimension,
           list(rule_id order by weight * (1 - pass_rate) * n_evaluated desc, rule_id) filter (where pass_rate < threshold) as failing_rules
    from scored group by all

),

purpose_score as (

    select source_system, season_year, purpose, 'PURPOSE_SCORE' as dimension, min(score) as score, sum(rules_scored) as rules_scored,
           arg_min(dimension, score) as limiting_dimension, bool_or(includes_contract_rules) as includes_contract_rules
    from dim group by 1, 2, 3

),

combined as (

    select d.source_system, d.season_year, d.purpose, d.dimension, d.score, d.rules_scored, cast(null as varchar) as limiting_dimension, d.includes_contract_rules, f.failing_rules
    from dim d left join failing f using (source_system, season_year, purpose, dimension)
    union all
    select p.source_system, p.season_year, p.purpose, p.dimension, p.score, p.rules_scored, p.limiting_dimension, p.includes_contract_rules, f.failing_rules
    from purpose_score p left join failing f on f.source_system = p.source_system and f.season_year = p.season_year and f.purpose = p.purpose and f.dimension = p.limiting_dimension

),

size as (

    select source_system, season_year, count(*) as n_records from {{ ref('dq_record_resolved') }} where season_year is not null group by 1, 2

),

orgs as (

    select source_system, season_year, count(*) as known_orgs, count(*) filter (where reported) as reporting_orgs
    from {{ ref('dq_org_season_base') }} group by 1, 2

),

sized as (

    select c.*, s.n_records, o.known_orgs, o.reporting_orgs,
           s.n_records < {{ privacy_param('dq_n_min') }} as interval_applied,
           {{ dq_wilson('c.score / 100.0', 's.n_records', 'low') }} * 100 as wilson_low,
           {{ dq_wilson('c.score / 100.0', 's.n_records', 'high') }} * 100 as wilson_high
    from combined c
    join size s using (source_system, season_year)
    left join orgs o using (source_system, season_year)

)

select
    source_system, season_year, purpose, dimension,
    round(score, 2)                                                         as score,
    round(case when interval_applied then wilson_low end, 2)                as score_interval_low,
    round(case when interval_applied then wilson_high end, 2)               as score_interval_high,
    interval_applied,
    {{ dq_grade('round(case when interval_applied then coalesce(wilson_low, score) else score end, 2)') }} as grade,
    n_records                                                               as record_count,
    known_orgs, reporting_orgs,
    rules_scored,
    includes_contract_rules,
    limiting_dimension,
    list_slice(coalesce(failing_rules, []), 1, 3)                           as top_failing_rules
from sized
