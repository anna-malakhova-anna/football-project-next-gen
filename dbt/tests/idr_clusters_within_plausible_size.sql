{{ config(tags=['phase2']) }}
-- Fail loudly if any cluster is bigger than one person could plausibly be (3 seasons x 2 US terms x 2 concurrent
-- leagues + 2 near-duplicates = 14, var idr_plausible_max_cluster_size). A transitive chain through siblings is
-- how this usually happens.
select matcher, stage, scope, cluster_id, max(cluster_size) as cluster_size
from {{ ref('idr_clusters') }}
group by 1, 2, 3, 4
having max(cluster_size) > {{ var('idr_plausible_max_cluster_size') }}
