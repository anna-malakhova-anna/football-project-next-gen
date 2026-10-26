{{ config(tags=['phase7']) }}
-- Spec D10: DP6's regime ports split the 22 program markets with nothing lost and nothing doubled. Every market is in exactly one markets port, every
-- unmeasured market in exactly one scenario port, and every port holds only markets of its own regime.
with markets as (
    select 'global_eu_uk' as port, country_code, legal_regime_id from {{ ref('share_exec__gmp_markets_eu_uk') }}
    union all select 'global_canada', country_code, legal_regime_id from {{ ref('share_exec__gmp_markets_canada') }}
    union all select 'global_other', country_code, legal_regime_id from {{ ref('share_exec__gmp_markets_other') }}
),
scenario as (
    select 'global_eu_uk' as port, country_code, legal_regime_id from {{ ref('share_exec__gmp_scenario_eu_uk') }}
    union all select 'global_other', country_code, legal_regime_id from {{ ref('share_exec__gmp_scenario_other') }}
)
select 'market missing from every port' as problem, m.country_code as detail from {{ ref('gmp_markets') }} m
where m.country_code not in (select country_code from markets)
union all
select 'market in more than one port', country_code from markets group by country_code having count(*) > 1
union all
select 'market in the wrong regime port', k.country_code from markets k join {{ ref('legal_regime') }} r using (legal_regime_id) where r.output_port <> k.port
union all
select 'unmeasured market missing from the scenario ports', s.country_code from {{ ref('mart_gmp_scenario') }} s
where s.country_code not in (select country_code from scenario)
union all
select 'scenario in the wrong regime port', k.country_code from scenario k join {{ ref('legal_regime') }} r using (legal_regime_id) where r.output_port <> k.port
