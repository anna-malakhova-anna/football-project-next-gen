-- depends_on: {{ ref('dq_rule_registry') }}
-- depends_on: {{ ref('dq_severity_weights') }}
-- depends_on: {{ ref('p5_params') }}
{# DP1. The fix list: one row per organization x season x issue, ranked by RECORDS AFFECTED. It reads only what DP1 measures (dq_rule_measures, the organization base), so it needs no resolved person:
   the checks that do (one record per child per season, records that agree) are not in it. The participant-weighted ranking, which does need DP2's persons, is DP4's dq_fix_ranking. #}
-- The top five overall plus the top three of the organization's own (non-systemic) issues, ranked by records_affected, then the rule's severity weight, then rule_id. What an operator is asked to do is the registry's
-- plain-language fix_guidance, with the records affected (a count only, never a record id).
--   records_affected  the registrations of this organization-season that fail the rule. For the no-file rule (DQ-TIME-ORG-REPORTED), which has no registrations of its own, it is an ESTIMATE of
--                     what the dark season is missing, stated in records_basis: EXPECTED_FROM_OTHER_SEASONS (the average the organization sent in the seasons it did report), else
--                     EXPECTED_FROM_PEERS (the median of the reporting organizations of the same source and season), else NOT_ESTIMABLE (NULL: nothing to estimate from). Never 0 by default.
--                     The no-file issue always ranks FIRST for a dark organization-season: it is the reason nothing else can be measured.
--   is_systemic       the rule is breached by at least systemic_share (p5_params, 80%) of the source's organizations that season: a platform or process problem, not this organization's.
--                     rank_in_scope ranks the organization's own issues without it, so the list stays informative when one platform gap tops every list.
-- A rule appears only if the organization breaches the registry threshold of at least one purpose it serves. INFO rules never appear.
with registry as (select * from {{ ref('dq_rule_registry') }}),

unioned as (select rule_id, source_system, org_id, season_year, n_evaluated, n_pass, pass_rate from {{ ref('dq_rule_measures') }}),

{{ dq_expanded_cte() }},

rule_results as ({{ dq_results_select() }}),

results as (

    select r.source_system, r.org_id, r.season_year, r.rule_id, r.purpose,
           r.n_evaluated - r.n_pass as failing, r.pass, r.observed_value, g.dimension, g.severity, g.fix_guidance, g.owner_role, g.grain
    from rule_results r join {{ ref('dq_rule_registry') }} g using (rule_id)
    where r.org_id is not null and g.severity <> 'INFO' and r.purpose is not null

),

breached as (

    select source_system, org_id, season_year, rule_id, any_value(dimension) as dimension, any_value(severity) as severity, any_value(fix_guidance) as fix_guidance,
           any_value(owner_role) as owner_role, any_value(grain) as rule_grain, max(failing) as records_affected,
           list(distinct purpose order by purpose) as purposes_breached
    from results where pass is false group by 1, 2, 3, 4

),

expected as (

    -- what a dark season is missing: the organization's mean registration count in the seasons it did report
    select source_system, org_id, avg(n_records) filter (where reported) as mean_records from {{ ref('dq_org_season_base') }} group by 1, 2

),

peers as (

    -- fallback for an organization that never reported: the median of the reporting organizations of the same source and season
    select source_system, season_year, median(n_records) filter (where reported) as peer_median from {{ ref('dq_org_season_base') }} group by 1, 2

),

issues as (

    select
        b.source_system, b.org_id, b.season_year, b.rule_id, b.dimension, b.severity, b.purposes_breached, b.fix_guidance, b.owner_role,
        case when b.rule_grain = 'ORG_SEASON' then round(coalesce(e.mean_records, p.peer_median))::bigint else b.records_affected end as records_affected,
        case when b.rule_grain <> 'ORG_SEASON' then 'COUNTED'
             when e.mean_records is not null then 'EXPECTED_FROM_OTHER_SEASONS'
             when p.peer_median is not null then 'EXPECTED_FROM_PEERS'
             else 'NOT_ESTIMABLE' end                                                                                      as records_basis
    from breached b
    left join expected e on e.source_system = b.source_system and e.org_id = b.org_id
    left join peers p on p.source_system = b.source_system and p.season_year = b.season_year

),

breadth as (

    select source_system, season_year, rule_id,
           count(distinct org_id) filter (where pass is false)::double / nullif(count(distinct org_id), 0) as share_of_orgs_breaching
    from results group by 1, 2, 3

),

ranked as (

    select issues.*,
           coalesce(br.share_of_orgs_breaching >= (select value::double from {{ ref('p5_params') }} where param = 'systemic_share'), false) as is_systemic,
           row_number() over (partition by source_system, org_id, season_year
                              order by (rule_id = 'DQ-TIME-ORG-REPORTED') desc, records_affected desc nulls last, (select weight from {{ ref('dq_severity_weights') }} w where w.severity = issues.severity) desc, rule_id) as fix_rank
    from issues left join breadth br using (source_system, season_year, rule_id)

),

scoped as (

    select *, row_number() over (partition by source_system, org_id, season_year, is_systemic order by fix_rank) as rank_in_scope from ranked

)

select
    r.source_system, r.org_id, o.org_name, r.season_year, r.fix_rank, r.is_systemic, r.rank_in_scope, r.rule_id, r.dimension, r.severity, r.purposes_breached,
    r.records_affected, r.records_basis, r.fix_guidance, r.owner_role
from scoped r
join {{ ref('dq_org_season_base') }} o using (source_system, org_id, season_year)
where r.fix_rank <= 5 or (not r.is_systemic and r.rank_in_scope <= 3)
