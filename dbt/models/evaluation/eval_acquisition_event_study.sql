{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). The event study of acquisition incrementality against the true effect by year since launch: the programme-caused new accounts per 1,000 households,
-- from fan_market_truth, over the same cohort cells (weighted by household population) as the estimate. Pre-period years should be near zero in both.
with cells as (select launch_cohort, years_since_launch, year, treated_households from {{ ref('mart_acquisition_incrementality') }}),

t as (

    select c.years_since_launch,
           sum(m.new_accounts_incremental * 1000.0 / m.household_population * c.treated_households) / sum(c.treated_households) as truth_att_per_1000
    from cells c
    join {{ source('ground_truth', 'fan_market_truth') }} m on m.launch_year = c.launch_cohort and m.year = c.year
    group by 1

)

select e.years_since_launch, e.att_per_1000_households as estimate, e.ci_low, e.ci_high, round(t.truth_att_per_1000, 5) as truth,
       round(e.att_per_1000_households - t.truth_att_per_1000, 5) as error,
       t.truth_att_per_1000 between e.ci_low and e.ci_high as truth_in_ci
from {{ ref('mart_acquisition_event_study') }} e join t using (years_since_launch)
order by 1
