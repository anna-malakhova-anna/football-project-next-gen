{{ config(tags=['phase4']) }}
-- The fan funnel: every stage is at most the stage before it (households >= linked >= contactable >= active >= monetized >= retained); UNLINKED households never get past the first stage and are
-- present as their own line; for each cohort, market type and segment the status rows add up to the ALL row; the step rates are proportions; and the 'ALL' market-type rows are the sum of team and non-team.
select 'stage_larger_than_the_one_before' as problem, cast(cohort_year as varchar) || '|' || market_type || '|' || segment || '|' || fan_status as detail
from {{ ref('mart_fan_funnel') }}
where linked_households > households or contactable_households > linked_households or active_households > contactable_households
   or monetized_households > active_households or retained_households > monetized_households
union all
select 'unlinked_household_in_a_later_stage', cast(cohort_year as varchar) || '|' || segment
from {{ ref('mart_fan_funnel') }} where fan_status = 'UNLINKED' and linked_households > 0
union all
select 'unlinked_line_missing', cast(cohort_year as varchar)
from (select distinct cohort_year from {{ ref('mart_fan_funnel') }}) y
where not exists (select 1 from {{ ref('mart_fan_funnel') }} f where f.cohort_year = y.cohort_year and f.fan_status = 'UNLINKED' and f.segment = 'ALL' and f.market_type = 'ALL' and f.households > 0)
union all
select 'status_rows_do_not_add_up_to_all', cast(cohort_year as varchar) || '|' || market_type || '|' || segment
from {{ ref('mart_fan_funnel') }}
group by cohort_year, market_type, segment
having sum(households) filter (where fan_status <> 'ALL') <> sum(households) filter (where fan_status = 'ALL')
union all
select 'market_types_do_not_add_up_to_all', cast(cohort_year as varchar) || '|' || segment || '|' || fan_status
from {{ ref('mart_fan_funnel') }}
group by cohort_year, segment, fan_status
having sum(households) filter (where market_type <> 'ALL') <> sum(households) filter (where market_type = 'ALL')
union all
select 'rate_out_of_range', cast(cohort_year as varchar) || '|' || market_type || '|' || segment || '|' || fan_status
from {{ ref('mart_fan_funnel') }}
where link_rate not between 0 and 1 or contactable_rate not between 0 and 1 or active_rate not between 0 and 1 or monetized_rate not between 0 and 1 or retained_rate not between 0 and 1
union all
select 'households_differ_from_the_status_table', cast(n as varchar) || ' vs ' || cast(s as varchar)
from (select (select sum(households) from {{ ref('mart_fan_funnel') }} where segment = 'ALL' and market_type = 'ALL' and fan_status = 'ALL') as n,
             (select count(*) from {{ ref('fct_household_fan_status') }}) as s) where n <> s
