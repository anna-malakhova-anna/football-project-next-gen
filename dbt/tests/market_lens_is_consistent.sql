{{ config(tags=['phase5']) }}
-- The club-market lens adds up (spec section 14): shared-market allocation weights sum to 1 per ZIP3; every participant-year's weights sum to 1; allocated participants across the US markets sum to the
-- US resolved total (and OUTSIDE_US to the rest); placed + allocated parts add up to the allocated total; per-market households add back up to the national figure; no participation rate is shown without
-- a loaded denominator; the market scorecard follows the minimum rule.
select 'zip3 weights do not sum to 1' as problem, zip3 as detail from {{ ref('club_market_map') }} group by zip3 having abs(sum(allocation_weight) - 1) > 1e-9
union all
select 'not 32 club markets plus NO_CLUB_MARKET', count(distinct club_market_id)::varchar from {{ ref('club_market_map') }} having count(distinct club_market_id) <> 33 or count(*) filter (where club_market_id = 'NO_CLUB_MARKET') = 0
union all
select 'participant-year weights do not sum to 1', participant_id || '|' || participation_year from {{ ref('int_participant_year_market') }} group by participant_id, participation_year having abs(sum(weight) - 1) > 1e-6
union all
select 'participant-years not all placed', participation_year::varchar from (
    select f.participation_year, count(*) as n, (select count(distinct m.participant_id) from {{ ref('int_participant_year_market') }} m where m.participation_year = f.participation_year) as m from {{ ref('fct_participant_year') }} f group by 1) where n <> m
union all
select 'US allocated participants differ from the US resolved total', c.participation_year::varchar
from (select participation_year, sum(participants_allocated) as a from {{ ref('mart_market_coverage') }} where club_market_id not in ('OUTSIDE_US') group by 1) c
join (select participation_year, count(*) as n from {{ ref('fct_participant_year') }} where attributed_country_code = 'US' group by 1) t using (participation_year)
where abs(c.a - t.n) > 0.1 * (select count(*) from {{ ref('mart_market_coverage') }} where participation_year = c.participation_year)
union all
select 'placed and allocated parts do not add up', club_market_id || '|' || participation_year
from {{ ref('mart_market_coverage') }} where abs(participants_allocated - participants_zip_placed - participants_unplaced_allocated - participants_outside_us) > 0.3
union all
select 'households per market do not sum to the national count', s.participation_year::varchar
from (select participation_year, sum(n) as h from {{ ref('mart_activation_funnel') }} where step_no = 3 and market_id <> 'ALL' group by 1) s
join (select participation_year, n from {{ ref('mart_activation_funnel') }} where step_no = 3 and market_id = 'ALL') n using (participation_year)
where abs(s.h - n.n) > 0.5
union all
select 'a participation rate without a denominator', club_market_id || '|' || participation_year from {{ ref('mart_market_coverage') }} where participation_rate is not null and youth_population is null
union all
select 'denominator status missing', club_market_id from {{ ref('mart_market_coverage') }} where denominator_status is null or (youth_population is null and denominator_status <> 'denominator not loaded')
union all
select 'market purpose score above a dimension score', p.club_market_id || '|' || p.season_year || '|' || p.purpose
from {{ ref('dq_scorecard_market') }} p join {{ ref('dq_scorecard_market') }} d on d.club_market_id = p.club_market_id and d.season_year = p.season_year and d.purpose = p.purpose and d.dimension <> 'PURPOSE_SCORE'
where p.dimension = 'PURPOSE_SCORE' and p.score > d.score + 0.011
union all
select 'market score out of range or grade missing', club_market_id from {{ ref('dq_scorecard_market') }} where score < 0 or score > 100 or grade is null
