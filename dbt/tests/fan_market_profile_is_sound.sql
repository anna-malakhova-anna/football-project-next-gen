{{ config(tags=['phase4']) }}
-- The market profile: one row per market; participant households add up to the households observed; fan accounts add up to the accounts with a market; markets where the programme never launched have
-- no participants; every market gets exactly one of the defined quadrants; the quadrant follows the thresholds (no literals); rates are proportions; the shape profile covers every household once.
select 'market_missing_or_twice' as problem, market_id as detail from {{ ref('market_map') }} m where (select count(*) from {{ ref('mart_market_profile') }} p where p.market_id = m.market_id) <> 1
union all
select 'participant_households_do_not_add_up', cast(a as varchar) || ' vs ' || cast(b as varchar)
from (select (select sum(participant_households) from {{ ref('mart_market_profile') }}) as a, (select count(*) from {{ ref('int_household_profile') }} where market_id is not null) as b) where a <> b
union all
select 'fan_accounts_do_not_add_up', cast(a as varchar) || ' vs ' || cast(b as varchar)
from (select (select sum(fan_accounts) from {{ ref('mart_market_profile') }}) as a, (select count(*) from {{ ref('dim_fan_account') }} where market_id is not null) as b) where a <> b
union all
select 'a_market_that_never_launched_has_participants', market_id from {{ ref('mart_market_profile') }} where launch_year is null and participant_households > 0
union all
select 'unknown_quadrant', market_id from {{ ref('mart_market_profile') }}
where quadrant not in ('Acquisition white space', 'Retention and engagement play', 'Program growth opportunity', 'Long-term build', 'UNCLASSIFIED')
union all
select 'quadrant_disagrees_with_the_thresholds', market_id from {{ ref('mart_market_profile') }}
where quadrant <> 'UNCLASSIFIED' and quadrant <> case
        when participation_per_1000 >= participation_threshold and fan_accounts_per_1000 < fan_threshold then 'Acquisition white space'
        when participation_per_1000 >= participation_threshold and fan_accounts_per_1000 >= fan_threshold then 'Retention and engagement play'
        when participation_per_1000 < participation_threshold and fan_accounts_per_1000 >= fan_threshold then 'Program growth opportunity'
        else 'Long-term build' end
union all
select 'rate_out_of_range', market_id from {{ ref('mart_market_profile') }}
where coalesce(net_new_rate, 0) not between 0 and 1 or coalesce(link_rate, 0) not between 0 and 1 or coalesce(girls_share, 0) not between 0 and 1 or coalesce(consent_capture_rate, 0) not between 0 and 1
union all
select 'shape_profile_does_not_cover_every_household_once', cast(a as varchar) || ' vs ' || cast(b as varchar)
from (select (select sum(households) from {{ ref('mart_household_shape_profile') }}) as a, (select count(*) from {{ ref('int_household_profile') }}) as b) where a <> b
