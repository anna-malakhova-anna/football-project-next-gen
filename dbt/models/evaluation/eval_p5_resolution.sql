{{ config(tags=['phase5']) }}
-- GROUND TRUTH (evaluation only). Phase 5 resolution graded on final clusters: pairwise precision and recall, and the false merges that matter most
-- (siblings and twins = same household, different child), at AUTO scope. Never used to tune the rules.
with recs as (

    select i.match_record_id, c.p5_person_id, t.true_person_id, t.household_id
    from {{ ref('p5_idr_input_records') }} i
    join {{ ref('p5_clusters') }} c using (match_record_id)
    join {{ source('ground_truth', 'p5_registration_truth') }} t
        on t.feed = i.source_system and t.source_record_id = i.source_record_id

),

pred as (

    select a.true_person_id as ta, b.true_person_id as tb, a.household_id as ha, b.household_id as hb
    from recs a join recs b on a.p5_person_id = b.p5_person_id and a.match_record_id < b.match_record_id

),

truth as (

    select count(*) as true_pairs
    from recs a join recs b on a.true_person_id = b.true_person_id and a.match_record_id < b.match_record_id

)

select
    (select count(*) from recs)                                             as records,
    (select count(distinct p5_person_id) from recs)                         as predicted_people,
    (select count(distinct true_person_id) from recs)                       as true_people,
    count(*)                                                                as predicted_pairs,
    count(*) filter (where ta = tb)                                         as true_positive_pairs,
    count(*) filter (where ta <> tb)                                        as false_merge_pairs,
    count(*) filter (where ta <> tb and ha = hb)                            as sibling_or_twin_false_merge_pairs,
    (select true_pairs from truth)                                          as true_pairs,
    round(count(*) filter (where ta = tb) / nullif(count(*), 0), 4)         as precision,
    round(count(*) filter (where ta = tb) / (select true_pairs from truth), 4) as recall
from pred
