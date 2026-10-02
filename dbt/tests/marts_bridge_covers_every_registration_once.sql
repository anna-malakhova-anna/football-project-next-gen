{{ config(tags=['phase2']) }}
-- Every registration maps to exactly one participant, and the bridge has exactly as many rows as the unioned model.
select 'row_count_differs' as problem, (select count(*) from {{ ref('bridge_registration_participant') }}) as bridge_rows,
       (select count(*) from {{ ref('int_registrations_unioned') }}) as unioned_rows
where (select count(*) from {{ ref('bridge_registration_participant') }}) <> (select count(*) from {{ ref('int_registrations_unioned') }})
union all
select 'registration_with_two_participants', count(*), null
from (select registration_key from {{ ref('bridge_registration_participant') }} group by 1 having count(distinct participant_id) > 1)
having count(*) > 0
union all
select 'participant_without_dim_row', count(*), null
from (select distinct participant_id from {{ ref('bridge_registration_participant') }}) b
left join {{ ref('dim_participant') }} d using (participant_id) where d.participant_id is null
having count(*) > 0
