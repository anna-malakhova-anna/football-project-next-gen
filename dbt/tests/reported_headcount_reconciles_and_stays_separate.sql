{{ config(tags=['phase4']) }}
-- Source E invariants: the fact equals the staged, non-superseded rows; the arithmetic is repaired (headcount = girls + boys); the global reach
-- bounds are ordered; and the reported headcount is NOT inside the participant counts (the participant mart never changes with it).
select 'fact_differs_from_staging' as problem, cast(f.participation_year as varchar) as detail
from (select participation_year, sum(headcount) as h from {{ ref('fct_reported_headcount') }} group by 1) f
join (select season_year as participation_year, sum(headcount) as h from {{ ref('stg_school_headcounts') }} where not is_superseded group by 1) s
  using (participation_year)
where f.h <> s.h
union all
select 'headcount_not_girls_plus_boys', headcount_key from {{ ref('fct_reported_headcount') }} where headcount <> girls_count + boys_count
union all
select 'negative_headcount', headcount_key from {{ ref('fct_reported_headcount') }} where headcount < 0
union all
select 'reach_bounds_disordered', cast(participation_year as varchar) || '|' || country_code
from {{ ref('mart_reported_headcount') }} where combined_reach_low > combined_reach_high
union all
select 'reach_low_below_resolved_participants', cast(participation_year as varchar) || '|' || country_code
from {{ ref('mart_reported_headcount') }} where combined_reach_low < participants_low
union all
select 'overlap_exceeds_either_side', cast(participation_year as varchar) || '|' || country_code
from {{ ref('mart_reported_headcount') }} where max_overlap > reported_headcount or max_overlap > youth_participants
union all
select 'participants_include_headcount', cast(g.participation_year as varchar)
from {{ ref('mart_participation_global') }} g
join {{ ref('mart_reported_headcount') }} r on r.participation_year = g.participation_year and r.country_code = 'ALL'
where g.unique_participants >= r.participants_low + r.reported_headcount
