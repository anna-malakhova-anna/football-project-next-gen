-- GROUND TRUTH (evaluation only). Cluster-level quality for each matcher, review stage and scope.
--   split rate        true people spread over more than one predicted cluster (under-merging: inflates counts)
--   merge rate        predicted clusters holding more than one true person (over-merging: undercounts)
--   sibling/twin merges  predicted clusters holding two true people from the same household. HEADLINE METRIC:
--                     a sibling false merge is a privacy incident (one child's consent applied to another)
--   participants      predicted vs true participant counts (Phase 3 leans on this)
with ct as (

    select c.matcher, c.stage, c.scope, c.cluster_id, c.match_record_id, t.true_person_id, t.household_id, t.twin_group_id
    from {{ ref('idr_clusters') }} c
    join {{ ref('eval_record_truth') }} t using (match_record_id)

),

per_person as (

    select matcher, stage, scope, true_person_id,
           count(distinct cluster_id) as clusters_spanned, count(*) as records
    from ct group by 1, 2, 3, 4

),

per_cluster as (

    select matcher, stage, scope, cluster_id,
           count(distinct true_person_id) as true_people, count(*) as records,
           -- two different true people from one household in this cluster (adults have no household)
           count(distinct true_person_id) filter (where household_id is not null) > count(distinct household_id)
                                                                            as has_household_merge,
           -- both members of a twin pair in this cluster
           count(distinct true_person_id) filter (where twin_group_id is not null) > count(distinct twin_group_id)
                                                                            as has_twin_merge
    from ct group by matcher, stage, scope, cluster_id

),

households as (

    select count(*) as multi_child_households
    from (select household_id from {{ ref('eval_record_truth') }} where household_id is not null
          group by household_id having count(distinct true_person_id) > 1)

)

select
    p.matcher, p.stage, p.scope,
    p.true_participants,
    c.predicted_participants,
    c.predicted_participants - p.true_participants                          as participant_count_error,
    round((c.predicted_participants - p.true_participants) * 100.0 / p.true_participants, 3) as participant_count_error_pct,
    p.people_split,
    round(p.people_split * 100.0 / p.people_with_2plus_records, 3)          as split_rate_pct,
    c.clusters_merged,
    round(c.clusters_merged * 100.0 / c.predicted_participants, 3)          as merge_rate_pct,
    c.sibling_or_twin_false_merges,
    c.twin_false_merges,
    h.multi_child_households,
    round(c.sibling_or_twin_false_merges * 100.0 / h.multi_child_households, 3) as sibling_twin_merge_pct_of_households
from (
    select matcher, stage, scope, count(*) as true_participants,
           count(*) filter (where clusters_spanned > 1) as people_split,
           count(*) filter (where records > 1) as people_with_2plus_records
    from per_person group by 1, 2, 3
) p
join (
    select matcher, stage, scope, count(*) as predicted_participants,
           count(*) filter (where true_people > 1) as clusters_merged,
           count(*) filter (where has_household_merge) as sibling_or_twin_false_merges,
           count(*) filter (where has_twin_merge) as twin_false_merges
    from per_cluster group by 1, 2, 3
) c using (matcher, stage, scope)
cross join households h
