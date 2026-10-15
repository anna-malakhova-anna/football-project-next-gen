{{ config(tags=['phase5']) }}
-- depends_on: {{ ref('p5_params') }}
-- CLUB share: every number that appears inside a headline sentence on the site (Phase 5.1, section 5.2), computed and rounded HERE so no page script or Python ever computes one.
-- Long format: one row per chart, lens and field. value_display is the string to paste into a sentence (people and families as whole numbers, estimates rounded to the nearest 10 with "about",
-- shares as whole percents or "1 in N"); value_raw is kept for tests. A count above zero and below k_min is never published: value_display reads "fewer than N" and suppressed is PRIMARY.
-- Reads only approved aggregate marts and configuration seeds. "Ready" means grade A or B (the two bands the grade seed describes as usable without a rebuild).
{% set k = privacy_param('k_min') %}
with
q as (select max(season_year) as y from {{ ref('dq_scorecard_source') }}),

purpose_scores as (
    select s.source_system, s.purpose, s.grade, s.score, d.plain_name as source_plain, p.plain_label as purpose_plain, p.purpose_order
    from {{ ref('dq_scorecard_source') }} s
    join q on s.season_year = q.y
    join {{ ref('source_display') }} d on d.source_system = s.source_system
    join (select purpose, plain_label, row_number() over (order by purpose) as purpose_order from {{ ref('dq_purposes') }}) p on p.purpose = s.purpose
    where s.dimension = 'PURPOSE_SCORE' and s.score is not null
),

worst as (
    select source_plain, purpose_plain from purpose_scores order by score, source_plain, purpose_plain limit 1
),

trend as (
    select entity_id, purpose, season_year, out_of_control, prior_seasons
    from {{ ref('dq_trend') }}
    where entity_type = 'SOURCE' and purpose = 'ACTIVATE'
),

trend_latest as (
    select entity_id, purpose, season_year, out_of_control, prior_seasons from trend where prior_seasons >= 3 and season_year = (select max(season_year) from trend)
),

trend_early as (
    select entity_id from trend where prior_seasons < 3 and season_year = (select max(season_year) from trend)
),

orgs as (
    select o.channel, o.grade,
           case when o.record_count < {{ p5_param('size_band_small_below') }} then 'small' when o.record_count >= {{ p5_param('size_band_large_from') }} then 'large' else 'medium' end as size_band
    from {{ ref('dq_scorecard_org') }} o, q
    where o.season_year = q.y and o.purpose = 'SEGMENT' and o.dimension = 'PURPOSE_SCORE' and o.reported and o.score is not null
),

org_groups as (
    select 'channel:' || channel as grp, count(*) as n, count(*) filter (where grade in ('C', 'D')) as n_cd from orgs group by channel
    union all
    select 'size:' || size_band, count(*), count(*) filter (where grade in ('C', 'D')) from orgs group by size_band
),

pareto as (
    select purpose, rank_in_purpose, cumulative_share, impact_units, rule_id,
           min(case when cumulative_share >= 0.8 then rank_in_purpose end) over (partition by purpose) as k80
    from {{ ref('mart_dq_impact') }}, q
    where season_year = q.y and population = 'MODELLED' and purpose in ('COUNT', 'SEGMENT', 'RETAIN', 'ACTIVATE')
),

pareto_k as (
    select purpose, least(coalesce(any_value(k80), 6), 6) as k from pareto group by purpose
),

pareto_cum as (
    select p.purpose, k.k, p.cumulative_share
    from pareto p join pareto_k k on p.purpose = k.purpose and p.rank_in_purpose = k.k
),

pareto_top as (
    select p.purpose, p.impact_units, r.plain_label
    from pareto p join {{ ref('dq_rule_registry') }} r on r.rule_id = p.rule_id
    where p.rank_in_purpose = 1
),

my as (select max(participation_year) as y from {{ ref('mart_market_coverage') }}),

markets as (
    select m.club_market_id, m.participants_allocated, m.grade_count, m.orgs_dark
    from {{ ref('mart_market_coverage') }} m, my
    where m.participation_year = my.y and regexp_matches(m.club_market_id, '^CM-') and m.participants_allocated >= {{ k }}
),

funnel as (
    select f.step_no, f.n, f.lost_dq, f.lost_privacy
    from {{ ref('mart_activation_funnel') }} f
    where f.market_id = 'ALL' and f.participation_year = (select max(participation_year) from {{ ref('mart_activation_funnel') }})
),

funnel_ends as (
    select (select n from funnel where step_no = (select min(step_no) from funnel where n > 0 and step_no >= 3)) as households,
           (select n from funnel where step_no = (select max(step_no) from funnel)) as activatable,
           (select sum(lost_dq) from funnel) as lost_dq,
           (select sum(lost_privacy) from funnel) as lost_privacy
),

rows_ as (
    -- Q1
    select 'Q1' as chart_id, 'both' as lens, 'n_sources' as field, cast(count(distinct source_system) as varchar) as value_display, count(distinct source_system) * 1.0 as value_raw, false as is_count from purpose_scores
    union all select 'Q1', 'both', 'n_ready_count', cast(count(*) as varchar), count(*) * 1.0, false from purpose_scores where purpose = 'COUNT' and grade in ('A', 'B')
    union all select 'Q1', 'both', 'n_ready_activate', cast(count(*) as varchar), count(*) * 1.0, false from purpose_scores where purpose = 'ACTIVATE' and grade in ('A', 'B')
    union all select 'Q1', 'both', 'worst_source_plain', source_plain, null, false from worst
    union all select 'Q1', 'both', 'worst_use_plain', lower(purpose_plain), null, false from worst
    -- Q2 (provisional: reads the control limits as built; ADR-020 records the decision about their width)
    union all select 'Q2', 'both', 'n_steady', cast(count(*) filter (where not coalesce(out_of_control, false)) as varchar), count(*) filter (where not coalesce(out_of_control, false)) * 1.0, false from trend_latest
    union all select 'Q2', 'both', 'n_shift', cast(count(*) filter (where coalesce(out_of_control, false)) as varchar), count(*) filter (where coalesce(out_of_control, false)) * 1.0, false from trend_latest
    union all select 'Q2', 'both', 'latest_season', cast(max(season_year) as varchar), max(season_year) * 1.0, false from trend_latest
    union all select 'Q2', 'both', 'n_too_early', cast(count(*) as varchar), count(*) * 1.0, false from trend_early
    -- Q4: share of leagues graded C or D for splitting players by age and gender (a group of fewer than k_min leagues is not reported)
    union all select 'Q4', 'both', 'pct_cd_' || lower(replace(grp, ':', '_')), cast(round(100.0 * n_cd / n) as bigint) || '%', round(100.0 * n_cd / n), false from org_groups where n >= {{ k }}
    union all select 'Q4', 'both', 'n_leagues_' || lower(replace(grp, ':', '_')), cast(n as varchar), n * 1.0, false from org_groups where n >= {{ k }}
    -- Q3, one set of fields per use
    union all select 'Q3', 'both', 'top_k_' || lower(purpose), cast(k as varchar), k * 1.0, false from pareto_cum
    union all select 'Q3', 'both', 'cum_pct_' || lower(purpose), cast(round(100 * cumulative_share) as bigint) || '%', round(100 * cumulative_share), false from pareto_cum
    union all select 'Q3', 'both', 'top_problem_' || lower(purpose), lower(plain_label), null, false from pareto_top
    union all select 'Q3', 'both', 'top_problem_size_' || lower(purpose), 'about ' || cast(round(impact_units, -1) as bigint), impact_units * 1.0, true from pareto_top
    -- M1 and M2
    union all select 'M1', 'club', 'n_markets', cast(count(*) as varchar), count(*) * 1.0, false from markets
    union all select 'M1', 'club', 'n_markets_ready', cast(count(*) as varchar), count(*) * 1.0, false from markets where grade_count in ('A', 'B')
    union all select 'M1', 'club', 'n_markets_dark', cast(count(*) as varchar), count(*) * 1.0, false from markets where orgs_dark > 0
    union all select 'M2', 'club', 'n_markets', cast(count(*) as varchar), count(*) * 1.0, false from markets
    -- M3: the two lenses on the same funnel
    union all select 'M3', 'club', 'activatable_households_ratio', 'about 1 in ' || cast(round(households / nullif(activatable, 0)) as bigint), activatable / nullif(households, 0), false from funnel_ends
    union all select 'M3', 'club', 'households_total', 'about ' || cast(round(households, -1) as bigint), households, true from funnel_ends
    union all select 'M3', 'club', 'activatable_households', 'about ' || cast(round(activatable, -1) as bigint), activatable, true from funnel_ends
    union all select 'M3', 'club', 'main_loss', case when lost_dq >= lost_privacy then 'missing or unusable records' else 'consent that was missing, declined or withdrawn' end, null, false from funnel_ends
)

select chart_id, lens, field,
       case when is_count and value_raw > 0 and value_raw < {{ k }} then 'fewer than ' || cast({{ k }} as varchar) else value_display end as value_display,
       case when is_count and value_raw > 0 and value_raw < {{ k }} then null else value_raw end as value_raw,
       case when is_count and value_raw > 0 and value_raw < {{ k }} then 'PRIMARY' else 'NONE' end as suppressed
from rows_
order by chart_id, lens, field
