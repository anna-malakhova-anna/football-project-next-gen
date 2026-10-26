{{ config(tags=['phase7']) }}
-- GROUND TRUTH (evaluation only, synthetic; ADR-025 section 6). The whitelisted summary of eval_gmp_scenario, for all markets with no participation
-- source and split by whether the answer key set the market against its comparables. Reported as it comes out: there is NO pass threshold, because
-- the result is the evidence for or against publishing a number for a dark market (Anna's decision D3).
with e as (select * from {{ ref('eval_gmp_scenario') }}),

grouped as (

    select 'ALL' as market_group, * from e
    union all
    select case when set_against_comparables then 'SET_AGAINST_COMPARABLES' else 'WITH_COMPARABLES' end, * from e

)

select
    market_group,
    count(*)                                                                as markets,
    count(*) filter (where truth_in_range)                                  as truth_in_range,
    round(avg(truth_in_range::int), 4)                                      as coverage,
    count(*) filter (where truth_vs_range = 'BELOW')                        as truth_below_range,
    count(*) filter (where truth_vs_range = 'ABOVE')                        as truth_above_range,
    count(*) filter (where not direction_match)                             as direction_wrong,
    round(avg((not direction_match)::int), 4)                               as direction_error,
    count(proxy_match)                                                      as proxy_direction_known,
    count(*) filter (where proxy_match)                                     as proxy_direction_right,
    count(*) filter (where comparables_differ)                              as comparables_differ_from_generator
from grouped
group by 1
order by case market_group when 'ALL' then 0 when 'WITH_COMPARABLES' then 1 else 2 end
