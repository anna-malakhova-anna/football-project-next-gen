{{ config(tags=['phase4']) }}
-- ANALYST share: a market-year panel of new fan accounts per 1,000 households, with the launch year and whether the market is treated that year. This is the table the incrementality
-- estimate is built from, so an analyst can re-estimate it. Markets are synthetic and carry no household or account identifier. Cells with fewer than k_min new accounts are suppressed.
with src as (

    select market_id, country_code, is_team_market, launch_year, year as panel_year, household_population, new_accounts as market_new_accounts,
           new_accounts_per_1000_households as market_new_accounts_per_1000, is_treated_in_year as market_is_treated
    from {{ ref('int_market_year_accounts') }}

)

select market_id, country_code, is_team_market, launch_year, panel_year, household_population, market_new_accounts, market_new_accounts_per_1000, market_is_treated, suppressed
from {{ suppress_small_cells('src', ['market_id', 'panel_year'], ['market_new_accounts'],
        rates={'market_new_accounts_per_1000': ['market_new_accounts']}, passthrough=['country_code', 'is_team_market', 'launch_year', 'household_population', 'market_is_treated']) }}
order by market_id, panel_year
