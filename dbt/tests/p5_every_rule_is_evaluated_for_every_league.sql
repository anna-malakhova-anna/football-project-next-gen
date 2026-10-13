{{ config(tags=['phase5']) }}
-- The results table has one row per rule x league group, so no rule is silently skipped for a league and no league is skipped for a rule.
select 'wrong row count' as problem
where (select count(*) from {{ ref('dq_rule_results_league') }}) <>
      (select count(*) from {{ ref('p5_dq_rules') }}) * (select count(distinct league_group) from {{ ref('p5_record_quality') }})
