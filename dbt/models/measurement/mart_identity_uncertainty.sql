-- How much could identity resolution alone move the participant count? LABEL-FREE: no ground truth, so this works in
-- production. Three bounds, each from the SAME connected_components macro over a different edge set (active matcher,
-- review stage POST_REVIEW):
--   low    deterministic + AUTO_MATCH + ALL PROBABLE pairs + steward MATCH   (every uncertain pair is really one person)
--   point  the production edges (what the pipeline reports)
--   high   production edges minus every edge inside a cluster with an open integrity issue (flagged clusters are
--          really several people)
-- Counted per participation year (GLOBAL) and per attributed country (COUNTRY, additive view). Data-trust columns sit
-- beside the bounds: open review items, participants touched by them, share resolved with high confidence.
{% set matcher = var('matcher') %}
with base as (

    select record_a as a, record_b as b, tier
    from {{ ref('idr_match_edges') }}
    where matcher = '{{ matcher }}' and stage = 'POST_REVIEW'

),

flagged as (select unnest(member_record_ids) as record from {{ ref('idr_cluster_integrity') }}),

edges as (

    select 'low' as bound, a, b from base
    union all
    select 'point', a, b from base where tier <> 'PROBABLE'
    union all
    select 'high', a, b from base where tier <> 'PROBABLE' and a not in (select record from flagged)

),

nodes as (

    select bounds.bound, r.match_record_id as node
    from (select unnest(['low', 'point', 'high']) as bound) bounds
    cross join {{ ref('idr_input_records') }} r

),

clusters as (select bound, node as match_record_id, cluster_id from {{ connected_components('nodes', 'edges', ['bound']) }}),

regs as (

    select
        c.bound, c.cluster_id, r.participation_year, r.country_code, r.registration_key,
        row_number() over (partition by c.bound, c.cluster_id, r.participation_year
                           order by r.term_order desc, r.registered_at desc nulls last, r.registration_key) as recency_rank
    from {{ ref('fct_registration') }} r
    join clusters c on c.match_record_id = r.registration_key
    where r.is_valid_registration

),

global_counts as (

    select participation_year, null as country_code, 'GLOBAL' as grain,
           count(distinct cluster_id) filter (where bound = 'low') as participants_low,
           count(distinct cluster_id) filter (where bound = 'point') as participants_point,
           count(distinct cluster_id) filter (where bound = 'high') as participants_high
    from regs group by participation_year

),

country_counts as (

    select participation_year, country_code, 'COUNTRY' as grain,
           count(*) filter (where bound = 'low') as participants_low,
           count(*) filter (where bound = 'point') as participants_point,
           count(*) filter (where bound = 'high') as participants_high
    from regs where recency_rank = 1 group by participation_year, country_code

),

counts as (select * from global_counts union all select * from country_counts),

-- participants behind every open review item
item_participants as (

    select q.queue_item_id, b.participant_id
    from {{ ref('idr_review_queue') }} q
    join {{ ref('bridge_registration_participant') }} b on b.match_record_id in (q.record_a, q.record_b) and b.registration_key = b.match_record_id
    where q.item_type = 'PROBABLE_PAIR'
    union
    select q.queue_item_id, b.participant_id
    from {{ ref('idr_review_queue') }} q
    join {{ ref('bridge_registration_participant') }} b on b.cluster_id = q.cluster_id and b.registration_key = b.match_record_id
    where q.item_type = 'CLUSTER_CONFLICT'

),

touched as (select distinct participant_id from item_participants),

year_participants as (

    select f.participation_year, f.attributed_country_code as country_code, f.participant_id,
           f.has_open_integrity_issue, t.participant_id is not null as in_review_item
    from {{ ref('fct_participant_year') }} f
    left join touched t using (participant_id)

),

trust as (

    select participation_year, null as country_code, 'GLOBAL' as grain,
           count(*) filter (where has_open_integrity_issue) as participants_open_integrity_issue,
           count(*) filter (where has_open_integrity_issue or in_review_item) as participants_touched_by_review,
           count(*) as point_participants
    from year_participants group by participation_year
    union all
    select participation_year, country_code, 'COUNTRY',
           count(*) filter (where has_open_integrity_issue),
           count(*) filter (where has_open_integrity_issue or in_review_item),
           count(*)
    from year_participants group by participation_year, country_code

),

items as (

    select y.participation_year, null as country_code, 'GLOBAL' as grain, count(distinct ip.queue_item_id) as open_review_items
    from item_participants ip join year_participants y using (participant_id) group by y.participation_year
    union all
    select y.participation_year, y.country_code, 'COUNTRY', count(distinct ip.queue_item_id)
    from item_participants ip join year_participants y using (participant_id) group by y.participation_year, y.country_code

)

select
    c.participation_year,
    c.grain,
    c.country_code,
    c.participants_low,
    c.participants_point,
    c.participants_high,
    round((c.participants_high - c.participants_low) * 1.0 / nullif(c.participants_point, 0), 5) as range_pct,
    coalesce(t.participants_open_integrity_issue, 0)                        as participants_open_integrity_issue,
    coalesce(t.participants_touched_by_review, 0)                           as participants_touched_by_review,
    round(1 - coalesce(t.participants_touched_by_review, 0) * 1.0 / nullif(t.point_participants, 0), 5) as pct_participants_high_confidence,
    coalesce(i.open_review_items, 0)                                        as open_review_items,
    '{{ var("methodology_version") }}'                                      as methodology_version
from counts c
left join trust t on t.participation_year = c.participation_year and t.grain = c.grain
                 and t.country_code is not distinct from c.country_code
left join items i on i.participation_year = c.participation_year and i.grain = c.grain
                 and i.country_code is not distinct from c.country_code
order by c.participation_year, c.grain desc, c.country_code
