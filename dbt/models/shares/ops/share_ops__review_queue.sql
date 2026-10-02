-- OPS share: the identity review queue (cluster conflicts, then probable pairs) with both records side by side.
select
    priority, queue_item_id, matcher, item_type, cluster_id, record_a, record_b, match_probability, override_applied,
    suggested_action, integrity_issues, members, feature_levels, weight_breakdown, reason
from {{ ref('idr_review_queue') }}
