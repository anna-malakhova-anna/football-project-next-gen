-- The market x year panel behind acquisition incrementality (rework spec 5.2): new fan accounts created in the market in the year, per 1,000 synthetic households. Household-free: it counts
-- accounts (duplicates collapsed) by the market of the account and the year the account was created. Accounts created before the data starts are not "new" in any year of the panel.
-- launch_year comes from market_map (an operational fact: when the programme started in the market); NULL means it never launched.
with years as (select unnest(range(first_observed_year, last_observed_year + 1)) as year from {{ ref('observation_window') }}),

acc as (

    select market_id, created_year as year, count(*) as new_accounts
    from {{ ref('dim_fan_account') }}
    where market_id is not null and created_year >= (select first_observed_year from {{ ref('observation_window') }})
    group by 1, 2

)

select
    m.market_id,
    m.country_code,
    m.is_team_market = 'Y'                                                  as is_team_market,
    m.launch_year,
    m.household_population,
    y.year,
    coalesce(a.new_accounts, 0)                                             as new_accounts,
    round(coalesce(a.new_accounts, 0) * 1000.0 / m.household_population, 6) as new_accounts_per_1000_households,
    m.launch_year is not null and y.year >= m.launch_year                   as is_treated_in_year
from {{ ref('market_map') }} m
cross join years y
left join acc a on a.market_id = m.market_id and a.year = y.year
