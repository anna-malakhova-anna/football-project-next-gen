-- EVERY registration in int_registrations_unioned (exact duplicates included) maps to exactly one participant.
-- This is the table Phase 3 counts from. Cluster = the active matcher's final clusters (var matcher, stage
-- POST_REVIEW, scope AUTO). link_method says how the record joined its participant:
--   SINGLETON          no edges; the participant has this one record
--   SOURCE_ID          linked by a stable source id (member_uuid, federation Player ID)
--   STEWARD            a steward decision
--   FS / RULES         matched by the active matcher; match_probability is the weakest FS edge into the record
--   EXACT_DUPLICATE    a collapsed exact copy of the surviving record
{% set matcher = var('matcher') %}
with clusters as (

    select match_record_id, cluster_id, cluster_size
    from {{ ref('idr_clusters') }}
    where matcher = '{{ matcher }}' and stage = 'POST_REVIEW' and scope = 'AUTO'

),

participants as (

    select
        c.cluster_id,
        {{ participant_id('min(r.source_record_id)') }}                     as participant_id
    from clusters c
    join {{ ref('idr_input_records') }} r on r.match_record_id = c.match_record_id
    group by c.cluster_id

),

edges as (

    select record_a as record, link_method, match_probability from {{ ref('idr_match_edges') }}
    where matcher = '{{ matcher }}' and stage = 'POST_REVIEW' and tier <> 'PROBABLE'
    union all
    select record_b, link_method, match_probability from {{ ref('idr_match_edges') }}
    where matcher = '{{ matcher }}' and stage = 'POST_REVIEW' and tier <> 'PROBABLE'

),

per_record as (

    select
        record,
        list_sort(list_distinct(list(link_method)))                         as link_methods,
        min(match_probability)                                              as match_probability
    from edges group by record

),

survivors as (

    select
        r.match_record_id,
        c.cluster_id,
        c.cluster_size,
        p.participant_id,
        coalesce(e.link_methods, []::varchar[])                             as link_methods,
        e.match_probability,
        case
            when e.link_methods is null then 'SINGLETON'
            when list_contains(e.link_methods, 'STEWARD') then 'STEWARD'
            when list_contains(e.link_methods, 'SOURCE_ID') then 'SOURCE_ID'
            else e.link_methods[1]
        end                                                                 as link_method,
        unnest(r.member_registration_keys)                                  as registration_key
    from {{ ref('idr_input_records') }} r
    join clusters c on c.match_record_id = r.match_record_id
    join participants p on p.cluster_id = c.cluster_id
    left join per_record e on e.record = r.match_record_id

)

select
    registration_key,
    participant_id,
    match_record_id,
    cluster_id,
    cluster_size,
    case when registration_key = match_record_id then link_method else 'EXACT_DUPLICATE' end as link_method,
    case when registration_key = match_record_id then match_probability end                  as match_probability,
    link_methods
from survivors
