{{ config(tags=['phase3']) }}
-- Each grouping set partitions the participants, so within one (year, grouping_id) the cells sum to the global unique
-- participants; the year-only set is the global count; youth and youth-girls totals match the fact table; shares are in [0, 1].
select 'grouping_set_does_not_sum_to_global' as problem, s.participation_year, s.grouping_id, sum(s.participants) as got, g.unique_participants as expected
from {{ ref('mart_participation_segments') }} s join {{ ref('mart_participation_global') }} g using (participation_year)
group by s.participation_year, s.grouping_id, g.unique_participants
having sum(s.participants) <> g.unique_participants
union all
select 'youth_total_differs', f.participation_year, null, s.youth_participants, f.n
from (select participation_year, count(*) filter (where is_youth) as n from {{ ref('fct_participant_year') }} group by 1) f
join {{ ref('mart_participation_segments') }} s on s.participation_year = f.participation_year and s.grouping_id = 31
where s.youth_participants <> f.n
union all
select 'youth_girls_total_differs', f.participation_year, null, s.youth_girls_participants, f.n
from (select participation_year, count(*) filter (where is_youth and sex = 'F') as n from {{ ref('fct_participant_year') }} group by 1) f
join {{ ref('mart_participation_segments') }} s on s.participation_year = f.participation_year and s.grouping_id = 31
where s.youth_girls_participants <> f.n
union all
select 'share_out_of_range', participation_year, grouping_id, girls_share_of_youth, null
from {{ ref('mart_participation_segments') }} where girls_share_of_youth < 0 or girls_share_of_youth > 1
