{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). What we expect of the fandom analysis, checked against the truth. Each estimator is compared with the truth over the households and months it averages over.
-- These are statements of what a sound design should show, not tuning targets: a failure means investigate and document (ADR-010), not adjust the design.
-- HONEST NOTE (rework step 7): the first generator made the naive comparison overstate the effect about threefold, and the spec expects that. In the fan-acquisition generator it does NOT:
-- the naive estimate lands on its own truth (about 0.99x) because two biases cancel. Participants are busier than other accounts before registering (selection, upward), but the linked
-- set also contains many NET_NEW accounts with low baselines (composition, downward). The naive estimate is right by cancellation, which is luck and not validity, so the checks no longer
-- claim that naive overstates. They check that the selection is real and that matching removes it: the unmatched comparison is clearly biased before registration, the matched one is not,
-- the matched estimate is close to its truth, and the pre-trend is flat.
select 'selection_is_real_unmatched_pre_period_gap_over_5pct' as check_name, value > 0.05 as passed, 'unmatched pre-period gap = ' || cast(round(value, 4) as varchar) as detail
from {{ ref('eval_fan_matching_diagnostics') }} where measure = 'unmatched_pre_period_gap_pct'
union all
select 'matching_removes_the_pre_period_gap', abs(m.value) < abs(u.value) / 3, 'matched gap ' || cast(round(m.value, 4) as varchar) || ' vs unmatched ' || cast(round(u.value, 4) as varchar)
from {{ ref('eval_fan_matching_diagnostics') }} m join {{ ref('eval_fan_matching_diagnostics') }} u on u.measure = 'unmatched_pre_period_gap_pct' where m.measure = 'matched_pre_period_gap_pct'
union all
select 'matched_is_within_30pct_of_truth', estimate_over_truth between 0.7 and 1.3, 'matched / truth = ' || cast(estimate_over_truth as varchar)
from {{ ref('eval_fan_effect') }} where estimator = 'DID_ADDITIVE'
union all
select 'pretrend_is_small', value < 0.10, 'largest pre-period gap = ' || cast(round(value, 4) as varchar)
from {{ ref('eval_fan_matching_diagnostics') }} where measure = 'pretrend_max_abs_effect_pct'
