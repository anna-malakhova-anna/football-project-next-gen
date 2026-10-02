{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). What we expect of the acquisition analysis, checked against the truth. Statements of what a sound design should show, not tuning targets.
--   * the programme-caused accounts the generator recorded lie inside the estimate's range
--   * the pre-period (years before launch) is flat: the estimate's interval contains zero at every pre-period year
--   * the naive claim, "every account created after a registration", scaled for the households the linkage cannot see, overclaims by at least half again
-- (The OBSERVED naive count can land near the truth by cancellation: it sees only linked households, which offsets counting accounts that would have appeared anyway. The scaled version removes
-- the cancellation.)
select 'incremental_truth_inside_the_range' as check_name, truth_in_range as passed, 'estimate ' || cast(estimate as varchar) || ' vs truth ' || cast(truth as varchar) as detail
from {{ ref('eval_acquisition') }} where measure = 'incremental_accounts'
union all
select 'pre_period_is_flat', coalesce(bool_and(ci_low <= 0 and ci_high >= 0), false), 'pre-period years checked: ' || cast(count(*) as varchar)
from {{ ref('eval_acquisition_event_study') }} where years_since_launch < 0
union all
select 'scaled_naive_overclaims_by_half_again', estimate_over_truth >= 1.5, 'scaled naive / truth = ' || cast(estimate_over_truth as varchar)
from {{ ref('eval_acquisition') }} where measure = 'naive_net_new_scaled_by_link_rate'
