{{ config(tags=['phase6']) }}
-- Phase 6: a range on a goal-scorecard row must hold its own point (low <= value <= high), and no row may show a range that belongs to another measure.
-- The counted number of players in club markets has NO range; the estimated total's range is the club-market coverage interval (counted plus the estimate for leagues that sent no file), rounded the same way.
with s as (select * from {{ ref('mart_goal_scorecard') }}),

cov as (

    select participation_year, round(sum(interval_low), -1) as lo, round(sum(interval_high), -1) as hi
    from {{ ref('mart_market_coverage') }}
    where regexp_matches(club_market_id, '^CM-') and participants_allocated >= {{ privacy_param('k_min') }} group by 1

)

select kpi_id as detail, 'the point is outside its own range' as problem
from s where value_low is not null and value_high is not null and not (value_low <= value and value <= value_high)
union all
select kpi_id, 'the counted players in club markets carry a range' from s where kpi_id = 'market_participants_with_coverage' and (value_low is not null or value_high is not null)
union all
select s.kpi_id, 'the estimated total shows a range that is not the coverage interval'
from s left join cov on cov.participation_year = s.year
where s.kpi_id = 'market_participants_estimated_total' and (cov.lo is distinct from s.value_low or cov.hi is distinct from s.value_high)
