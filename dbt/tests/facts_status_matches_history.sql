{{ config(tags=['phase3']) }}
-- Status re-derived independently from the registration history must agree with fct_participant_year (rules C11-C13):
-- NEW = first valid year; RETURNING = valid last year; REACTIVATED = a gap, then back.
with yrs as (select distinct participant_id, participation_year from {{ ref('fct_registration') }} where is_valid_registration),
expected as (
    select y.participant_id, y.participation_year,
        case
            when y.participation_year = (select min(participation_year) from yrs) then 'CENSORED'
            when y.participation_year = (select min(participation_year) from yrs y2 where y2.participant_id = y.participant_id) then 'NEW'
            when exists (select 1 from yrs p where p.participant_id = y.participant_id and p.participation_year = y.participation_year - 1) then 'RETURNING'
            else 'REACTIVATED'
        end as status
    from yrs y
)
select e.participant_id, e.participation_year, e.status as expected_status, f.status as got_status
from expected e left join {{ ref('fct_participant_year') }} f using (participant_id, participation_year)
where f.status is distinct from e.status
