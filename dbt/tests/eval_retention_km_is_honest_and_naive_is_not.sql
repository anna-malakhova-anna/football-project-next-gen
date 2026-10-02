{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). Against the generator's true churn parameters: the overall curve is inside its interval at every step, about
-- 95% of reliable segment cells are (the intervals are honest; a coverage below 85% means they are too narrow), and the naive age-out-as-churn
-- version understates retention for the oldest youth entrants by a wide margin (the reason the censoring rule exists).
select 'overall_curve_outside_ci' as problem, cast(years_since_entry as varchar) as detail
from {{ ref('eval_retention') }} where segment_type = 'ALL' and not truth_in_ci
union all
select 'ci_coverage_below_85pct', cast(round(avg(truth_in_ci::int), 3) as varchar)
from {{ ref('eval_retention') }} where reliable having avg(truth_in_ci::int) < 0.85
union all
select 'naive_does_not_understate_for_oldest_youth', cast(min(naive_understates_by) as varchar)
from {{ ref('eval_retention') }}
where segment_type = 'entry_age_band' and segment_value = '14-17' and years_since_entry = 1 having min(naive_understates_by) < 0.10
union all
select 'naive_differs_where_nobody_ages_out', segment_value
from {{ ref('eval_retention') }}
where segment_type = 'entry_age_band' and segment_value in ('18-29', '30-44', '45+') and abs(naive_understates_by) > 1e-6
