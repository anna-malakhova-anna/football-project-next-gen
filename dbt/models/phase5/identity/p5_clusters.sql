-- Connected components of the AUTO_MATCH links: one cluster = one resolved child (p5_person_id). A record with no link is its own person.
-- PROBABLE pairs are not merged here (precision first); they are counted in p5_resolution_summary as the "possible further merges".
with nodes as (select match_record_id as node from {{ ref('p5_idr_input_records') }}),

edges as (select record_a as a, record_b as b from {{ ref('p5_pair_scores') }} where tier = 'AUTO_MATCH')

select node as match_record_id, 'PP-' || md5(cluster_id) as p5_person_id, cluster_size
from {{ connected_components('nodes', 'edges', []) }}
