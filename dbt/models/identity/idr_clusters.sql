-- Connected components of the match edges (macro connected_components, a recursive CTE), for every
-- matcher x stage x scope. Edges are undirected; cluster_id = the smallest reachable match_record_id; a record with no
-- edges is its own cluster. Scopes:
--   AUTO               deterministic + AUTO_MATCH + steward edges   (what the pipeline uses)
--   AUTO_PLUS_PROBABLE adds PROBABLE edges                           (evaluation, and the "low" identity bound)
-- A runaway merge cannot be stopped inside the recursion, so tests/idr_clusters_within_plausible_size.sql catches it
-- right after the build (var idr_plausible_max_cluster_size).
with combos as (

    select distinct matcher, stage, scope
    from {{ ref('idr_match_edges') }}
    cross join (select unnest(['AUTO', 'AUTO_PLUS_PROBABLE']) as scope)

),

nodes as (

    select c.matcher, c.stage, c.scope, r.match_record_id as node
    from combos c cross join {{ ref('idr_input_records') }} r

),

edges as (

    select e.matcher, e.stage, s.scope, e.record_a as a, e.record_b as b
    from {{ ref('idr_match_edges') }} e
    cross join (select unnest(['AUTO', 'AUTO_PLUS_PROBABLE']) as scope) s
    where s.scope = 'AUTO_PLUS_PROBABLE' or e.tier <> 'PROBABLE'

)

select matcher, stage, scope, node as match_record_id, cluster_id, cluster_size
from {{ connected_components('nodes', 'edges', ['matcher', 'stage', 'scope']) }}
