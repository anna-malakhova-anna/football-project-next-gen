{{ config(tags=['phase3']) }}
-- Reporting periods: years are contiguous and cover every season year in the data; every cutoff date is the
-- project age cutoff (var age_cutoff_month_day) of its year; seasons sit inside their year; each year has spring and fall.
select 'cutoff_not_project_cutoff' as problem, period_id as detail
from {{ ref('reporting_periods') }}
where cutoff_date <> make_date(participation_year, split_part('{{ var("age_cutoff_month_day") }}', '-', 1)::int, split_part('{{ var("age_cutoff_month_day") }}', '-', 2)::int)
union all
select 'period_outside_its_year', period_id from {{ ref('reporting_periods') }}
where extract(year from start_date) <> participation_year or extract(year from end_date) <> participation_year or start_date > end_date
union all
select 'year_missing_a_season', 'Y' || y.participation_year
from (select distinct participation_year from {{ ref('reporting_periods') }}) y
where (select count(*) from {{ ref('reporting_periods') }} p where p.participation_year = y.participation_year and p.period_type = 'US_SEASON') <> 2
   or (select count(*) from {{ ref('reporting_periods') }} p where p.participation_year = y.participation_year and p.period_type = 'YEAR') <> 1
union all
select 'years_not_contiguous', cast(max(participation_year) as varchar)
from {{ ref('reporting_periods') }} where period_type = 'YEAR'
having max(participation_year) - min(participation_year) + 1 <> count(*)
union all
select 'data_year_without_period', cast(i.season_year as varchar)
from (select distinct season_year from {{ ref('int_registrations_unioned') }}) i
left join {{ ref('reporting_periods') }} p on p.participation_year = i.season_year and p.period_type = 'YEAR'
where p.period_id is null
