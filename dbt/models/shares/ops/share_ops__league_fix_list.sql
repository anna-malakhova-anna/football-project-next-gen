{{ config(tags=['phase6']) }}
-- OPS share, DP1 output port (Phase 6): the fix list of each LEAGUE per season, in plain words: what to fix, why, and roughly how many players or families it affects. Per organization; counts only, never a
-- record id. A count below the small-cell size is hidden. For the organization-reported rule the count is an estimate of what a dark season is missing (basis EXPECTED_FROM_OTHER_SEASONS).
{% set k = privacy_param('k_min') %}
select
    f.season_year, f.source_system, f.org_id, f.org_name, f.rank_in_scope as fix_rank, f.is_systemic,
    f.rule_id, r.plain_label as problem_plain, r.plain_action as what_to_do_plain,
    f.impact_unit,
    case when f.impact_estimate >= {{ k }} then cast(round(f.impact_estimate, -1) as bigint) end as estimated_impact,
    f.impact_basis,
    case when f.impact_estimate >= {{ k }} then 'NONE' else 'PRIMARY' end   as suppressed
from {{ ref('dq_fix_list') }} f join {{ ref('dq_rule_registry') }} r on r.rule_id = f.rule_id
where f.rank_in_scope is not null
order by f.season_year, f.source_system, f.org_id, f.rank_in_scope
