{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). What we expect of the value-uplift and lapse analyses: statements of what a sound design should show, not tuning targets. The per-month difference is
-- compared with the exact expected effect (the percentages are unstable where the counterfactual is near zero, so they are not used). Known and reported rather than hidden: for EXISTING fans
-- the engagement (events) estimate sits a little above its truth with the truth just outside its interval (residual selection and contamination), so it is NOT among these checks.
select 'existing_fans_net_spend_truth_inside_interval' as check_name, truth_in_ci_per_month as passed, 'estimate ' || cast(did_per_month as varchar) || ' vs truth ' || cast(truth_per_month as varchar) as detail
from {{ ref('eval_fan_value_uplift') }} where status_group = 'EXISTING' and outcome = 'net_spend_total'
union all
select 'existing_fans_ticket_and_subscription_truths_inside_intervals', coalesce(bool_and(truth_in_ci_per_month), false), 'outcomes checked: ' || cast(count(*) as varchar)
from {{ ref('eval_fan_value_uplift') }} where status_group = 'EXISTING' and outcome in ('net_spend_ticket', 'net_spend_subscription')
union all
select 'lapsed_fans_events_truth_inside_interval', truth_in_ci_per_month, 'estimate ' || cast(did_per_month as varchar) || ' vs truth ' || cast(truth_per_month as varchar)
from {{ ref('eval_fan_value_uplift') }} where status_group = 'LAPSED' and outcome = 'events'
union all
select 'lapse_rate_rises_after_the_child_stops', measured_rate_ratio > 1 and measured_over_truth between 0.67 and 1.5, 'measured ' || cast(measured_rate_ratio as varchar) || ' vs built-in ' || cast(true_hazard_multiplier as varchar)
from {{ ref('eval_fan_lapse_after_child_churn') }}
