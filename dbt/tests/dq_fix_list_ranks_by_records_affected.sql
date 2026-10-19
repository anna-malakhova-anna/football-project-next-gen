{{ config(tags=['phase5']) }}
-- DP1's dq_fix_list: ranks are unique per organization-season and ordered by records affected (ties: the rule's severity weight, then rule_id); no INFO rule appears; every issue really breaches a
-- registry threshold of DP1's own measures; the organization-reported issue appears only for a dark organization-season; the list carries counts only (no record, person or household id column).
select 'duplicate fix rank' as problem, source_system || '|' || org_id || '|' || season_year as detail from {{ ref('dq_fix_list') }} group by source_system, org_id, season_year, fix_rank having count(*) > 1
union all
select 'fix list not ordered by records affected', a.source_system || '|' || a.org_id || '|' || a.season_year
from {{ ref('dq_fix_list') }} a join {{ ref('dq_fix_list') }} b
  on a.source_system = b.source_system and a.org_id = b.org_id and a.season_year = b.season_year and a.fix_rank < b.fix_rank
where a.records_affected < b.records_affected
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
