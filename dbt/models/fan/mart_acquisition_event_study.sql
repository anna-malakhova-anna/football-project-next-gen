-- The event study: the group-time effects of mart_acquisition_incrementality averaged over launch cohorts for each year since launch (-2 to +3), weighted by the cohort's household population.
-- A flat pre-period (k < 0 near zero) supports the design. se combines the cohort standard errors (cohorts use different markets, so they are treated as independent; controls are shared, so the
-- interval is somewhat too narrow). 95% interval = estimate +/- 1.96 se.
select
    years_since_launch,
    count(*)                                                                as cohorts,
    sum(treated_markets)                                                    as treated_markets,
    round(sum(att_per_1000_households * treated_households) / sum(treated_households), 5) as att_per_1000_households,
    round(sqrt(sum(power(se_per_1000_households * treated_households, 2))) / sum(treated_households), 5) as se_per_1000_households,
    round(sum(att_per_1000_households * treated_households) / sum(treated_households)
          - 1.96 * sqrt(sum(power(se_per_1000_households * treated_households, 2))) / sum(treated_households), 5) as ci_low,
    round(sum(att_per_1000_households * treated_households) / sum(treated_households)
          + 1.96 * sqrt(sum(power(se_per_1000_households * treated_households, 2))) / sum(treated_households), 5) as ci_high,
    '{{ var("methodology_version") }}'                                      as methodology_version
from {{ ref('mart_acquisition_incrementality') }}
group by years_since_launch
order by years_since_launch
