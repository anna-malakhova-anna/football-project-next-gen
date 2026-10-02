{{ config(tags=['phase4']) }}
-- Cohort triangle starts at 100% and never exceeds it; transition shares add to one per origin division; driver rates and intervals are proper
-- proportions; the youth-to-adult rate is a proportion of the players who aged out.
select 'cohort_k0_not_100pct' as problem, cast(entry_year as varchar) || '|' || grain as detail
from {{ ref('mart_retention_cohorts') }} where years_since_entry = 0 and retention_pct <> 1
union all
select 'cohort_share_out_of_range', cast(entry_year as varchar) || '|' || grain || '|' || cast(years_since_entry as varchar)
from {{ ref('mart_retention_cohorts') }} where retention_pct > 1 or retention_among_eligible > 1 or active_count > cohort_size
union all
select 'cohort_cell_not_observable', cast(entry_year as varchar) || '|' || cast(years_since_entry as varchar)
from {{ ref('mart_retention_cohorts') }} where entry_year + years_since_entry > (select last_observed_year from {{ ref('observation_window') }})
union all
select 'transition_shares_do_not_sum_to_1', cast(from_year as varchar) || '|' || from_division
from {{ ref('mart_retention_transitions') }} group by from_year, from_division having abs(sum(share_of_from) - 1) > 0.001
union all
select 'driver_rate_out_of_range', segment_type || '|' || segment_value || '|' || coalesce(cast(participation_year as varchar), 'pooled')
from {{ ref('mart_retention_drivers') }}
where retained_n > eligible_n or retention_rate not between 0 and 1 or ci_low > retention_rate or retention_rate > ci_high
union all
select 'driver_pooled_differs_from_yearly_sum', segment_type || '|' || segment_value
from (
    select segment_type, segment_value,
           sum(eligible_n) filter (where participation_year is null) as pooled_n,
           sum(eligible_n) filter (where participation_year is not null) as yearly_n
    from {{ ref('mart_retention_drivers') }} group by 1, 2
) where pooled_n <> yearly_n
union all
select 'youth_to_adult_out_of_range', coalesce(cast(participation_year as varchar), 'pooled')
from {{ ref('mart_youth_to_adult') }} where continued_n > aged_out_n or youth_to_adult_rate not between 0 and 1
