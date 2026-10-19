{{ config(tags=['phase5']) }}
-- DP1's dq_fix_list: ranks are unique per organization-season and ordered by records affected (ties: the rule's severity weight, then rule_id; the no-file issue is always first); no INFO rule appears; every issue really breaches a
-- registry threshold of DP1's own measures; the organization-reported issue appears only for a dark organization-season; the list carries counts only (no record, person or household id column).
select 'duplicate fix rank' as problem, source_system || '|' || org_id || '|' || season_year as detail from {{ ref('dq_fix_list') }} group by source_system, org_id, season_year, fix_rank having count(*) > 1
union all
select 'fix list not ordered by records affected', a.source_system || '|' || a.org_id || '|' || a.season_year
from {{ ref('dq_fix_list') }} a join {{ ref('dq_fix_list') }} b
  on a.source_system = b.source_system and a.org_id = b.org_id and a.season_year = b.season_year and a.fix_rank < b.fix_rank
where a.records_affected < b.records_affected and a.rule_id <> 'DQ-TIME-ORG-REPORTED'
union all
select 'INFO rule in the fix list', rule_id from {{ ref('dq_fix_list') }} where severity = 'INFO'
union all
select 'identity-dependent rule in the DP1 fix list', rule_id from {{ ref('dq_fix_list') }}
where rule_id in ('DQ-UNIQ-CHILD-SEASON', 'DQ-CONS-DOB-AGREES', 'DQ-CONS-SEX-AGREES', 'DQ-CONS-POSTAL-AGREES', 'DQ-CONS-AGE-GROUP-AGREES')
union all
select 'issue that breaches no threshold', f.rule_id
from {{ ref('dq_fix_list') }} f
where not exists (select 1 from {{ ref('dq_rule_results') }} r where r.rule_id = f.rule_id and r.source_system = f.source_system and r.org_id = f.org_id and r.season_year = f.season_year and r.pass is false)
union all
select 'organization-reported issue for a reporting organization', f.org_id
from {{ ref('dq_fix_list') }} f join {{ ref('dq_org_season_base') }} o using (source_system, org_id, season_year)
where f.rule_id = 'DQ-TIME-ORG-REPORTED' and o.reported
union all
select 'identifying column in the fix list', column_name
from information_schema.columns
where table_schema = '{{ ref("dq_fix_list").schema }}' and table_name = 'dq_fix_list' and regexp_matches(lower(column_name), 'person|participant|household|record_key|source_record|email|name') and lower(column_name) <> 'org_name'
union all
select 'dark organization-season without the no-file fix', o.source_system || '|' || o.org_id || '|' || o.season_year
from {{ ref('dq_org_season_base') }} o
where not o.reported
  and not exists (select 1 from {{ ref('dq_fix_list') }} f where f.source_system = o.source_system and f.org_id = o.org_id and f.season_year = o.season_year and f.rule_id = 'DQ-TIME-ORG-REPORTED')
union all
select 'no-file fix not first', source_system || '|' || org_id || '|' || season_year
from {{ ref('dq_fix_list') }} where rule_id = 'DQ-TIME-ORG-REPORTED' and (fix_rank <> 1 or (not is_systemic and rank_in_scope <> 1))
union all
select 'no-file fix shown as zero', source_system || '|' || org_id || '|' || season_year
from {{ ref('dq_fix_list') }} where rule_id = 'DQ-TIME-ORG-REPORTED' and coalesce(records_affected, 0) = 0 and records_basis <> 'NOT_ESTIMABLE'
union all
select 'no-file fix with a basis that is not an estimate', source_system || '|' || org_id || '|' || season_year
from {{ ref('dq_fix_list') }} where rule_id = 'DQ-TIME-ORG-REPORTED' and records_basis not in ('EXPECTED_FROM_OTHER_SEASONS', 'EXPECTED_FROM_PEERS', 'NOT_ESTIMABLE')
union all
select 'counted fix labelled as an estimate', source_system || '|' || org_id || '|' || season_year
from {{ ref('dq_fix_list') }} where rule_id <> 'DQ-TIME-ORG-REPORTED' and records_basis <> 'COUNTED'
union all
select 'no-file fix in the ops share not labelled estimated', org_id || '|' || season_year
from {{ ref('share_ops__league_fix_list') }} where rule_id = 'DQ-TIME-ORG-REPORTED' and scale_plain not like 'estimated:%'
union all
select 'visible fix-list size says records', org_id || '|' || season_year
from {{ ref('share_ops__league_fix_list') }} where lower(scale_plain || ' ' || problem_plain || ' ' || what_to_do_plain) like '%records%' and rule_id not like 'DQ-CTR-%' and rule_id not like 'DQ-STD-%'
