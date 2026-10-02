{{ config(tags=['phase3']) }}
-- The scorecard covers the full KPI tree for every year (including all five data-trust KPIs), every kpi_id is in the
-- metric catalog, the headline values equal the marts they come from, bounds bracket the value, and the censoring rule
-- shows up as NULL (not zero) in the first year.
with expected(kpi_id) as (
    values ('unique_participants'), ('new_participants'), ('returning_participants'), ('reactivated_participants'),
           ('retention_rate'), ('youth_girls_participants'), ('girls_share_of_youth'), ('international_participants'),
           ('countries_with_participants'), ('multi_org_participants'), ('registrations_per_participant'),
           ('identity_range_pct'), ('pct_participants_high_confidence'), ('open_review_items'), ('sources_onboarded'),
           ('sources_known'), ('pct_registrations_failing_dq')
),
years as (select distinct participation_year from {{ ref('mart_participation_global') }})
select 'missing_kpi' as problem, y.participation_year, e.kpi_id as detail
from years y cross join expected e
left join {{ ref('mart_kpi_scorecard') }} s on s.participation_year = y.participation_year and s.kpi_id = e.kpi_id
where s.kpi_id is null
union all
select 'kpi_not_in_catalog', participation_year, kpi_id
from {{ ref('mart_kpi_scorecard') }} where kpi_id not in (select metric_id from {{ ref('metric_catalog') }})
union all
select 'north_star_differs_from_global_mart', s.participation_year, cast(s.value as varchar)
from {{ ref('mart_kpi_scorecard') }} s join {{ ref('mart_participation_global') }} g using (participation_year)
where s.kpi_id = 'unique_participants' and s.value <> g.unique_participants
union all
select 'bounds_do_not_bracket_value', participation_year, kpi_id
from {{ ref('mart_kpi_scorecard') }} where low is not null and (low > value or value > high)
union all
select 'first_year_growth_kpi_not_null', participation_year, kpi_id
from {{ ref('mart_kpi_scorecard') }}
where participation_year = (select min(participation_year) from years)
  and kpi_id in ('new_participants', 'returning_participants', 'reactivated_participants', 'retention_rate') and value is not null
union all
select 'one_methodology_version', null, cast(count(distinct methodology_version) as varchar)
from {{ ref('mart_kpi_scorecard') }} having count(distinct methodology_version) <> 1
