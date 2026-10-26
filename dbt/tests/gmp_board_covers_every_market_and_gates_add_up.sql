{{ config(tags=['phase7']) }}
-- Spec section 9: the board has one card for each of the 22 program markets; a MET gate really has its value at or above the target and a NOT_YET gate
-- below it; MAINTAIN holds only MEASURED markets; every dimension score is 1 to 5.
select 'market without a card' as problem, m.country_code as detail from {{ ref('gmp_markets') }} m
where m.country_code not in (select country_code from {{ ref('mart_gmp_board') }})
union all
select 'gate status disagrees with its values', country_code from {{ ref('mart_gmp_board') }}
where (gate_status = 'MET' and current_value < target_value) or (gate_status = 'NOT_YET' and current_value >= target_value)
union all
select 'MAINTAIN lane holds an unmeasured market', country_code from {{ ref('mart_gmp_board') }} where lane = 'MAINTAIN' and status <> 'MEASURED'
union all
select 'dimension score outside 1 to 5', country_code from {{ ref('mart_gmp_priority') }}
where least(value_to_goals, feasibility_today, data_readiness, privacy_risk) < 1 or greatest(value_to_goals, feasibility_today, data_readiness, privacy_risk) > 5
