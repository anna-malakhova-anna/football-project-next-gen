{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). The naive and matched estimates against the true effect, which the generator knows exactly.
--   true_uplift_parameter   the configured uplift while a child is active (e.g. 0.15)
--   true_effect_pct         the effect the matched households ACTUALLY got over the months the estimate averages over, as a share of what they would have done with no programme.
--                           The generator records, for every participant account and month, the expected events as observed (uplift, decay after the last active season, and any
--                           reactivation the programme caused) and the expected events with no programme; the truth is (sum observed - sum no programme) / sum no programme over the
--                           matched households' post months. It is below the parameter because the uplift decays after churn, and above it where a registration reactivated a lapsed fan.
-- (Each estimator is compared with the truth over the households and months IT averages over: see naive_oracle.) Nothing here feeds back into the design. If the matched estimate is far from the truth, that is investigated and written down (ADR-010), not tuned away.
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

-- the NAIVE estimator averages over a different population and window: every linked household (left-censored ones too), every month from its first registration to the end of the data, decay and
-- all. Its truth is the same oracle over THAT population and window, so each estimator is compared with the effect on the households and months it actually averages over.
naive_oracle as (

    select (sum(t.expected_events_observed) - sum(t.expected_events_no_programme)) / sum(t.expected_events_no_programme) as true_effect_naive_window_pct
    from {{ ref('int_participant_household_timeline') }} tl
    join {{ source('ground_truth', 'fan_effect_truth') }} t
      on t.account_id = tl.account_id
     and t.month_idx >= date_diff('month', make_date((select y from y0), 1, 1), tl.first_registration_month)
    where tl.is_linked

),

-- NAIVE_EXISTING averages over the linked households that already had an account (every fan status except NET_NEW and UNLINKED): the same oracle over THAT population and window.
naive_existing_oracle as (

    select (sum(t.expected_events_observed) - sum(t.expected_events_no_programme)) / sum(t.expected_events_no_programme) as true_effect_naive_existing_pct
    from {{ ref('int_participant_household_timeline') }} tl
    join {{ ref('fct_household_fan_status') }} fs on fs.household_id = tl.household_id and fs.fan_status not in ('NET_NEW', 'UNLINKED')
    join {{ source('ground_truth', 'fan_effect_truth') }} t
      on t.account_id = tl.account_id
     and t.month_idx >= date_diff('month', make_date((select y from y0), 1, 1), tl.first_registration_month)
    where tl.is_linked

),

param as (select any_value(true_uplift) as true_uplift_parameter from {{ source('ground_truth', 'fan_truth') }} where is_participant_household),

truth as (

    select (observed - no_programme) / no_programme as true_effect_matched_pct, (select true_effect_naive_window_pct from naive_oracle) as true_effect_naive_window_pct, (select true_effect_naive_existing_pct from naive_existing_oracle) as true_effect_naive_existing_pct,
           (select true_uplift_parameter from param) as true_uplift_parameter from oracle

)

select
    s.estimator,
    s.estimate_pct,
    s.ci_low_pct,
    s.ci_high_pct,
    round(t.true_uplift_parameter, 5)                                       as true_uplift_parameter,
    round(case s.estimator when 'NAIVE' then t.true_effect_naive_window_pct when 'NAIVE_EXISTING' then t.true_effect_naive_existing_pct else t.true_effect_matched_pct end, 5) as true_effect_pct,
    round(s.estimate_pct - case s.estimator when 'NAIVE' then t.true_effect_naive_window_pct when 'NAIVE_EXISTING' then t.true_effect_naive_existing_pct else t.true_effect_matched_pct end, 5) as error_pct_points,
    round(s.estimate_pct / case s.estimator when 'NAIVE' then t.true_effect_naive_window_pct when 'NAIVE_EXISTING' then t.true_effect_naive_existing_pct else t.true_effect_matched_pct end, 3) as estimate_over_truth,
    case s.estimator when 'NAIVE' then t.true_effect_naive_window_pct when 'NAIVE_EXISTING' then t.true_effect_naive_existing_pct else t.true_effect_matched_pct end between s.ci_low_pct and s.ci_high_pct as truth_in_ci
from {{ ref('mart_fan_outcomes_summary') }} s cross join truth t
order by case s.estimator when 'NAIVE_EXISTING' then 1 when 'NAIVE' then 2 when 'DID_ADDITIVE' then 3 else 4 end
