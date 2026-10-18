-- RESTRICTED (schema `linkage`). The estimates side by side, with how many households stand behind them.
--   NAIVE            participant vs non-participant fan households over the same months (mart_fan_naive): biased by who enrolls
--   DID_ADDITIVE     matched difference-in-differences, the headline: (post - pre for matched participants) - (post - pre for weighted matched comparisons),
--                    in events per household-month, then expressed as a % of the participants' counterfactual post level (post mean - DiD)
--   DID_RATIO        the same data as a ratio of ratios, (post/pre treated) / (post/pre comparison) - 1: a sensitivity check on the additive form (point estimate only)
-- Uncertainty is ANALYTIC (decided here, not bootstrapped): the standard error of the difference between the participants' mean change and the comparisons'
-- weighted mean change, from the household-level changes, with 95% intervals = estimate +/- 1.96 se. Comparison accounts can be candidates at several event
-- months, so their weights repeat across strata and the interval is somewhat too narrow; the n_comparison_pairs column says how many pairs there are.
-- match_rate = treated households that found at least one comparison / eligible treated households (not left-censored, enough pre and post months).
-- Reading it: the estimate describes LINKED households only (ADR-009 explains who gets linked).
with u as (select *, post_rate - pre_rate as d from {{ ref('int_fan_cem_matched') }}),

t as (select count(*) as n, avg(d) as mean_d, var_samp(d) / count(*) as var_mean, avg(pre_rate) as pre, avg(post_rate) as post from u where is_treated),

c as (

    select
        count(*)                                                            as pairs,
        count(distinct account_id)                                          as units,
        sum(weight * d) / sum(weight)                                       as mean_d,
        sum(weight * pre_rate) / sum(weight)                                as pre,
        sum(weight * post_rate) / sum(weight)                               as post,
        power(sum(weight), 2) / sum(weight * weight)                        as n_eff
    from u where not is_treated

),

c2 as (

    select sum(u.weight * u.weight * power(u.d - c.mean_d, 2)) / power(sum(u.weight), 2) as var_mean
    from u cross join c where not u.is_treated

),

elig as (select count(*) as n from {{ ref('int_fan_cem_candidates') }} where is_treated),

did as (

    select
        t.mean_d - c.mean_d                                                 as did,
        sqrt(t.var_mean + c2.var_mean)                                      as se,
        t.post - (t.mean_d - c.mean_d)                                      as counterfactual_post,
        (t.post / t.pre) / (c.post / c.pre) - 1                             as did_ratio
    from t cross join c cross join c2

)

select
    estimator, estimate_pct, ci_low_pct, ci_high_pct, cast(null as double) as estimate_events_per_month, cast(null as double) as se_events_per_month,
    treated_households as treated_matched, cast(null as bigint) as comparison_pairs, comparison_units as comparison_units,
    cast(null as bigint) as eligible_treated, cast(null as double) as match_rate
from {{ ref('mart_fan_naive') }}
union all
select
    'DID_ADDITIVE', round(did / counterfactual_post, 5), round((did - 1.96 * se) / counterfactual_post, 5), round((did + 1.96 * se) / counterfactual_post, 5),
    round(did, 5), round(se, 5), t.n, c.pairs, c.units, elig.n, round(t.n * 1.0 / elig.n, 4)
from did cross join t cross join c cross join elig
union all
select 'DID_RATIO', round(did_ratio, 5), null, null, null, null, t.n, c.pairs, c.units, elig.n, round(t.n * 1.0 / elig.n, 4)
from did cross join t cross join c cross join elig
