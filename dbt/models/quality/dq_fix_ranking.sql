-- depends_on: {{ ref('dq_rule_registry') }}
-- depends_on: {{ ref('dq_severity_weights') }}
-- depends_on: {{ ref('p5_params') }}
-- DP4. The fix RANKING weighted by participants: one row per organization x season x issue (DP1's dq_fix_list ranks the same issues by records affected, with no identity): the top five overall plus the top three of the organization's own (non-systemic) issues, ranked by IMPACT (mart_dq_impact), not by raw count. What an operator is asked to do, in the registry's own
-- plain-language fix_guidance, with the records affected (a count only, never a record id).
--   records_affected  the records of this organization-season that fail the rule. For the organization-reported rule, which has no records of its own, it is the number of records the
--                     organization sent in its other seasons on average (basis EXPECTED_FROM_OTHER_SEASONS): what a dark season is missing, estimated without the answer key.
--   impact_estimate   records_affected x the rule's yield (impact units per failing record, from mart_dq_impact, pooled over seasons, for the same population and the purposes the organization
--                     breaches). A rule whose failures remove participants outranks a cosmetic one that fails more often. A rule with no measured yield ranks last (basis NOT_MEASURED).
--   is_systemic       the rule is breached by at least systemic_share (p5_params, 80%) of the source's organizations that season: a platform or process problem (a form that records no consent
--                     timestamp), not this organization's. fix_rank_org_specific ranks the organization's own issues without it, so the list stays informative when one platform gap tops every list.
-- A rule appears only if the organization breaches the registry threshold of at least one purpose it serves. INFO rules never appear.
with results as (

    select r.source_system, r.org_id, r.season_year, r.rule_id, r.purpose,
           r.n_evaluated - r.n_pass as failing, r.pass, r.observed_value, g.dimension, g.severity, g.fix_guidance, g.owner_role, g.grain
    from {{ ref('dq_rule_results') }} r join {{ ref('dq_rule_registry') }} g using (rule_id)
    where r.org_id is not null and g.severity <> 'INFO' and r.purpose is not null

),

breached as (

    select source_system, org_id, season_year, rule_id, any_value(dimension) as dimension, any_value(severity) as severity, any_value(fix_guidance) as fix_guidance,
           any_value(owner_role) as owner_role, any_value(grain) as rule_grain, max(failing) as records_affected,
           list(distinct purpose order by purpose) as purposes_breached
    from results where pass is false group by 1, 2, 3, 4

),

yield as (

    select rule_id, population, purpose, sum(impact_units)::double / nullif(sum(records_failing), 0) as per_record, any_value(unit) as unit
    from {{ ref('mart_dq_impact') }} group by all

),

best_yield as (

    select b.source_system, b.org_id, b.season_year, b.rule_id, max(y.per_record) as per_record, any_value(y.unit order by y.per_record desc) as unit
    from breached b
    cross join unnest(b.purposes_breached) as p(purpose)
    join yield y on y.rule_id = b.rule_id and y.purpose = p.purpose
                and y.population = case when b.source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') then 'MODELLED' else 'CHANNEL_FEED' end
    group by all

),

expected as (

    -- what a dark season is missing: the organization's mean record count in the seasons it did report
    select source_system, org_id, avg(n_records) filter (where reported) as mean_records from {{ ref('dq_org_season_base') }} group by 1, 2

),

issues as (

    select
        b.source_system, b.org_id, b.season_year, b.rule_id, b.dimension, b.severity, b.purposes_breached, b.fix_guidance, b.owner_role,
        case when b.rule_grain = 'ORG_SEASON' then round(coalesce(e.mean_records, 0))::bigint else b.records_affected end as records_affected,
        case when b.rule_grain = 'ORG_SEASON' then 1.0 else coalesce(y.per_record, 0) end                                   as yield,
        case when b.rule_grain = 'ORG_SEASON' then 'EXPECTED_FROM_OTHER_SEASONS' when y.per_record is null then 'NOT_MEASURED' else 'MEASURED' end as impact_basis,
        case when b.rule_grain = 'ORG_SEASON' then 'PARTICIPANTS' else coalesce(y.unit, 'PARTICIPANTS') end                as impact_unit
    from breached b
    left join best_yield y using (source_system, org_id, season_year, rule_id)
    left join expected e on e.source_system = b.source_system and e.org_id = b.org_id

),

breadth as (

    select source_system, season_year, rule_id,
           count(distinct org_id) filter (where pass is false)::double / nullif(count(distinct org_id), 0) as share_of_orgs_breaching
    from results group by 1, 2, 3

),

ranked as (

    select issues.*, round(records_affected * yield, 1) as impact_estimate,
           coalesce(br.share_of_orgs_breaching >= (select value::double from {{ ref('p5_params') }} where param = 'systemic_share'), false) as is_systemic,
           row_number() over (partition by source_system, org_id, season_year
                              order by records_affected * yield desc, (select weight from {{ ref('dq_severity_weights') }} w where w.severity = issues.severity) desc, rule_id) as fix_rank
    from issues left join breadth br using (source_system, season_year, rule_id)

),

scoped as (

    select *, row_number() over (partition by source_system, org_id, season_year, is_systemic order by fix_rank) as rank_in_scope from ranked

)

select
    r.source_system, r.org_id, o.org_name, r.season_year, r.fix_rank, r.is_systemic, r.rank_in_scope, r.rule_id, r.dimension, r.severity, r.purposes_breached,
    r.records_affected, r.impact_estimate, r.impact_unit, r.impact_basis, r.fix_guidance, r.owner_role
from scoped r
join {{ ref('dq_org_season_base') }} o using (source_system, org_id, season_year)
where r.fix_rank <= 5 or (not r.is_systemic and r.rank_in_scope <= 3)
