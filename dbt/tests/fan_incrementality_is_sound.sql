{{ config(tags=['phase4']) }}
-- Acquisition incrementality: the comparison markets of every cell are never already treated in the comparison years (launch year is NULL or after both the cell's year and its cohort), the
-- treated markets are exactly the cohort's, cohort 2021 (no pre-period) is not estimated, the reference year k = -1 is never an estimate, and event times stay inside -2 to +3.
with cells as (select * from {{ ref('mart_acquisition_incrementality') }}),

m as (select distinct market_id, launch_year from {{ ref('int_market_year_accounts') }})

select 'control_count_differs_from_the_clean_definition' as problem, cast(c.launch_cohort as varchar) || '|' || cast(c.years_since_launch as varchar) as detail
from cells c
where c.control_markets <> (select count(*) from m where m.launch_year is null or m.launch_year > greatest(c.year, c.launch_cohort))
union all
select 'treated_count_differs_from_the_cohort', cast(c.launch_cohort as varchar) || '|' || cast(c.years_since_launch as varchar)
from cells c where c.treated_markets <> (select count(*) from m where m.launch_year = c.launch_cohort)
union all
select 'cohort_without_a_pre_period_estimated', cast(launch_cohort as varchar) from cells where launch_cohort <= (select min(year) from {{ ref('int_market_year_accounts') }})
union all
select 'reference_year_estimated', cast(launch_cohort as varchar) from cells where years_since_launch = -1
union all
select 'event_time_out_of_range', cast(launch_cohort as varchar) || '|' || cast(years_since_launch as varchar) from cells where years_since_launch not between -2 and 3
union all
select 'a_treated_market_is_also_a_control', cast(launch_cohort as varchar)
from cells c where exists (select 1 from m where m.launch_year = c.launch_cohort and (m.launch_year > greatest(c.year, c.launch_cohort)))
union all
select 'panel_years_do_not_cover_the_window', cast(n as varchar) from (select count(distinct year) as n from {{ ref('int_market_year_accounts') }}) where n <> (select last_observed_year - first_observed_year + 1 from {{ ref('observation_window') }})
