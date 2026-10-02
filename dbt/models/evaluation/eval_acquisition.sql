{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). Acquisition incrementality against the truth the generator knows: how many accounts the programme actually caused (acq_type INCREMENTAL), in the same
-- market-year cells the estimate uses, and how far the NAIVE claim ("every account created after a registration") overshoots.
--   truth_incremental_same_cells   the programme-caused new accounts in exactly the cohort-year cells of the estimate (fan_market_truth)
--   truth_net_new_households       households whose account was created after their first registration (caused or not), the launch cohorts of the estimate
--   truth_incremental_households   of those, the ones the programme caused
-- The comparison is between the estimate with its range, the observed and scaled naive counts, and the truth. Nothing here feeds back into the design.
with cells as (select launch_cohort, year from {{ ref('mart_acquisition_incrementality') }} where is_post_period),

truth_cells as (

    select sum(t.new_accounts_incremental) as truth_incremental_same_cells
    from {{ source('ground_truth', 'fan_market_truth') }} t
    join cells c on c.launch_cohort = t.launch_year and c.year = t.year
),

hh as (

    select
        count(*) filter (where truth_status = 'NET_NEW')                    as truth_net_new_households,
        count(*) filter (where acq_type = 'INCREMENTAL')                    as truth_incremental_households
    from {{ source('ground_truth', 'fan_truth') }} f
    join {{ ref('market_map') }} m on m.market_id = f.market_id
    where f.is_participant_household and f.first_registration_year in (select distinct launch_cohort from {{ ref('mart_acquisition_incrementality') }}) and m.launch_year = f.first_registration_year
),

s as (select * from {{ ref('mart_acquisition_summary') }})

select 'incremental_accounts' as measure, s.incremental_accounts as estimate, s.incremental_ci_low as ci_low, s.incremental_ci_high as ci_high,
       t.truth_incremental_same_cells as truth,
       round(s.incremental_accounts - t.truth_incremental_same_cells, 1) as error,
       t.truth_incremental_same_cells between s.incremental_ci_low and s.incremental_ci_high as truth_in_range,
       round(s.incremental_accounts / t.truth_incremental_same_cells, 3) as estimate_over_truth
from s cross join truth_cells t
union all
select 'naive_net_new_observed', s.naive_net_new_observed, null, null, t.truth_incremental_same_cells, s.naive_net_new_observed - t.truth_incremental_same_cells, null,
       round(s.naive_net_new_observed * 1.0 / t.truth_incremental_same_cells, 3)
from s cross join truth_cells t
union all
select 'naive_net_new_scaled_by_link_rate', s.naive_net_new_scaled, null, null, t.truth_incremental_same_cells, s.naive_net_new_scaled - t.truth_incremental_same_cells, null,
       round(s.naive_net_new_scaled * 1.0 / t.truth_incremental_same_cells, 3)
from s cross join truth_cells t
union all
select 'truth_net_new_households', null, null, null, h.truth_net_new_households, null, null, null from hh h
union all
select 'truth_incremental_households', null, null, null, h.truth_incremental_households, null, null, null from hh h
