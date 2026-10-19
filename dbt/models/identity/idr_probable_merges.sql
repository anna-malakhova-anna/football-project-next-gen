-- DP2 RESTRICTED PORT (consumer: DP4). The PROBABLE identity links, after steward review, that would merge two different AUTO clusters: the uncertain merges that widen the participant count's bounds.
-- Two record keys per row, nothing else. DP4's cost of a rule (mart_dq_impact) counts the ones a failing record is entangled in, instead of reading idr_match_edges and idr_clusters.
select e.record_a, e.record_b
from {{ ref('idr_match_edges') }} e
join {{ ref('idr_clusters') }} ca on ca.matcher = e.matcher and ca.stage = e.stage and ca.scope = 'AUTO' and ca.match_record_id = e.record_a
join {{ ref('idr_clusters') }} cb on cb.matcher = e.matcher and cb.stage = e.stage and cb.scope = 'AUTO' and cb.match_record_id = e.record_b
where e.matcher = '{{ var("matcher") }}' and e.stage = 'POST_REVIEW' and e.tier = 'PROBABLE' and ca.cluster_id <> cb.cluster_id
