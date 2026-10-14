{{ config(tags=['phase5']) }}
-- Stages 3 to 5 are nested subsets (households), stage 2 cannot exceed stage 1 (children), and the activation statuses partition the households.
with f as (select stage, n from {{ ref('p5_consent_funnel') }})

select 'stage 2 exceeds stage 1' as problem where (select n from f where stage = 2) > (select n from f where stage = 1)
union all
select 'stage 4 exceeds stage 3' where (select n from f where stage = 4) > (select n from f where stage = 3)
union all
select 'stage 5 exceeds stage 4 is allowed only if provenance is not required' where (select n from f where stage = 5) > (select n from f where stage = 4)
union all
select 'statuses do not partition households' where (select count(*) from {{ ref('p5_household_activation') }}) <> (select n from f where stage = 3)
