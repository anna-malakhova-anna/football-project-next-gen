-- GROUND TRUTH (evaluation only). Precision and recall of the Fellegi-Sunter matchers across probability thresholds,
-- measured on FINAL clusters (deterministic links + every scored pair at or above the threshold that is not forced
-- to NON_MATCH or capped at PROBABLE). This is the table that justifies T_auto and T_review (ADR-003).
--   review_items_if_auto    pairs that would sit in the review queue if this threshold were T_auto, with T_review as seeded
--   review_items_if_review  pairs that would sit in the review queue if this threshold were T_review, with T_auto as seeded
-- Exported to CSV by `make eval` for a chart in Phase 4.
{% set grid = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.925, 0.95, 0.96, 0.97, 0.98, 0.985, 0.99, 0.995, 0.997, 0.998, 0.999] %}
with grid(threshold) as (select * from (values {% for t in grid %}({{ t }}){{ ',' if not loop.last }}{% endfor %}) as g(threshold)),

matchers as (select distinct matcher from {{ ref('idr_pair_scores_fs') }}),

combos as (select m.matcher, g.threshold from matchers m cross join grid g),

scored as (select * from {{ ref('idr_pair_scores_fs') }}),

edges as (

    select c.matcher, c.threshold, s.record_a as a, s.record_b as b
    from combos c join scored s on s.matcher = c.matcher
    where s.match_probability >= c.threshold and not s.forced_non_match and not s.capped_at_probable
    union all
    select c.matcher, c.threshold, d.record_a, d.record_b
    from combos c cross join {{ ref('idr_deterministic_links') }} d

),

nodes as (

    select c.matcher, c.threshold, r.match_record_id as node from combos c cross join {{ ref('idr_input_records') }} r

),

cluster as (

    select matcher, threshold, node as match_record_id, cluster_id
    from {{ connected_components('nodes', 'edges', ['matcher', 'threshold']) }}

),

pred as (

    select a.matcher, a.threshold, a.match_record_id as record_a, b.match_record_id as record_b
    from cluster a join cluster b
        on a.matcher = b.matcher and a.threshold = b.threshold and a.cluster_id = b.cluster_id and a.match_record_id < b.match_record_id

),

truth as (select record_a, record_b from {{ ref('eval_truth_pairs') }}),

pairwise as (

    select p.matcher, p.threshold, count(*) as predicted_pairs, count(t.record_a) as true_positives
    from pred p left join truth t on t.record_a = p.record_a and t.record_b = p.record_b
    group by 1, 2

),

by_cluster as (

    select c.matcher, c.threshold, c.cluster_id,
           count(distinct t.true_person_id) as true_people,
           count(distinct t.true_person_id) filter (where t.household_id is not null) > count(distinct t.household_id) as household_merge
    from cluster c join {{ ref('eval_record_truth') }} t using (match_record_id)
    group by 1, 2, 3

),

cluster_stats as (

    select matcher, threshold, count(*) as predicted_participants,
           count(*) filter (where true_people > 1) as clusters_merged,
           count(*) filter (where household_merge) as sibling_or_twin_false_merges
    from by_cluster group by 1, 2

),

queue as (

    select
        c.matcher, c.threshold,
        count(*) filter (where s.match_probability >= th.t_review and not s.forced_non_match
                         and (s.match_probability < c.threshold or s.capped_at_probable)) as review_items_if_auto,
        count(*) filter (where s.match_probability >= c.threshold and not s.forced_non_match
                         and (s.match_probability < th.t_auto or s.capped_at_probable)) as review_items_if_review
    from combos c
    join scored s on s.matcher = c.matcher
    join {{ ref('match_thresholds') }} th on th.matcher_version = c.matcher
    group by 1, 2

),

true_total as (select count(*) as true_pairs from truth)

select
    p.matcher,
    p.threshold,
    t.true_pairs,
    p.predicted_pairs,
    p.true_positives,
    p.predicted_pairs - p.true_positives                                    as false_positives,
    t.true_pairs - p.true_positives                                         as false_negatives,
    round(p.true_positives * 1.0 / p.predicted_pairs, 5)                    as precision,
    round(p.true_positives * 1.0 / t.true_pairs, 5)                         as recall,
    round(2.0 * p.true_positives / (p.predicted_pairs + t.true_pairs), 5)   as f1,
    cs.predicted_participants,
    cs.clusters_merged,
    cs.sibling_or_twin_false_merges,
    q.review_items_if_auto,
    q.review_items_if_review
from pairwise p
cross join true_total t
join cluster_stats cs using (matcher, threshold)
join queue q using (matcher, threshold)
order by p.matcher, p.threshold
