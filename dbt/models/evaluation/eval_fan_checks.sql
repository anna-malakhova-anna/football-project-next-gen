{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). What we expect of the fandom analysis, checked against the truth, stated as ORDERINGS: the naive comparison overstates the effect, the matched one
-- is much closer to the truth than the naive one, and the pre-period is flat. These are statements of what a sound design should show, not tuning targets: a failure means
-- investigate and document (ADR-010), not adjust the design.
-- (Rework step 3 restated them. They used to say "naive at least 2x the truth and matched within a fifth of the naive error", which encoded the strong selection of the first
-- generator. In the fan-acquisition generator account holders are fandom-heavy as a group, so participants differ less from the other account holders and the naive gap is smaller;
-- the truth also now includes reactivations the programme caused.)
select 'naive_overstates_the_effect' as check_name, estimate_over_truth >= 1.25 as passed, 'naive / truth = ' || cast(estimate_over_truth as varchar) as detail
from {{ ref('eval_fan_effect') }} where estimator = 'NAIVE'
union all
select 'matched_is_much_closer_than_naive',
       (select abs(error_pct_points) from {{ ref('eval_fan_effect') }} where estimator = 'DID_ADDITIVE')
         < (select abs(error_pct_points) from {{ ref('eval_fan_effect') }} where estimator = 'NAIVE') / 2,
       'matched error is under half the naive error'
union all
select 'matched_is_within_30pct_of_truth', estimate_over_truth between 0.7 and 1.3, 'matched / truth = ' || cast(estimate_over_truth as varchar)
from {{ ref('eval_fan_effect') }} where estimator = 'DID_ADDITIVE'
union all
select 'pretrend_is_small', value < 0.10, 'largest pre-period gap = ' || cast(round(value, 4) as varchar)
from {{ ref('eval_fan_matching_diagnostics') }} where measure = 'pretrend_max_abs_effect_pct'
