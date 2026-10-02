{#-
  connected_components(nodes, edges, keys)  -> a subquery of (keys..., node, cluster_id, cluster_size)
  Connected components of an undirected graph, in SQL, with a recursive CTE. Callable against ANY edge set, which is
  how identity uncertainty computes its low / point / high counts (Phase 3).

    nodes  a relation or CTE name with columns (<keys>, node): every node in each graph, so isolated nodes
           become singleton clusters
    edges  a relation or CTE name with columns (<keys>, a, b): the edges, treated as undirected
    keys   list of column names that partition independent graphs (for example ['matcher', 'stage', 'scope']),
           or [] for a single graph

  cluster_id is the smallest reachable node (string order). The recursion is a set (UNION), so it terminates once no
  new node is reachable; a runaway merge is caught by a size test after the build, not inside the recursion.
  Snowflake: WITH RECURSIVE with UNION behaves the same way.
-#}
{% macro connected_components(nodes, edges, keys=[]) -%}
{%- set k = keys | join(', ') -%}
{%- set kc = (k ~ ', ') if keys else '' -%}
(
    with recursive
    undirected as (
        select {{ kc }}a as x, b as y from {{ edges }}
        union all
        select {{ kc }}b, a from {{ edges }}
    ),
    reach({{ kc }}src, node) as (
        select {{ kc }}node, node from {{ nodes }}
        union
        select {% for key in keys %}r.{{ key }}, {% endfor %}r.src, u.y
        from reach r
        join undirected u on {% for key in keys %}u.{{ key }} = r.{{ key }} and {% endfor %}u.x = r.node
    )
    select
        {{ kc }}src as node,
        min(node) as cluster_id,
        count(*) over (partition by {{ kc }}min(node)) as cluster_size
    from reach
    group by {{ kc }}src
)
{%- endmacro %}
