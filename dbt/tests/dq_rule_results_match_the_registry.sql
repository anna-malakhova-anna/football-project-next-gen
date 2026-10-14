{{ config(tags=['phase5']) }}
-- Every rule in dq_rule_results is in the registry, every registry rule ran at least once, a pass rate never exceeds one, and a pass is never recorded without a threshold.
select rule_id, 'result rule not in the registry' as problem from {{ ref('dq_rule_results') }} where rule_id not in (select rule_id from {{ ref('dq_rule_registry') }})
union all
select rule_id, 'registry rule never ran' from {{ ref('dq_rule_registry') }} where rule_id not in (select rule_id from {{ ref('dq_rule_results') }})
union all
select distinct rule_id, 'n_pass exceeds n_evaluated' from {{ ref('dq_rule_results') }} where n_pass > n_evaluated
union all
select distinct rule_id, 'pass without a threshold' from {{ ref('dq_rule_results') }} where pass is not null and threshold is null
union all
select distinct rule_id, 'pass disagrees with observed >= threshold' from {{ ref('dq_rule_results') }} where pass is not null and pass <> (observed_value >= threshold)
