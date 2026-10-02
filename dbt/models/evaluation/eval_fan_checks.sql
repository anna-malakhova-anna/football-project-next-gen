{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). What the spec expects of the fandom analysis, checked against the truth. These are statements of the expected
-- ordering, not tuning targets: naive badly inflated, matched much closer. A failure here means investigate and document (ADR-010), not adjust the design.
select 'naive_is_inflated_at_least_2x' as check_name, estimate_over_truth >= 2 as passed, 'naive / truth = ' || cast(estimate_over_truth as varchar) as detail
from {{ ref('eval_fan_effect') }} where estimator = 'NAIVE'
union all
select 'matched_is_closer_than_naive',
       (select abs(error_pct_points) from {{ ref('eval_fan_effect') }} where estimator = 'DID_ADDITIVE')
         < (select abs(error_pct_points) from {{ ref('eval_fan_effect') }} where estimator = 'NAIVE') / 5,
       'matched error is under a fifth of the naive error'
union all
select 'matched_is_within_30pct_of_truth', estimate_over_truth between 0.7 and 1.3, 'matched / truth = ' || cast(estimate_over_truth as varchar)
from {{ ref('eval_fan_effect') }} where estimator = 'DID_ADDITIVE'
union all
select 'pretrend_is_small', value < 0.10, 'largest pre-period gap = ' || cast(round(value, 4) as varchar)
from {{ ref('eval_fan_matching_diagnostics') }} where measure = 'pretrend_max_abs_effect_pct'
