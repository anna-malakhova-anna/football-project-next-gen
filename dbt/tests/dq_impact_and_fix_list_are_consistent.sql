{{ config(tags=['phase5']) }}
-- mart_dq_impact: impact units are non-negative and no larger than the failing records can explain; the Pareto is a proper cumulative share ending at 1; ranks start at 1.
-- dq_fix_ranking (DP4): ranks are unique per organization-season and ordered by impact (not by raw count); no INFO rule appears; every issue really breaches a registry threshold; the organization-reported
-- issue appears only for a dark organization-season; the list carries counts only (no record, person or household id column).
select 'negative impact' as problem, rule_id as detail from {{ ref('mart_dq_impact') }} where impact_units < 0 or participants_lost < 0
union all
select 'more participants lost than failing records', rule_id from {{ ref('mart_dq_impact') }} where participants_lost > records_failing
union all
select 'cumulative share not ending at 1', purpose || '|' || population || '|' || season_year
from (select purpose, population, season_year, max(cumulative_share) as m, sum(impact_units) as total from {{ ref('mart_dq_impact') }} group by all) where total > 0 and abs(m - 1) > 0.001
union all
select 'rank does not start at 1', purpose || '|' || population || '|' || season_year
from (select purpose, population, season_year, min(rank_in_purpose) as r from {{ ref('mart_dq_impact') }} group by all) where r <> 1
union all
select 'duplicate fix rank', source_system || '|' || org_id || '|' || season_year from {{ ref('dq_fix_ranking') }} group by source_system, org_id, season_year, fix_rank having count(*) > 1
union all
select 'fix list not ordered by impact', a.source_system || '|' || a.org_id || '|' || a.season_year
from {{ ref('dq_fix_ranking') }} a join {{ ref('dq_fix_ranking') }} b
  on a.source_system = b.source_system and a.org_id = b.org_id and a.season_year = b.season_year and a.fix_rank < b.fix_rank
where a.impact_estimate < b.impact_estimate
union all
select 'INFO rule in the fix list', rule_id from {{ ref('dq_fix_ranking') }} where severity = 'INFO'
union all
select 'issue that breaches no threshold', f.rule_id
from {{ ref('dq_fix_ranking') }} f
where not exists (select 1 from {{ ref('dq_rule_results') }} r where r.rule_id = f.rule_id and r.source_system = f.source_system and r.org_id = f.org_id and r.season_year = f.season_year and r.pass is false)
union all
select 'organization-reported issue for a reporting organization', f.org_id
from {{ ref('dq_fix_ranking') }} f join {{ ref('dq_org_season_base') }} o using (source_system, org_id, season_year)
where f.rule_id = 'DQ-TIME-ORG-REPORTED' and o.reported
union all
select 'identifying column in the fix list', column_name
from information_schema.columns
where table_schema = '{{ ref("dq_fix_ranking").schema }}' and table_name = 'dq_fix_ranking' and regexp_matches(lower(column_name), 'person|participant|household|record_key|source_record|email|name') and lower(column_name) <> 'org_name'
