{{ config(tags=['phase2']) }}
-- The twin/sibling guard: no AUTO_MATCH edge may join two records registered in the same org and season
-- with different first names (two children registered together). Covers every matcher and stage.
select e.matcher, e.stage, e.record_a, e.record_b, e.link_method
from {{ ref('idr_match_edges') }} e
join {{ ref('idr_pair_features') }} f on f.record_a = e.record_a and f.record_b = e.record_b
where e.tier in ('AUTO_MATCH', 'STEWARD')
  and e.stage = 'PRE_REVIEW'
  and f.context_level = 'SAME_ORG_SAME_SEASON'
  and f.first_name_level = 'DIFFERENT'
