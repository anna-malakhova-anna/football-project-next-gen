{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). Checks on eval_retention, kept as a model in models/evaluation/ (with an accepted_values test on `passed`) because
-- a test outside this folder that read the truth would break the isolation rule. Against the generator's true churn parameters:
--   * the overall curve is inside its interval at every step
--   * about 95% of reliable segment cells are (a coverage below 85% means the intervals are too narrow)
--   * the naive age-out-as-churn version understates retention for the oldest youth entrants by a wide margin (the reason the censoring rule exists)
--   * naive and censored agree where nobody ages out inside the window (an adult cannot age out)
select 'overall_curve_inside_ci' as check_name,
       coalesce(bool_and(truth_in_ci), false) as passed,
       'steps checked: ' || count(*) as detail
from {{ ref('eval_retention') }} where segment_type = 'ALL'
union all
select 'ci_coverage_at_least_85pct', coalesce(avg(truth_in_ci::int), 0) >= 0.85, 'coverage: ' || cast(round(avg(truth_in_ci::int), 3) as varchar)
from {{ ref('eval_retention') }} where reliable
union all
select 'naive_understates_for_oldest_youth', coalesce(min(naive_understates_by), 0) >= 0.10, 'understatement at step 1: ' || cast(min(naive_understates_by) as varchar)
from {{ ref('eval_retention') }} where segment_type = 'entry_age_band' and segment_value = '14-17' and years_since_entry = 1
union all
select 'naive_equals_censored_for_adults', coalesce(bool_and(abs(naive_understates_by) < 1e-6), false), 'bands: 18-29, 30-44, 45+'
from {{ ref('eval_retention') }} where segment_type = 'entry_age_band' and segment_value in ('18-29', '30-44', '45+')
