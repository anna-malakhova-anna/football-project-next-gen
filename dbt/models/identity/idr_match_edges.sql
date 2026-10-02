-- The links that merge records into people, for every matcher and review stage. Union of:
--   * deterministic links (source ids)
--   * AUTO_MATCH and PROBABLE pairs from each matcher (rules, fs_naive, fs) (PROBABLE edges are only used by the "AUTO + PROBABLE"
--     evaluation scope; the pipeline itself clusters on AUTO scope)
--   * steward MATCH decisions (stage POST_REVIEW only), minus steward NO_MATCH decisions
-- Each edge keeps its link_method (SOURCE_ID, RULES, FS, STEWARD) and the reason it was made.
-- `matcher` and `stage` columns let the evaluation compare matchers and before/after steward review;
-- the marts read only matcher = var('matcher') and stage = POST_REVIEW.
with matchers as (

    select 'rules' as matcher
    union all
    select 'fs_naive'
    union all
    select 'fs'

),

stages as (select unnest(['PRE_REVIEW', 'POST_REVIEW']) as stage),

deterministic as (

    select m.matcher, s.stage, d.record_a, d.record_b, d.link_method, d.link_tier as tier,
           d.link_reason as reason, cast(null as double) as match_probability
    from {{ ref('idr_deterministic_links') }} d cross join matchers m cross join stages s

),

scored as (

    select r.matcher, s.stage, r.record_a, r.record_b, 'RULES' as link_method, r.tier,
           r.rule_id || ': ' || r.reason as reason, cast(null as double) as match_probability
    from {{ ref('idr_pair_scores_rules') }} r cross join stages s
    where r.tier in ('AUTO_MATCH', 'PROBABLE')

),

fs_scored as (

    select f.matcher, s.stage, f.record_a, f.record_b, 'FS' as link_method, f.tier,
           f.reason || coalesce(' [override: ' || f.override_applied || ']', '') as reason, f.match_probability
    from {{ ref('idr_pair_scores_fs') }} f cross join stages s
    where f.tier in ('AUTO_MATCH', 'PROBABLE')

),

steward as (

    select m.matcher, 'POST_REVIEW' as stage, least(d.record_a, d.record_b) as record_a, greatest(d.record_a, d.record_b) as record_b,
           'STEWARD' as link_method, 'STEWARD' as tier,
           'steward decision by ' || coalesce(d.decided_by, 'unknown') as reason, cast(null as double) as match_probability
    from {{ ref('review_decisions') }} d cross join matchers m
    where d.decision = 'MATCH'

),

overrides as (

    select least(record_a, record_b) as record_a, greatest(record_a, record_b) as record_b
    from {{ ref('review_decisions') }} where decision = 'NO_MATCH'

),

combined as (

    select * from deterministic
    union all select * from scored
    union all select * from fs_scored
    union all select * from steward

)

select c.*
from combined c
left join overrides o
    on c.stage = 'POST_REVIEW' and o.record_a = c.record_a and o.record_b = c.record_b
where o.record_a is null
