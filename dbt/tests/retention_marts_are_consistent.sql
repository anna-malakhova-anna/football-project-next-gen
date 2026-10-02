{{ config(tags=['phase4']) }}
-- Cohort triangle starts at 100%, never exceeds it, and only contains cells that can be observed.
select 'cohort_k0_not_100pct' as problem, cast(entry_year as varchar) || '|' || grain as detail
from {{ ref('mart_retention_cohorts') }} where years_since_entry = 0 and retention_pct <> 1
union all
select 'cohort_share_out_of_range', cast(entry_year as varchar) || '|' || grain || '|' || cast(years_since_entry as varchar)
from {{ ref('mart_retention_cohorts') }} where retention_pct > 1 or retention_among_eligible > 1 or active_count > cohort_size
union all
select 'cohort_cell_not_observable', cast(entry_year as varchar) || '|' || cast(years_since_entry as varchar)
from {{ ref('mart_retention_cohorts') }} where entry_year + years_since_entry > (select last_observed_year from {{ ref('observation_window') }})
