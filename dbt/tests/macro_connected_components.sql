{{ config(tags=['phase2']) }}
-- connected_components on tiny handwritten graphs, in two independent partitions (g1, g2). Returns failing cases.
--   g1: a-b-c chain; d-e; f alone; g-h-i triangle plus a duplicate and a reversed edge
--   g2: the same node name 'a' alone: partitions must not leak into each other
with nodes(g, node) as (
    values ('g1','a'),('g1','b'),('g1','c'),('g1','d'),('g1','e'),('g1','f'),('g1','g'),('g1','h'),('g1','i'),('g2','a'),('g2','b')
),
edges(g, a, b) as (
    values ('g1','a','b'),('g1','b','c'),('g1','e','d'),('g1','g','h'),('g1','h','i'),('g1','i','g'),('g1','g','h'),('g1','h','g'),
           ('g2','b','b')
),
expected(g, node, cluster_id, cluster_size) as (
    values ('g1','a','a',3),('g1','b','a',3),('g1','c','a',3),('g1','d','d',2),('g1','e','d',2),('g1','f','f',1),
           ('g1','g','g',3),('g1','h','g',3),('g1','i','g',3),('g2','a','a',1),('g2','b','b',1)
),
actual as (select * from {{ connected_components('nodes', 'edges', ['g']) }})
select 'mismatch' as problem, e.g, e.node, e.cluster_id as expected_cluster, a.cluster_id as got_cluster, e.cluster_size as expected_size, a.cluster_size as got_size
from expected e left join actual a using (g, node)
where a.cluster_id is distinct from e.cluster_id or a.cluster_size is distinct from e.cluster_size
union all
select 'row_count', null, null, null, null, (select count(*) from expected), (select count(*) from actual)
where (select count(*) from expected) <> (select count(*) from actual)
