{{ config(tags=['phase2']) }}
-- Fail loudly if any cluster is bigger than one person could plausibly be (observed years x 2 US terms x 2 concurrent
-- leagues + 2 near-duplicates, from the observation window: macro idr_plausible_max_cluster_size). A transitive chain through siblings is
-- how this usually happens.
select matcher, stage, scope, cluster_id, max(cluster_size) as cluster_size
from {{ ref('idr_clusters') }}
group by 1, 2, 3, 4
having max(cluster_size) > {{ idr_plausible_max_cluster_size() }}
