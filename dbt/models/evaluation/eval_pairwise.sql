-- GROUND TRUTH (evaluation only). Pairwise precision, recall and F1 for each matcher, review stage and scope.
-- Computed on FINAL CLUSTERS, not just scored pairs: a pair counts as predicted when both records ended up in
-- the same cluster, so transitive errors (A~B, B~C) are counted. Scopes:
--   AUTO               clusters from deterministic + AUTO_MATCH (+ steward) edges
--   AUTO_PLUS_PROBABLE also merges PROBABLE pairs
-- Deterministic (source id) pairs are true by construction and sit in every cluster set. They inflate recall, so
-- `recall_nondeterministic` reports recall on the true pairs that needed matching.
with pred as (

    select a.matcher, a.stage, a.scope, a.match_record_id as record_a, b.match_record_id as record_b
    from {{ ref('idr_clusters') }} a
    join {{ ref('idr_clusters') }} b
        on a.matcher = b.matcher and a.stage = b.stage and a.scope = b.scope and a.cluster_id = b.cluster_id
       and a.match_record_id < b.match_record_id

),

truth as (select record_a, record_b, is_deterministic from {{ ref('eval_truth_pairs') }}),

totals as (

    select count(*) as true_pairs, count(*) filter (where not is_deterministic) as true_pairs_nondeterministic from truth

),

combos as (select distinct matcher, stage, scope from {{ ref('idr_clusters') }}),

stats as (

    select
        p.matcher, p.stage, p.scope,
        count(*)                                                            as predicted_pairs,
        count(t.record_a)                                                   as true_positives,
        count(*) filter (where t.record_a is null)                          as false_positives,
        count(t.record_a) filter (where not t.is_deterministic)             as true_positives_nondeterministic
    from pred p
    left join truth t on t.record_a = p.record_a and t.record_b = p.record_b
    group by 1, 2, 3

)

select
    c.matcher,
    c.stage,
    c.scope,
    t.true_pairs,
    coalesce(s.predicted_pairs, 0)                                          as predicted_pairs,
    coalesce(s.true_positives, 0)                                           as true_positives,
    coalesce(s.false_positives, 0)                                          as false_positives,
    t.true_pairs - coalesce(s.true_positives, 0)                            as false_negatives,
    round(coalesce(s.true_positives, 0) * 1.0 / nullif(s.predicted_pairs, 0), 5)           as precision,
    round(coalesce(s.true_positives, 0) * 1.0 / t.true_pairs, 5)                           as recall,
    round(2.0 * coalesce(s.true_positives, 0) / nullif(s.predicted_pairs + t.true_pairs, 0), 5) as f1,
    round(coalesce(s.true_positives_nondeterministic, 0) * 1.0 / nullif(t.true_pairs_nondeterministic, 0), 5)
                                                                            as recall_nondeterministic
from combos c
cross join totals t
left join stats s on s.matcher = c.matcher and s.stage = c.stage and s.scope = c.scope
