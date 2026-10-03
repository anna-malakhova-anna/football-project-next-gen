{{ config(tags=['phase4']) }}
-- ANALYST share: the market-level acquisition event study, by years since a market's launch: the extra new fan accounts per 1,000 households in launched markets compared with markets that
-- had not launched yet, with a 95% interval. A flat pre-period is the check that the comparison is fair. AGGREGATE ONLY (restricted `linkage` schema, ADR-009): markets, not households.
-- Cells with fewer than 3 treated markets are suppressed (the estimate would describe one or two markets).
with src as (

    select years_since_launch, cohorts as launch_cohorts, treated_markets as acquisition_treated_markets, att_per_1000_households as acquisition_effect_per_1000,
           se_per_1000_households as acquisition_effect_se, ci_low as acquisition_effect_ci_low, ci_high as acquisition_effect_ci_high
    from {{ ref('mart_acquisition_event_study') }}

)

select years_since_launch, launch_cohorts, acquisition_treated_markets, acquisition_effect_per_1000, acquisition_effect_se, acquisition_effect_ci_low, acquisition_effect_ci_high,
       case when acquisition_treated_markets < 3 then 'PRIMARY' else 'NONE' end as suppressed
from src
order by years_since_launch
