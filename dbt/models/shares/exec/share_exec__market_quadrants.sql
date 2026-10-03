{{ config(tags=['phase4']) }}
-- EXEC share: where is flag strong and where is the fan base strong? One row per synthetic market with at least k_min participant households, with its quadrant; markets below k_min are
-- ROLLED UP into one row per quadrant (market_id NULL), so no small market is published on its own. Counts and rates per 1,000 households; an invented geography (not real metro areas).
-- AGGREGATE ONLY (restricted `linkage` schema, ADR-009). The rollup row is suppressed in turn if it is still below k_min.
{% set k = privacy_param('k_min') %}
with m as (

    select market_id, market_name, country_code, quadrant, is_team_market, launch_year, household_population, participant_households, fan_accounts, linked_households,
           net_new_households, participation_per_1000, fan_accounts_per_1000, net_new_rate, link_rate
    from {{ ref('mart_market_profile') }}

),

big as (

    select market_id, market_name, country_code, quadrant, is_team_market, launch_year, household_population, participant_households, fan_accounts,
           participation_per_1000, fan_accounts_per_1000, net_new_rate, link_rate, 1 as markets_in_row
    from m where participant_households >= {{ k }}

),

small as (

    select cast(null as varchar) as market_id, 'Markets below the small-cell threshold' as market_name, cast(null as varchar) as country_code, quadrant,
           cast(null as boolean) as is_team_market, cast(null as integer) as launch_year,
           sum(household_population) as household_population,
           sum(participant_households) as participant_households, sum(fan_accounts) as fan_accounts,
           sum(participant_households) * 1000.0 / sum(household_population) as participation_per_1000,
           sum(fan_accounts) * 1000.0 / sum(household_population) as fan_accounts_per_1000,
           sum(net_new_households) * 1.0 / nullif(sum(linked_households), 0) as net_new_rate,
           sum(linked_households) * 1.0 / nullif(sum(participant_households), 0) as link_rate,
           count(*) as markets_in_row
    from m where participant_households < {{ k }} group by quadrant

),

u as (

    select market_id, market_name, country_code, quadrant, is_team_market, launch_year, household_population, participant_households, fan_accounts, participation_per_1000, fan_accounts_per_1000, net_new_rate, link_rate, markets_in_row from big
    union all
    select market_id, market_name, country_code, quadrant, is_team_market, launch_year, household_population, participant_households, fan_accounts, participation_per_1000, fan_accounts_per_1000, net_new_rate, link_rate, markets_in_row from small

)

select market_id, market_name, country_code, quadrant, is_team_market, launch_year, household_population, markets_in_row,
       case when participant_households >= {{ k }} then participant_households end as participant_households,
       case when participant_households >= {{ k }} then fan_accounts end as fan_accounts,
       case when participant_households >= {{ k }} then participation_per_1000 end as participation_per_1000,
       case when participant_households >= {{ k }} then fan_accounts_per_1000 end as fan_accounts_per_1000,
       case when participant_households >= {{ k }} then net_new_rate end as net_new_rate,
       case when participant_households >= {{ k }} then link_rate end as link_rate,
       case when participant_households >= {{ k }} then 'NONE' else 'PRIMARY' end as suppressed
from u
order by quadrant, market_id nulls last
