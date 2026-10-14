{{ config(schema='phase5_restricted') }}
-- The same connected components as p5_clusters but ALSO merging PROBABLE links: the label-free LOW end of the identity range. A market's children counted this way can only be fewer.
with nodes as (select match_record_id as node from {{ ref('p5_idr_input_records') }}),

edges as (select record_a as a, record_b as b from {{ ref('p5_pair_scores') }} where tier in ('AUTO_MATCH', 'PROBABLE'))

select node as match_record_id, 'PP-' || md5(cluster_id) as p5_low_person_id
from {{ connected_components('nodes', 'edges', []) }}
