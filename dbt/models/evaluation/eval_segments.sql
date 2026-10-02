-- GROUND TRUTH (evaluation only). Pairwise recall (and precision where it is defined) by segment, for each matcher,
-- review stage and scope, measured on final clusters.
--   source_pair   US-US, US-CA (cross-border), CA-CA, INTL-INTL, ...: recall of true pairs and precision of predicted pairs
--   defect        recall of true pairs where either record carries the injected defect (from the generator's manifest):
--                 nickname, typo, accents stripped, day/month swap, email change, birth year off by one, name order,
--                 family-name change, plus `none` (no matching-relevant defect)
--   situation     same org + season (near-duplicates), same season in different orgs (multi-league play)
with rec as (

    select match_record_id, source_system, source_record_id, season_key, organization_id from {{ ref('idr_input_records') }}

),

true_pairs as (

    select
        t.record_a, t.record_b, t.is_deterministic,
        {{ source_pair('a.source_system', 'b.source_system') }} as source_pair,
        case when a.season_key = b.season_key and a.organization_id = b.organization_id then 'same_org_same_season'
             when a.season_key = b.season_key then 'multi_league_same_season' end as situation,
        a.source_system as a_system, a.source_record_id as a_rid, b.source_system as b_system, b.source_record_id as b_rid
    from {{ ref('eval_truth_pairs') }} t
    join rec a on a.match_record_id = t.record_a
    join rec b on b.match_record_id = t.record_b

),

relevant_defects as (

    select unnest(['name_typo_reregistration', 'nickname_reregistration', 'accents_stripped', 'dob_day_month_swapped',
                   'guardian_email_changed_between_seasons', 'birth_year_off_by_one', 'name_order_inverted',
                   'family_name_change', 'impossible_dob']) as defect_id

),

pair_defects as (

    -- every (pair, defect) where either record carries a matching-relevant injected defect
    select p.record_a, p.record_b, m.defect_id
    from true_pairs p
    join {{ source('ground_truth', 'defect_manifest') }} m
        on (m.source_system = p.a_system and m.source_record_id = p.a_rid) or (m.source_system = p.b_system and m.source_record_id = p.b_rid)
    join relevant_defects d on d.defect_id = m.defect_id
    group by 1, 2, 3

),

pair_segments as (

    select record_a, record_b, 'source_pair' as segment_type, source_pair as segment from true_pairs
    union all
    select record_a, record_b, 'situation', situation from true_pairs where situation is not null
    union all
    select record_a, record_b, 'defect', defect_id from pair_defects
    union all
    select p.record_a, p.record_b, 'defect', 'none'
    from true_pairs p left join pair_defects d using (record_a, record_b) where d.record_a is null

),

in_cluster as (

    -- true pairs that ended up in the same predicted cluster, per matcher / stage / scope
    select c.matcher, c.stage, c.scope, t.record_a, t.record_b
    from {{ ref('eval_truth_pairs') }} t
    join {{ ref('idr_clusters') }} c on c.match_record_id = t.record_a
    join {{ ref('idr_clusters') }} d
        on d.match_record_id = t.record_b and d.matcher = c.matcher and d.stage = c.stage and d.scope = c.scope and d.cluster_id = c.cluster_id

),

combos as (select distinct matcher, stage, scope from {{ ref('idr_clusters') }}),

recall as (

    select
        co.matcher, co.stage, co.scope, s.segment_type, s.segment,
        count(*)                                                            as true_pairs,
        count(ic.record_a)                                                  as true_positives
    from combos co
    cross join pair_segments s
    left join in_cluster ic
        on ic.matcher = co.matcher and ic.stage = co.stage and ic.scope = co.scope
       and ic.record_a = s.record_a and ic.record_b = s.record_b
    group by 1, 2, 3, 4, 5

),

pred as (

    select a.matcher, a.stage, a.scope, a.match_record_id as record_a, b.match_record_id as record_b
    from {{ ref('idr_clusters') }} a
    join {{ ref('idr_clusters') }} b
        on a.matcher = b.matcher and a.stage = b.stage and a.scope = b.scope and a.cluster_id = b.cluster_id
       and a.match_record_id < b.match_record_id

),

precision_by_source_pair as (

    select
        p.matcher, p.stage, p.scope,
        {{ source_pair('ra.source_system', 'rb.source_system') }} as segment,
        count(*)                                                            as predicted_pairs,
        count(t.record_a)                                                   as correct_pairs
    from pred p
    join rec ra on ra.match_record_id = p.record_a
    join rec rb on rb.match_record_id = p.record_b
    left join {{ ref('eval_truth_pairs') }} t on t.record_a = p.record_a and t.record_b = p.record_b
    group by 1, 2, 3, 4

)

select
    r.matcher, r.stage, r.scope, r.segment_type, r.segment,
    r.true_pairs,
    r.true_positives,
    round(r.true_positives * 1.0 / r.true_pairs, 5)                         as recall,
    p.predicted_pairs,
    round(p.correct_pairs * 1.0 / nullif(p.predicted_pairs, 0), 5)          as precision
from recall r
left join precision_by_source_pair p
    on r.segment_type = 'source_pair' and p.matcher = r.matcher and p.stage = r.stage and p.scope = r.scope and p.segment = r.segment
order by r.matcher, r.stage, r.scope, r.segment_type, r.segment
