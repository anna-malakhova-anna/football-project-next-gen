-- depends_on: {{ ref('privacy_params') }}
-- depends_on: {{ ref('dq_grade_bands') }}
-- depends_on: {{ ref('dq_severity_weights') }}
-- The club-market scorecard: club market x season x purpose x dimension, by the same method as the organization and source scorecards (severity-weighted dimension scores; PURPOSE_SCORE = the minimum;
-- Wilson interval and lower-bound grading below dq_n_min). Records are counted with their allocation weights, so a shared market gets its share of each record; record_count is therefore an
-- allocated count. Contract rules are source-level and not part of a market's score. OUTSIDE_US is the Canadian and international participants (the lens is domestic by design).
-- This table is for the data steward; the club-facing aggregate (with suppression) is share_club.
with scored as (

    select r.club_market_id, r.season_year, r.purpose, r.dimension, r.rule_id, r.severity, r.observed_value as pass_rate, r.n_evaluated, r.pass, w.weight
    from {{ ref('dq_market_rule_results') }} r join {{ ref('dq_severity_weights') }} w using (severity)
    where r.purpose is not null and w.weight > 0 and r.n_evaluated > 0

),

dim as (select club_market_id, season_year, purpose, dimension, (100 * sum(weight::decimal(18, 6) * pass_rate::decimal(18, 9)) / sum(weight::decimal(18, 6)))::double as score, count(*) as rules_scored from scored group by all),

failing as (

    select club_market_id, season_year, purpose, dimension,
           list(rule_id order by round(weight * (1 - pass_rate) * n_evaluated, 6) desc, round(n_evaluated * (1 - pass_rate), 6) desc, rule_id) filter (where pass is false) as failing_rules
    from scored group by all

),

purpose_score as (

    select club_market_id, season_year, purpose, 'PURPOSE_SCORE' as dimension, min(score) as score, sum(rules_scored) as rules_scored, arg_min(dim.dimension, (round(dim.score, 6), pri.tie_priority)) as limiting_dimension
    from dim join {{ ref('dq_dimensions') }} pri on pri.dimension = dim.dimension group by 1, 2, 3

),

combined as (

    select d.club_market_id, d.season_year, d.purpose, d.dimension, d.score, d.rules_scored, cast(null as varchar) as limiting_dimension, f.failing_rules
    from dim d left join failing f using (club_market_id, season_year, purpose, dimension)
    union all
    select p.club_market_id, p.season_year, p.purpose, p.dimension, p.score, p.rules_scored, p.limiting_dimension, f.failing_rules
    from purpose_score p left join failing f on f.club_market_id = p.club_market_id and f.season_year = p.season_year and f.purpose = p.purpose and f.dimension = p.limiting_dimension

),

size as (

    select m.club_market_id, b.season_year, sum(m.weight) as n_records
    from {{ ref('dq_record_resolved') }} b join {{ ref('int_participant_year_market') }} m on m.participant_id = b.person_id and m.participation_year = b.season_year
    where b.source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') group by 1, 2

),

sized as (

    select c.*, s.n_records, s.n_records < {{ privacy_param('dq_n_min') }} as interval_applied,
           {{ dq_wilson('c.score / 100.0', 's.n_records', 'low') }} * 100 as wilson_low, {{ dq_wilson('c.score / 100.0', 's.n_records', 'high') }} * 100 as wilson_high
    from combined c join size s using (club_market_id, season_year)

)

select
    club_market_id, coalesce(any_value(m.market_name) over (partition by club_market_id), case club_market_id when 'OUTSIDE_US' then 'Outside the US' when 'UNALLOCATED' then 'Unallocated' end) as market_name,
    season_year, purpose, dimension,
    round(score, 2) as score,
    round(case when interval_applied then wilson_low end, 2) as score_interval_low,
    round(case when interval_applied then wilson_high end, 2) as score_interval_high,
    interval_applied,
    {{ dq_grade('round(case when interval_applied then coalesce(wilson_low, score) else score end, 2)') }} as grade,
    round(n_records, 1) as record_count,
    rules_scored, limiting_dimension,
    list_slice(coalesce(failing_rules, []), 1, 3) as top_failing_rules
from sized
left join (select distinct club_market_id as cm, market_name from {{ ref('club_market_map') }}) m on m.cm = sized.club_market_id
