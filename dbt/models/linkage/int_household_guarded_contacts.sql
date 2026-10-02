-- RESTRICTED (schema `linkage`). Guardian contacts shared by more than six participants: never used to form a household.
-- Listed so a reviewer can see what the guard excluded. Counts only, no values: the contact itself is not needed to review the guard.
select contact_type, count(*) as guarded_contacts, max(n_participants) as largest_group
from (
    select contact_type, contact_value, count(distinct participant_id) as n_participants
    from (
        select b.participant_id, 'EMAIL' as contact_type, u.contact_email as contact_value
        from {{ ref('bridge_registration_participant') }} b join {{ ref('int_registrations_unioned') }} u using (registration_key)
        where u.is_minor and u.contact_email is not null
        union
        select b.participant_id, 'PHONE', u.contact_phone
        from {{ ref('bridge_registration_participant') }} b join {{ ref('int_registrations_unioned') }} u using (registration_key)
        where u.is_minor and u.contact_phone is not null
    ) group by 1, 2
) where n_participants > 6
group by 1
