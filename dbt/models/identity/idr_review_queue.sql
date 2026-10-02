-- What a data steward looks at, in priority order, with everything needed to decide side by side.
--   1. CLUSTER_CONFLICT  clusters flagged by idr_cluster_integrity (suggested action SPLIT_CLUSTER), largest first
--   2. PROBABLE_PAIR     PROBABLE pairs from the active matcher whose records are in different clusters and that no
--                        steward has decided yet, closest to T_auto first (CONFIRM_MATCH or CONFIRM_NON_MATCH)
-- Steward decisions go in the review_decisions seed (MATCH / NO_MATCH) and feed back into idr_match_edges.
{% set matcher = var('matcher') %}
with t as (select * from {{ ref('match_thresholds') }} where matcher_version = '{{ matcher }}'),

rec as (

    select
        match_record_id,
        json_object('source', source_system, 'first_name', first_name, 'last_name', last_name, 'dob', dob,
                    'birth_year', birth_year, 'sex', sex, 'email', contact_email, 'phone', contact_phone,
                    'postal_code', postal_code, 'organization', organization_id, 'season', season_key,
                    'division', canonical_division) as attrs
    from {{ ref('idr_input_records') }}

),

clusters as (

    select match_record_id, cluster_id
    from {{ ref('idr_clusters') }}
    where matcher = '{{ matcher }}' and stage = 'POST_REVIEW' and scope = 'AUTO'

),

decided as (

    select least(record_a, record_b) as record_a, greatest(record_a, record_b) as record_b from {{ ref('review_decisions') }}

),

conflicts as (

    select
        'CLUSTER_CONFLICT'                                                  as item_type,
        i.cluster_id,
        cast(null as varchar)                                               as record_a,
        cast(null as varchar)                                               as record_b,
        cast(null as double)                                                as match_probability,
        cast(null as varchar)                                               as override_applied,
        'SPLIT_CLUSTER'                                                     as suggested_action,
        i.integrity_issues,
        (select json_group_array(json_object('record', r.match_record_id, 'attrs', r.attrs))
         from rec r where list_contains(i.member_record_ids, r.match_record_id)) as members,
        cast(null as json)                                                  as feature_levels,
        cast(null as json)                                                  as weight_breakdown,
        'cluster of ' || i.cluster_size || ' records with: ' || array_to_string(i.integrity_issues, ', ') as reason,
        1                                                                   as priority_group,
        i.cluster_size * 100.0 + len(i.integrity_issues)                    as sort_key
    from {{ ref('idr_cluster_integrity') }} i

),

probable as (

    select
        'PROBABLE_PAIR'                                                     as item_type,
        cast(null as varchar)                                               as cluster_id,
        p.record_a,
        p.record_b,
        {% if matcher == 'rules' %}cast(null as double){% else %}p.match_probability{% endif %} as match_probability,
        {% if matcher == 'rules' %}cast(null as varchar){% else %}p.override_applied{% endif %} as override_applied,
        {% if matcher == 'rules' %}'CONFIRM_MATCH'{% else %}
        case when p.capped_at_probable then 'CONFIRM_NON_MATCH'
             when p.match_probability >= (t.t_review + t.t_auto) / 2 then 'CONFIRM_MATCH'
             else 'CONFIRM_NON_MATCH' end{% endif %}                        as suggested_action,
        cast(null as varchar[])                                             as integrity_issues,
        json_array(json_object('record', p.record_a, 'attrs', ra.attrs), json_object('record', p.record_b, 'attrs', rb.attrs)) as members,
        to_json(struct_pack(
            first_name := f.first_name_level, last_name := f.last_name_level, dob := f.dob_level, email := f.email_level,
            phone := f.phone_level, postal := f.postal_level, sex := f.sex_level, context := f.context_level)) as feature_levels,
        {% if matcher == 'rules' %}cast(null as json){% else %}p.weight_breakdown{% endif %} as weight_breakdown,
        p.reason                                                            as reason,
        2                                                                   as priority_group,
        {% if matcher == 'rules' %}0.0{% else %}p.match_probability{% endif %} as sort_key
    from (
        {% if matcher == 'rules' %}
        select record_a, record_b, reason, tier, false as capped_at_probable from {{ ref('idr_pair_scores_rules') }}
        {% else %}
        select * from {{ ref('idr_pair_scores_fs') }} where matcher = '{{ matcher }}'
        {% endif %}
    ) p
    cross join t
    join {{ ref('idr_pair_features') }} f on f.record_a = p.record_a and f.record_b = p.record_b
    join rec ra on ra.match_record_id = p.record_a
    join rec rb on rb.match_record_id = p.record_b
    join clusters ca on ca.match_record_id = p.record_a
    join clusters cb on cb.match_record_id = p.record_b
    left join decided d on d.record_a = p.record_a and d.record_b = p.record_b
    where p.tier = 'PROBABLE' and ca.cluster_id <> cb.cluster_id and d.record_a is null

),

combined as (

    select * from conflicts
    union all
    select * from probable

)

select
    row_number() over (order by priority_group, sort_key desc, coalesce(cluster_id, record_a))::integer as priority,
    md5(item_type || '|' || coalesce(cluster_id, record_a || '|' || record_b))                          as queue_item_id,
    '{{ matcher }}'                                                         as matcher,
    * exclude (priority_group, sort_key)
from combined
