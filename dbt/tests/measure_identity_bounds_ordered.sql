{{ config(tags=['phase3']) }}
-- low <= point <= high; the point estimate is the reported number (global unique participants); the country rows
-- (attributed view) sum to the global row for every bound; the share high-confidence is a proportion.
select 'bounds_not_ordered' as problem, participation_year, grain, country_code, participants_low as low, participants_point as point, participants_high as high
from {{ ref('mart_identity_uncertainty') }}
where participants_low > participants_point or participants_point > participants_high
union all
select 'point_not_reported_number', u.participation_year, 'GLOBAL', null, null, u.participants_point, g.unique_participants
from {{ ref('mart_identity_uncertainty') }} u join {{ ref('mart_participation_global') }} g using (participation_year)
where u.grain = 'GLOBAL' and u.participants_point <> g.unique_participants
union all
select 'country_rows_do_not_sum_to_global_' || b.bound, g.participation_year, 'COUNTRY', null,
       case b.bound when 'low' then c.low end, case b.bound when 'point' then c.point end, case b.bound when 'high' then c.high end
from (select unnest(['low', 'point', 'high']) as bound) b
cross join {{ ref('mart_identity_uncertainty') }} g
join (select participation_year, sum(participants_low) low, sum(participants_point) point, sum(participants_high) high
      from {{ ref('mart_identity_uncertainty') }} where grain = 'COUNTRY' group by 1) c using (participation_year)
where g.grain = 'GLOBAL'
  and ((b.bound = 'low' and c.low <> g.participants_low) or (b.bound = 'point' and c.point <> g.participants_point)
       or (b.bound = 'high' and c.high <> g.participants_high))
union all
select 'share_out_of_range', participation_year, grain, country_code, null, pct_participants_high_confidence, null
from {{ ref('mart_identity_uncertainty') }} where pct_participants_high_confidence < 0 or pct_participants_high_confidence > 1
