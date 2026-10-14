{{ config(tags=['phase5']) }}
-- Phase 1 migration: every flag classified in dq_flag_severity is checked by exactly one PHASE1 registry rule. dq_flag_severity keeps the TREATMENT of a flag in the counting rules;
-- the registry measures how often it fires. A flag with no rule, or two rules, is a hole or a duplicate engine.
with f as (select flag from {{ ref('dq_flag_severity') }}),

hits as (

    select f.flag, r.rule_id
    from f join {{ ref('dq_rule_registry') }} r on r.origin = 'PHASE1' and contains(r.check_sql, '''' || f.flag || '''')

)

select f.flag, count(h.rule_id) as rules
from f left join hits h using (flag)
group by 1 having count(h.rule_id) <> 1
union all
select flag, count(*) from (select distinct flag, rule_id from hits) group by 1 having count(*) > 1
