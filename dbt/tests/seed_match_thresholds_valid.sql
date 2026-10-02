{{ config(tags=['phase2']) }}
-- 0 < t_review < t_auto < 1 and a positive prior for every matcher version.
select matcher_version, t_review, t_auto, prior_odds
from {{ ref('match_thresholds') }}
where not (t_review > 0 and t_review < t_auto and t_auto < 1 and prior_odds > 0)
