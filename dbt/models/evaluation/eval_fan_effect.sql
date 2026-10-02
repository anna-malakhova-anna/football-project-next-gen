{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). The naive and matched estimates against the true uplift, which the generator knows.
--   true_uplift_parameter   the configured uplift while a child is active (e.g. 0.15)
--   true_effect_pct         the uplift the matched households ACTUALLY got over the months the estimate averages over: the uplift decays after a household's
--                           last active season, so this is below the parameter. For each matched participant household and each post month, the true multiplier
--                           minus one, averaged with weights proportional to the household's pre-period engagement (a stand-in for its baseline level, so a
--                           busy household counts for more, as it does in the estimate).
-- Nothing here feeds back into the design. If the matched estimate is far from the truth, that is investigated and written down (ADR-010), not tuned away.
{% set post = var('fan_post_months') %}
with m as (

    select m.account_id, m.e, m.pre_rate, m.post_months, t.true_uplift, t.decay_half_life_months, t.last_active_year
    from {{ ref('int_fan_cem_matched') }} m
    join {{ source('ground_truth', 'fan_truth') }} t on t.account_id = m.account_id
    where m.is_treated

),

months as (

    select m.*, k, (m.e + to_months(k))::date as month_k,
           make_date(m.last_active_year, 12, 1) as active_end
    from m cross join (select unnest(range(0, {{ post }})) as k) ks
    where k < m.post_months

),

uplift as (

    select pre_rate,
           true_uplift * case when month_k <= active_end then 1.0
                              else power(0.5, date_diff('month', active_end, month_k) * 1.0 / decay_half_life_months) end as uplift_k
    from months

),

truth as (

    select sum(pre_rate * uplift_k) / sum(pre_rate) as true_effect_pct, avg(uplift_k) as true_effect_unweighted_pct,
           (select any_value(true_uplift) from m) as true_uplift_parameter
    from uplift

)

select
    s.estimator,
    s.estimate_pct,
    s.ci_low_pct,
    s.ci_high_pct,
    round(t.true_uplift_parameter, 5)                                       as true_uplift_parameter,
    round(t.true_effect_pct, 5)                                             as true_effect_pct,
    round(t.true_effect_unweighted_pct, 5)                                  as true_effect_unweighted_pct,
    round(s.estimate_pct - t.true_effect_pct, 5)                            as error_pct_points,
    round(s.estimate_pct / t.true_effect_pct, 3)                            as estimate_over_truth,
    t.true_effect_pct between s.ci_low_pct and s.ci_high_pct                as truth_in_ci
from {{ ref('mart_fan_outcomes_summary') }} s cross join truth t
order by case s.estimator when 'NAIVE' then 1 when 'DID_ADDITIVE' then 2 else 3 end
