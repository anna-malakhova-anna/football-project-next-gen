-- depends_on: {{ ref('privacy_params') }}
-- depends_on: {{ ref('dq_grade_bands') }}
-- depends_on: {{ ref('dq_severity_weights') }}
-- depends_on: {{ ref('observation_window') }}
-- The country scorecard (Phase 7, ADR-025 section 1): country x season x purpose x dimension, by EXACTLY the method of dq_scorecard_source, grouped by the
-- country of each organization instead of by source. US_LEAGUE organizations are the US, CA_CLUB organizations Canada, INTL_FED organizations their
-- sheet's country (region_code). Record rules are pooled over the country's organizations; the organization-reported rule becomes the share of the
-- country's known organizations that sent a file; a contract rule (measured once per source) counts in every country and season of its source.
-- A test (dq_scorecard_country_matches_source) checks that a one-country source scores the same here as in dq_scorecard_source.
with org_country as (

    select distinct org_id, source_system,
           case source_system when 'US_LEAGUE' then 'US' when 'CA_CLUB' then 'CA' when 'INTL_FED' then region_code end as country_code
    from {{ ref('dq_org_season_base') }}
    where source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED')

),

rec as (

    select o.country_code, r.source_system, r.season_year, r.purpose, r.dimension, r.rule_id, r.severity, sum(r.n_pass) as n_pass, sum(r.n_evaluated) as n_evaluated,
           sum(r.n_pass)::double / nullif(sum(r.n_evaluated), 0) as pass_rate
    from {{ ref('dq_rule_results') }} r join org_country o using (org_id, source_system)
    where r.origin <> 'CONTRACT' and r.purpose is not null and r.season_year between {{ first_observed_year() }} and (select last_observed_year from {{ ref('observation_window') }})
    group by all

),

seasons as (select distinct country_code, source_system, season_year from rec),

ctr as (

    select s.country_code, s.source_system, s.season_year, r.purpose, r.dimension, r.rule_id, r.severity, r.n_pass, r.n_evaluated, r.observed_value as pass_rate
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

    select country_code, source_system, season_year, purpose, dimension,
           (100 * sum(weight::decimal(18, 6) * pass_rate::decimal(18, 9)) / sum(weight::decimal(18, 6)))::double as score, count(*) as rules_scored,
           bool_or(rule_id like 'DQ-CTR-%') as includes_contract_rules
    from scored group by all

),

failing as (

    select country_code, source_system, season_year, purpose, dimension,
           list(rule_id order by round(weight * (1 - pass_rate) * n_evaluated, 6) desc, round(n_evaluated * (1 - pass_rate), 6) desc, rule_id) filter (where pass_rate < threshold) as failing_rules
    from scored group by all

),

purpose_score as (

    select country_code, source_system, season_year, purpose, 'PURPOSE_SCORE' as dimension, min(score) as score, sum(rules_scored) as rules_scored,
           arg_min(dim.dimension, (round(dim.score, 6), pri.tie_priority)) as limiting_dimension, bool_or(includes_contract_rules) as includes_contract_rules
    from dim join {{ ref('dq_dimensions') }} pri on pri.dimension = dim.dimension group by 1, 2, 3, 4

),

combined as (

    select d.country_code, d.source_system, d.season_year, d.purpose, d.dimension, d.score, d.rules_scored, cast(null as varchar) as limiting_dimension, d.includes_contract_rules, f.failing_rules
    from dim d left join failing f using (country_code, source_system, season_year, purpose, dimension)
    union all
    select p.country_code, p.source_system, p.season_year, p.purpose, p.dimension, p.score, p.rules_scored, p.limiting_dimension, p.includes_contract_rules, f.failing_rules
    from purpose_score p left join failing f on f.country_code = p.country_code and f.source_system = p.source_system and f.season_year = p.season_year
                                               and f.purpose = p.purpose and f.dimension = p.limiting_dimension

),

size as (

    select o.country_code, r.source_system, r.season_year, count(*) as n_records
    from {{ ref('dq_record_resolved') }} r join org_country o using (org_id, source_system)
    where r.season_year is not null group by 1, 2, 3

),

orgs as (

    select o.country_code, b.source_system, b.season_year, count(*) as known_orgs, count(*) filter (where b.reported) as reporting_orgs
    from {{ ref('dq_org_season_base') }} b join org_country o using (org_id, source_system) group by 1, 2, 3

),

sized as (

    select c.*, s.n_records, o.known_orgs, o.reporting_orgs,
           s.n_records < {{ privacy_param('dq_n_min') }} as interval_applied,
           {{ dq_wilson('c.score / 100.0', 's.n_records', 'low') }} * 100 as wilson_low,
           {{ dq_wilson('c.score / 100.0', 's.n_records', 'high') }} * 100 as wilson_high
    from combined c
    join size s using (country_code, source_system, season_year)
    left join orgs o using (country_code, source_system, season_year)

)

select
    country_code, source_system, season_year, purpose, dimension,
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
