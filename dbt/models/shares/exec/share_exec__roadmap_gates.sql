{{ config(tags=['phase6']) }}
-- Release gates of the roadmap (Phase 6 addendum, section 2.2). One row per gate in product_targets: the CURRENT value computed here from existing exports, the status, and the bar geometry.
-- The site renders these columns and computes nothing. MET if the comparison holds; NOT_YET if it does not; PENDING when the source value is missing (rendered as "baseline pending", never as 0).
-- Aggregates only: no person key, no direct or quasi identifier. The headline fields (n_met, n_gates, blocking_gate_plain) repeat on every row so one query fills the page sentence.
with latest_src as (select max(season_year) as y from {{ ref('dq_scorecard_source') }}),

us_league as (

    select s.purpose, s.score
    from {{ ref('dq_scorecard_source') }} s join latest_src l on s.season_year = l.y
    where s.source_system = 'US_LEAGUE' and s.dimension = 'PURPOSE_SCORE'

),

identity_range as (

    select 100.0 * (interval_high - interval_low) / nullif(reported_point, 0) as pct
    from {{ ref('mart_uncertainty_decomposition') }}
    where component = 'IDENTITY' and participation_year = (select max(participation_year) from {{ ref('mart_uncertainty_decomposition') }} where component = 'IDENTITY')

),

-- a country's counting score is the weaker of: the share of its known organizations that sent a file (timeliness), and its weakest reporting organization's counting score
intl_year as (select max(season_year) as y from {{ ref('dq_scorecard_org') }} where source_system = 'INTL_FED'),

country_time as (

    select o.region_code, 100.0 * count(*) filter (where o.dimension = 'TIMELINESS' and o.score > 0) / nullif(count(*) filter (where o.dimension = 'TIMELINESS'), 0) as timeliness
    from {{ ref('dq_scorecard_org') }} o join intl_year y on o.season_year = y.y
    where o.source_system = 'INTL_FED' and o.purpose = 'COUNT' group by o.region_code

),

country_quality as (

    select o.region_code, min(o.score) as weakest_reporting
    from {{ ref('dq_scorecard_org') }} o join intl_year y on o.season_year = y.y
    where o.source_system = 'INTL_FED' and o.purpose = 'COUNT' and o.dimension = 'PURPOSE_SCORE' and o.score > 0 group by o.region_code

),

country_score as (

    select t.region_code, least(t.timeliness, coalesce(q.weakest_reporting, 0)) as score
    from country_time t left join country_quality q using (region_code)

),

consent as (

    select participation_year, household_id, has_known_full, marketing_status
    from {{ ref('int_household_year_consent') }}
    where participation_year = (select max(participation_year) from {{ ref('int_household_year_consent') }})

),

current_values as (

    select 'X_COUNT' as gate_id, (select score from us_league where purpose = 'COUNT') as current_value
    union all select 'X_GEO', (select score from us_league where purpose = 'GEO')
    union all select 'Y', (select pct from identity_range)
    union all select 'N', (select count(*) filter (where {{ dq_grade('score') }} in ('A', 'B')) from country_score)
    union all select 'Z_ANALYTICS', (select 100.0 * count(*) filter (where has_known_full) / nullif(count(*), 0) from consent)
    -- an opt-in is fully known when it is GRANTED_FULL (what, when and which purpose are known); GRANTED_INCOMPLETE is an opt-in with a gap
    union all select 'Z_ACTIVATION', (select 100.0 * count(*) filter (where marketing_status = 'GRANTED_FULL') / nullif(count(*) filter (where marketing_status in ('GRANTED_FULL', 'GRANTED_INCOMPLETE')), 0) from consent)

),

g as (

    select t.gate_id, t.product_id, t.kind, t.metric as definition, t.plain_name, t.comparison, t.threshold_value as target, t.unit, t.baseline_2025, t.gate_for,
           t.source_model, t.source_field, round(c.current_value, 2) as current_value
    from {{ ref('product_targets') }} t left join current_values c using (gate_id)

),

scored as (

    select g.*,
           case when current_value is null then 'PENDING'
                when comparison = 'at least' and current_value >= target then 'MET'
                when comparison = 'at most' and current_value <= target then 'MET'
                else 'NOT_YET' end as status,
           -- bar axis: "at least" gates run 0 to 125% of the target; "at most" guardrails run 0 to 200% of the limit; the marker sits at the target
           case when comparison = 'at least' then target * 1.25 else target * 2.0 end as axis_max
    from g

),

final as (

    select gate_id, product_id, kind, definition, plain_name, comparison, target, unit, baseline_2025, gate_for, source_model, source_field, current_value, status,
           case when current_value is null then null else round(least(100.0, 100.0 * current_value / axis_max), 1) end as bar_fill_pct,
           round(100.0 * target / axis_max, 1) as target_marker_pct,
           case unit when 'percent' then '%' when 'score' then ' points' else '' end as sfx,
           case unit when 'count' then ' countries' else '' end as tail
    from scored

)

select f.* exclude (sfx, tail),
       case status when 'MET' then 'Met ✓' when 'NOT_YET' then 'Not yet' else 'Baseline pending' end as status_text,
       case when current_value is null then 'baseline pending'
            when comparison = 'at least' then 'now ' || regexp_replace(cast(round(current_value, 1) as varchar), '\.0$', '') || sfx || ', needs ' || regexp_replace(cast(round(target, 1) as varchar), '\.0$', '') || sfx || ' or more' || tail
            else 'now ' || regexp_replace(cast(round(current_value, 2) as varchar), '\.0+$', '') || sfx || ', limit ' || regexp_replace(cast(round(target, 1) as varchar), '\.0$', '') || sfx end as value_text,
       count(*) over () as n_gates,
       count(*) filter (where status = 'MET') over () as n_met,
       (select string_agg(plain_name, ' and ' order by plain_name) from (select distinct plain_name from final where status <> 'MET' and gate_for like '%v1 exit%' and product_id = 'DP4')) as blocking_gate_plain
from final f
order by gate_id
