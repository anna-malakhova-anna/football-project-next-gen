-- Connected components of the match edges, computed in SQL with a recursive CTE.
-- Edges are treated as undirected; cluster_id = the smallest reachable match_record_id; a record with no
-- edges is its own cluster. Computed for every matcher x stage x scope:
--   scope AUTO               deterministic + AUTO_MATCH + steward edges   (what the pipeline uses)
--   scope AUTO_PLUS_PROBABLE adds PROBABLE edges                           (evaluation only)
-- The recursion is a set (UNION), so it terminates when no new record is reachable. A runaway merge cannot be
-- stopped inside the recursion, so it is caught right after the build by
-- tests/idr_clusters_within_plausible_size.sql (var idr_plausible_max_cluster_size).
with recursive

combos as (

    select distinct matcher, stage, scope
    from {{ ref('idr_match_edges') }}
    cross join (select unnest(['AUTO', 'AUTO_PLUS_PROBABLE']) as scope)

),

nodes as (

    select c.matcher, c.stage, c.scope, r.match_record_id
    from combos c cross join {{ ref('idr_input_records') }} r

),

scoped as (

    select e.matcher, e.stage, s.scope, e.record_a as a, e.record_b as b
    from {{ ref('idr_match_edges') }} e
    cross join (select unnest(['AUTO', 'AUTO_PLUS_PROBABLE']) as scope) s
    where s.scope = 'AUTO_PLUS_PROBABLE' or e.tier <> 'PROBABLE'

),

undirected as (

    select matcher, stage, scope, a as x, b as y from scoped
    union all
    select matcher, stage, scope, b, a from scoped

),

reach(matcher, stage, scope, src, node) as (

    select matcher, stage, scope, match_record_id, match_record_id from nodes
    union
    select r.matcher, r.stage, r.scope, r.src, u.y
    from reach r
    join undirected u on u.matcher = r.matcher and u.stage = r.stage and u.scope = r.scope and u.x = r.node

)

select
    matcher,
    stage,
    scope,
    src                                                                     as match_record_id,
    min(node)                                                               as cluster_id,
    count(*) over (partition by matcher, stage, scope, min(node))           as cluster_size
from reach
group by matcher, stage, scope, src
