{{ config(tags=['phase3']) }}
-- The data covers exactly the configured observation window: its first year is first_observed_year (the left-censored
-- year, from config seasons.first_observed_year) and its last is last_observed_year; no registration lies outside it, and
-- the facts have a row for every year in the window.
select 'first_year_differs' as problem, cast(min(participation_year) as varchar) as got, cast(max(w.first_observed_year) as varchar) as expected
from {{ ref('fct_participant_year') }} cross join {{ ref('observation_window') }} w
having min(participation_year) <> max(w.first_observed_year)
union all
select 'last_year_differs', cast(max(participation_year) as varchar), cast(max(w.last_observed_year) as varchar)
from {{ ref('fct_participant_year') }} cross join {{ ref('observation_window') }} w
having max(participation_year) <> max(w.last_observed_year)
union all
select 'registration_outside_window', cast(count(*) as varchar), '0'
from {{ ref('fct_registration') }} f cross join {{ ref('observation_window') }} w
where f.participation_year < w.first_observed_year or f.participation_year > w.last_observed_year
having count(*) > 0
union all
select 'year_without_facts', cast(p.participation_year as varchar), null
from {{ ref('reporting_periods') }} p
left join (select distinct participation_year from {{ ref('fct_participant_year') }}) f using (participation_year)
where p.period_type = 'YEAR' and f.participation_year is null
