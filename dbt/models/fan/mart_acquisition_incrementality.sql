-- ACQUISITION INCREMENTALITY, measured at MARKET level with the staggered rollout (rework spec 5.2). Households that are neither fans nor participants are invisible, so a household-level
-- comparison cannot measure acquisition; markets can, because the programme launched in different markets in different years and some never launched.
--
-- Design: a STACKED, COHORT-SPECIFIC comparison, not a pooled two-way fixed-effects regression (ADR-011 explains why: with staggered timing the pooled estimator uses already-treated
-- markets as controls and is biased). For each launch cohort L (markets launching in year L) and each event time k (years since launch), the group-time effect is
--     ATT(L, k) = mean over cohort-L markets of [rate(L+k) - rate(L-1)]  -  mean over CONTROL markets of [rate(L+k) - rate(L-1)]
-- where rate is new fan accounts per 1,000 households, the base year is the year BEFORE launch (L-1), and the controls are the markets NOT YET TREATED in either year plus the never-treated
-- ones (launch_year is NULL or later than max(L+k, L)). Cohort 2021 has no pre-period inside the data and is not estimated.
-- se is the standard error of that difference of means (from market-level changes); n_* are market counts. incremental_accounts = ATT / 1000 x the cohort's household population: the new
-- fan accounts the programme added in those markets that year (k >= 0). Pre-period cells (k < 0) are the check on the design: they should be near zero.
with p as (select * from {{ ref('int_market_year_accounts') }}),

cohorts as (select distinct launch_year as cohort from p where launch_year is not null and launch_year > (select min(year) from p)),

ks as (select unnest(range(-2, 4)) as k),

cells as (

    select c.cohort, k.k, c.cohort + k.k as year, c.cohort - 1 as base_year
    from cohorts c cross join ks k
    where k.k <> -1 and c.cohort + k.k between (select min(year) from p) and (select max(year) from p) and c.cohort - 1 >= (select min(year) from p)

),

treated as (

    select ce.cohort, ce.k, m.market_id, m.household_population, t1.new_accounts_per_1000_households - t0.new_accounts_per_1000_households as d
    from cells ce
    join (select distinct market_id, household_population, launch_year from p) m on m.launch_year = ce.cohort
    join p t1 on t1.market_id = m.market_id and t1.year = ce.year
    join p t0 on t0.market_id = m.market_id and t0.year = ce.base_year

),

control as (

    select ce.cohort, ce.k, m.market_id, t1.new_accounts_per_1000_households - t0.new_accounts_per_1000_households as d
    from cells ce
    join (select distinct market_id, launch_year from p) m on m.launch_year is null or m.launch_year > greatest(ce.year, ce.cohort)
    join p t1 on t1.market_id = m.market_id and t1.year = ce.year
    join p t0 on t0.market_id = m.market_id and t0.year = ce.base_year

),

tg as (select cohort, k, count(*) as n_treated, avg(d) as mean_d, var_samp(d) as var_d, sum(household_population) as treated_households from treated group by 1, 2),

cg as (select cohort, k, count(*) as n_control, avg(d) as mean_d, var_samp(d) as var_d from control group by 1, 2)

select
    tg.cohort                                                               as launch_cohort,
    tg.k                                                                    as years_since_launch,
    tg.cohort + tg.k                                                        as year,
    tg.n_treated                                                            as treated_markets,
    cg.n_control                                                            as control_markets,
    tg.treated_households,
    round(tg.mean_d - cg.mean_d, 5)                                         as att_per_1000_households,
    round(sqrt(coalesce(tg.var_d, 0) / tg.n_treated + coalesce(cg.var_d, 0) / cg.n_control), 5) as se_per_1000_households,
    round((tg.mean_d - cg.mean_d) * tg.treated_households / 1000.0, 3)      as incremental_accounts,
    round(sqrt(coalesce(tg.var_d, 0) / tg.n_treated + coalesce(cg.var_d, 0) / cg.n_control) * tg.treated_households / 1000.0, 3) as se_incremental_accounts,
    tg.k >= 0                                                               as is_post_period,
    '{{ var("methodology_version") }}'                                      as methodology_version
from tg join cg using (cohort, k)
order by 1, 2
