-- RESTRICTED (schema `linkage`; counts only). The headline of acquisition incrementality: how many new fan accounts the programme ADDED (market-level estimate, with a range) next to the NAIVE count
-- "every account created after a registration". The naive count comes from the household fan status: NET_NEW linked households. It overclaims twice over: it includes accounts that would have been
-- created anyway (organic) and it sees only LINKED households. `naive_net_new_scaled` divides by the link rate of the same cohorts, the generous version of the naive claim.
-- Cells: launch cohorts 2022 to 2024 (2021 has no pre-period), years since launch 0 to +3 that fall inside the data. The range is +/- 1.96 se, treating cells as independent (they share controls,
-- so it is somewhat too narrow).
with i as (select * from {{ ref('mart_acquisition_incrementality') }} where is_post_period),

est as (

    select
        sum(incremental_accounts)                                           as incremental_accounts,
        sum(incremental_accounts) - 1.96 * sqrt(sum(power(se_incremental_accounts, 2))) as ci_low,
        sum(incremental_accounts) + 1.96 * sqrt(sum(power(se_incremental_accounts, 2))) as ci_high,
        count(*)                                                            as cells,
        sum(treated_markets)                                                as market_years
    from i

),

naive as (

    select
        count(*) filter (where fan_status = 'NET_NEW')                      as net_new_linked_households,
        count(*) filter (where fan_status <> 'UNLINKED')                    as linked_households,
        count(*)                                                            as households
    from {{ ref('fct_household_fan_status') }}
    where first_year in (select distinct launch_cohort from {{ ref('mart_acquisition_incrementality') }}) and not is_left_censored      -- the launch cohorts the estimate covers
)

select
    round(e.incremental_accounts, 1)                                        as incremental_accounts,
    round(e.ci_low, 1)                                                      as incremental_ci_low,
    round(e.ci_high, 1)                                                     as incremental_ci_high,
    e.cells,
    e.market_years,
    n.net_new_linked_households                                             as naive_net_new_observed,
    round(n.net_new_linked_households * n.households * 1.0 / n.linked_households, 0) as naive_net_new_scaled,
    round(n.linked_households * 1.0 / n.households, 4)                      as link_rate,
    n.households                                                            as participant_households,
    round(100.0 * e.incremental_accounts / n.households, 2)                 as incremental_per_100_households,
    round(100.0 * e.ci_low / n.households, 2)                               as incremental_per_100_households_ci_low,
    round(100.0 * e.ci_high / n.households, 2)                              as incremental_per_100_households_ci_high,
    '{{ var("methodology_version") }}'                                      as methodology_version
from est e cross join naive n
