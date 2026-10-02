{{ config(tags=['phase3']) }}
-- new + returning + reactivated + censored = unique participants every year, and no first-year participant is new or
-- returning (the censoring rule); retention is returning / prior-year participants.
select participation_year, unique_participants,
       new_participants + returning_participants + reactivated_participants + censored_participants as status_total
from {{ ref('mart_participation_global') }}
where unique_participants <> new_participants + returning_participants + reactivated_participants + censored_participants
union all
select participation_year, null, new_participants + returning_participants
from {{ ref('mart_participation_global') }}
where participation_year = (select min(participation_year) from {{ ref('mart_participation_global') }})
  and (new_participants > 0 or returning_participants > 0 or reactivated_participants > 0 or retention_rate is not null)
union all
select g.participation_year, null, null
from {{ ref('mart_participation_global') }} g
join {{ ref('mart_participation_global') }} p on p.participation_year = g.participation_year - 1
where g.retention_rate is distinct from round(g.returning_participants * 1.0 / p.unique_participants, 4)
