{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). The naive and matched estimates against the true effect, which the generator knows exactly.
--   true_uplift_parameter   the configured uplift while a child is active (e.g. 0.15)
--   true_effect_pct         the effect the matched households ACTUALLY got over the months the estimate averages over, as a share of what they would have done with no programme.
--                           The generator records, for every participant account and month, the expected events as observed (uplift, decay after the last active season, and any
--                           reactivation the programme caused) and the expected events with no programme; the truth is (sum observed - sum no programme) / sum no programme over the
--                           matched households' post months. It is below the parameter because the uplift decays after churn, and above it where a registration reactivated a lapsed fan.
-- Nothing here feeds back into the design. If the matched estimate is far from the truth, that is investigated and written down (ADR-010), not tuned away.
{% set post = var('fan_post_months') %}
with y0 as (select first_observed_year as y from {{ ref('observation_window') }}),

m as (

    select m.account_id, m.e, m.post_months, date_diff('month', make_date((select y from y0), 1, 1), m.e) as e_mi
    from {{ ref('int_fan_cem_matched') }} m
    where m.is_treated

),

oracle as (

    select sum(t.expected_events_observed) as observed, sum(t.expected_events_no_programme) as no_programme
    from m
    join {{ source('ground_truth', 'fan_effect_truth') }} t
      on t.account_id = m.account_id and t.month_idx >= m.e_mi and t.month_idx < m.e_mi + m.post_months

),

param as (select any_value(true_uplift) as true_uplift_parameter from {{ source('ground_truth', 'fan_truth') }} where is_participant_household),

truth as (

    select (observed - no_programme) / no_programme as true_effect_pct, (select true_uplift_parameter from param) as true_uplift_parameter from oracle

)

select
    s.estimator,
    s.estimate_pct,
    s.ci_low_pct,
    s.ci_high_pct,
    round(t.true_uplift_parameter, 5)                                       as true_uplift_parameter,
    round(t.true_effect_pct, 5)                                             as true_effect_pct,
    round(s.estimate_pct - t.true_effect_pct, 5)                            as error_pct_points,
    round(s.estimate_pct / t.true_effect_pct, 3)                            as estimate_over_truth,
    t.true_effect_pct between s.ci_low_pct and s.ci_high_pct                as truth_in_ci
from {{ ref('mart_fan_outcomes_summary') }} s cross join truth t
order by case s.estimator when 'NAIVE' then 1 when 'DID_ADDITIVE' then 2 else 3 end
