{{ config(tags=['phase7']) }}
-- ADR-025: all 22 program markets have exactly one status; a planning scenario exists for every PROXY_ONLY and DARK market and for no other;
-- and a scenario range is ordered (low <= high).
select 'market count is not 22' as problem, cast(count(*) as varchar) as detail from {{ ref('mart_gmp_market_status') }} having count(*) <> 22
union all
select 'unmeasured market without a scenario', s.country_code from {{ ref('mart_gmp_market_status') }} s
where s.status in ('PROXY_ONLY', 'DARK') and not exists (select 1 from {{ ref('mart_gmp_scenario') }} c where c.country_code = s.country_code)
union all
select 'scenario for a market with participation data', c.country_code from {{ ref('mart_gmp_scenario') }} c
join {{ ref('mart_gmp_market_status') }} s using (country_code) where s.status not in ('PROXY_ONLY', 'DARK')
union all
select 'scenario range out of order', country_code from {{ ref('mart_gmp_scenario') }} where scenario_low > scenario_high
