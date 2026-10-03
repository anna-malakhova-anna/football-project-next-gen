{{ config(tags=['phase4']) }}
-- EXEC share: how many fan accounts did the programme add that would not have existed anyway? One row: the incremental estimate with its interval next to the naive count of
-- net-new households, scaled up by the link rate. Counts of accounts across many markets, so no cell is small; the macro still applies k_min. AGGREGATE ONLY (restricted `linkage` schema, ADR-009).
-- The estimate compares launching markets with markets that had not launched yet (stacked cohort comparison, ADR-011); it is an estimate with an interval, not a count.
with src as (

    select methodology_version,
           cast(round(incremental_accounts) as bigint)  as incremental_fan_accounts,
           cast(round(incremental_ci_low) as bigint)    as incremental_fan_accounts_ci_low,
           cast(round(incremental_ci_high) as bigint)   as incremental_fan_accounts_ci_high,
           naive_net_new_observed                       as net_new_linked_households,
           cast(round(naive_net_new_scaled) as bigint)  as net_new_households_scaled,
           market_years                                 as market_years_compared
    from {{ ref('mart_acquisition_summary') }}

)

select methodology_version, incremental_fan_accounts, incremental_fan_accounts_ci_low, incremental_fan_accounts_ci_high, net_new_linked_households,
       net_new_households_scaled, market_years_compared, suppressed,
       'Incremental = accounts that would not exist without the programme, estimated from staggered market launches. Net-new = households with no account before registering: more than incremental, because some would have joined anyway. Synthetic data.' as caveat
from {{ suppress_small_cells('src', ['methodology_version'],
        ['net_new_linked_households', 'incremental_fan_accounts', 'incremental_fan_accounts_ci_low', 'incremental_fan_accounts_ci_high', 'net_new_households_scaled', 'market_years_compared']) }}
