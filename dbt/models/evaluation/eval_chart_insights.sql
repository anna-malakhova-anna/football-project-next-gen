{{ config(tags=['phase5']) }}
-- EVALUATION: the numbers inside headline sentences of the cards that are graded against the synthetic answer key (Phase 5.1, section 5.2). Same long shape as the share_*__chart_insights models, but it lives here
-- because it reads evaluation models: an answer-key number never enters a share. Counts of checks and score points; no person-level value.
with u as (
    select participation_year,
           identity_interval_contains_truth as identity_ok,
           true_participants_in_data between dq_strict and dq_lenient as dq_ok,
           true_total_participants between identity_point + coverage_low and identity_point + coverage_high as coverage_ok
    from {{ ref('eval_uncertainty_decomposition') }}
),

checks as (
    select count(*) * 3 as n_checks, sum(identity_ok::int + dq_ok::int + coverage_ok::int) as n_inside from u
),

f as (
    select variant_id, f1, in_standard from {{ ref('eval_minimization_tradeoff') }} where is_headline_matcher and f1 is not null
),

cost as (
    select 100 * ((select f1 from f order by variant_id limit 1) - (select f1 from f where in_standard limit 1)) as pts
),

gmp as (
    select * from {{ ref('eval_gmp_scenario_summary') }} where market_group = 'ALL'
),

rows_ as (
    select 'U3' as chart_id, 'both' as lens, 'n_checks' as field, cast(n_checks as varchar) as value_display, n_checks * 1.0 as value_raw from checks
    union all select 'U3', 'both', 'n_inside', cast(n_inside as varchar), n_inside * 1.0 from checks
    -- a whole clause, so the card's sentence is true whichever way the cost goes (pts = F1 points the standard loses against the full fields)
    union all select 'P3', 'both', 'matching_effect',
           case when pts <= 0 then 'it matches as accurately as the full fields'
                when pts < 0.5 then 'it matches almost as accurately as the full fields (less than half a point lower)'
                else 'it matches ' || cast(round(pts, 1) as varchar) || ' points less accurately than the full fields' end,
           round(pts, 2) from cost
)

, gmp_rows as (
    -- Phase 7 (G3): the planning scenario graded against the synthetic answer key (ADR-026)
    select 'G3' as chart_id, 'both' as lens, 'n_markets' as field, cast(markets as varchar) as value_display, markets * 1.0 as value_raw from gmp
    union all select 'G3', 'both', 'n_inside', cast(truth_in_range as varchar), truth_in_range * 1.0 from gmp
    union all select 'G3', 'both', 'n_above', cast(truth_above_range as varchar), truth_above_range * 1.0 from gmp
    union all select 'G3', 'both', 'n_direction_wrong', cast(direction_wrong as varchar), direction_wrong * 1.0 from gmp
    union all select 'G3', 'both', 'n_direction_graded', cast(direction_graded as varchar), direction_graded * 1.0 from gmp
    -- a whole clause, so the card's sentence is true whatever the count (ADR-045: direction graded only beyond the minimum detectable change)
    union all select 'G3', 'both', 'direction_result',
           'We grade the guessed direction only where the true number moved by more than '
           || cast(round(minimum_detectable_change * 100)::int as varchar) || '%, the smallest change the method can tell from noise. '
           || case when direction_graded = 0 then 'No market moved that much, so the direction could not be graded'
                   else 'That was ' || cast(direction_graded as varchar) || ' of ' || cast(markets as varchar)
                        || ' markets, and the direction was wrong in ' || cast(direction_wrong as varchar) || ' of them' end,
           direction_graded * 1.0 from gmp
    union all select 'G3', 'both', 'n_proxy_known', cast(proxy_direction_known as varchar), proxy_direction_known * 1.0 from gmp
    union all select 'G3', 'both', 'n_proxy_right', cast(proxy_direction_right as varchar), proxy_direction_right * 1.0 from gmp
)

select chart_id, lens, field, value_display, value_raw, 'NONE' as suppressed from (select * from rows_ union all select * from gmp_rows) order by chart_id, field
