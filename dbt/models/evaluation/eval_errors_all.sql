-- GROUND TRUTH (evaluation only). Every false positive (predicted same cluster, different true people) and false
-- negative (true pair split across clusters) at the AUTO scope, per matcher and review stage, NOT capped: the counts in
-- eval_error_categories read this model; eval_errors keeps the first 200 of each kind for the error analysis.
-- One row per record pair: a cluster holding a records of one child and b of another is a*b false-positive pairs.
-- likely_cause is assigned by SQL rules, in this order:
--   false positive   TWIN, SIBLING (same household), TRANSITIVE_CHAIN (merged only through a third record), OTHER
--   false negative   NAME_CHANGE, BLOCKING_MISS (never a candidate), GUARD_OVERRIDE (a hard guard ruled it out),
--                    BELOW_THRESHOLD (scored, but under T_auto), OTHER
-- This feeds the error analysis in ADR-003 and docs/identity_resolution.md.
with scope_clusters as (

    select matcher, stage, match_record_id, cluster_id from {{ ref('idr_clusters') }} where scope = 'AUTO'

),

pred as (

    select a.matcher, a.stage, a.match_record_id as record_a, b.match_record_id as record_b
    from scope_clusters a join scope_clusters b
        on a.matcher = b.matcher and a.stage = b.stage and a.cluster_id = b.cluster_id and a.match_record_id < b.match_record_id

),

scores as (

    select 'rules' as matcher, record_a, record_b, tier, cast(null as double) as match_probability,
           case when rule_id = 'R4' then 'R4_SIBLING_TWIN_GUARD' end as override_applied
    from {{ ref('idr_pair_scores_rules') }}
    union all
    select matcher, record_a, record_b, tier, match_probability, override_applied from {{ ref('idr_pair_scores_fs') }}

),

direct_edges as (

    select distinct matcher, stage, record_a, record_b from {{ ref('idr_match_edges') }} where tier <> 'PROBABLE'

),

fp as (

    select p.matcher, p.stage, 'FALSE_POSITIVE' as error_type, p.record_a, p.record_b
    from pred p
    left join {{ ref('eval_truth_pairs') }} t on t.record_a = p.record_a and t.record_b = p.record_b
    where t.record_a is null

),

fn as (

    select c.matcher, c.stage, 'FALSE_NEGATIVE' as error_type, t.record_a, t.record_b
    from (select distinct matcher, stage from scope_clusters) c
    cross join {{ ref('eval_truth_pairs') }} t
    join scope_clusters ca on ca.matcher = c.matcher and ca.stage = c.stage and ca.match_record_id = t.record_a
    join scope_clusters cb on cb.matcher = c.matcher and cb.stage = c.stage and cb.match_record_id = t.record_b
    where ca.cluster_id <> cb.cluster_id

),

errors as (select * from fp union all select * from fn),

described as (

    select
        e.*,
        ta.true_person_id as true_person_a,
        tb.true_person_id as true_person_b,
        ta.household_id = tb.household_id as same_household,
        ta.twin_group_id is not null and ta.twin_group_id = tb.twin_group_id as same_twin_group,
        coalesce(pa.name_change_season is not null or pb.name_change_season is not null, false) as involves_name_change,
        cp.record_a is not null as is_candidate,
        d.is_deterministic as deterministic_pair,
        s.tier, s.match_probability, s.override_applied,
        f.source_pair, f.first_name_level, f.last_name_level, f.dob_level, f.email_level, f.phone_level, f.context_level,
        de.record_a is not null as directly_linked
    from errors e
    join {{ ref('eval_record_truth') }} ta on ta.match_record_id = e.record_a
    join {{ ref('eval_record_truth') }} tb on tb.match_record_id = e.record_b
    left join {{ source('ground_truth', 'person_registry') }} pa on pa.true_person_id = ta.true_person_id
    left join {{ source('ground_truth', 'person_registry') }} pb on pb.true_person_id = tb.true_person_id
    left join {{ ref('idr_candidate_pairs') }} cp on cp.record_a = e.record_a and cp.record_b = e.record_b
    left join {{ ref('eval_truth_pairs') }} d on d.record_a = e.record_a and d.record_b = e.record_b
    left join scores s on s.matcher = e.matcher and s.record_a = e.record_a and s.record_b = e.record_b
    left join {{ ref('idr_pair_features') }} f on f.record_a = e.record_a and f.record_b = e.record_b
    left join direct_edges de on de.matcher = e.matcher and de.stage = e.stage and de.record_a = e.record_a and de.record_b = e.record_b

),

caused as (

    select
        *,
        case
            when error_type = 'FALSE_POSITIVE' then
                case when same_twin_group then 'TWIN'
                     when same_household then 'SIBLING'
                     when not directly_linked then 'TRANSITIVE_CHAIN'
                     else 'OTHER' end
            else
                case when involves_name_change then 'NAME_CHANGE'
                     when not is_candidate and not coalesce(deterministic_pair, false) then 'BLOCKING_MISS'
                     when override_applied is not null and tier = 'NON_MATCH' then 'GUARD_OVERRIDE'
                     when tier in ('PROBABLE', 'NON_MATCH') then 'BELOW_THRESHOLD'
                     else 'OTHER' end
        end as likely_cause
    from described

)

select
    matcher, stage, error_type, likely_cause,
    record_a, record_b, true_person_a, true_person_b, source_pair,
    tier, match_probability, override_applied,
    first_name_level, last_name_level, dob_level, email_level, phone_level, context_level
from caused
