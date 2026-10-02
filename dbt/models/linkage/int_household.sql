-- RESTRICTED (schema `linkage`). Households as observed in registrations: participants who share a guardian contact (normalized email or phone).
--   * a MINOR joins the households of everyone who shares a guardian email or phone with them (siblings, twins; an email change mid-way is bridged
--     by a shared phone, and the reverse)
--   * an ADULT player is a household of one: their own contact is theirs, not a guardian's
--   * GUARD: a contact value shared by more than `household_max_members` participants is a shared inbox or a data-entry accident, not a family;
--     it creates no edges and is listed in int_household_guarded_contacts
-- Contacts come from valid registrations only. No name or date of birth is used: this is a household of contacts, not an identity decision.
{% set max_members = 6 %}
with reg as (

    select b.participant_id, u.contact_email, u.contact_phone, u.is_minor
    from {{ ref('bridge_registration_participant') }} b
    join {{ ref('int_registrations_unioned') }} u on u.registration_key = b.registration_key
    join {{ ref('fct_registration') }} f on f.registration_key = b.registration_key
    where f.is_valid_registration

),

people as (

    select participant_id, bool_or(is_minor) as is_minor from reg group by 1

),

contacts as (

    select distinct participant_id, 'EMAIL' as contact_type, contact_email as contact_value from reg where contact_email is not null
    union
    select distinct participant_id, 'PHONE', contact_phone from reg where contact_phone is not null

),

minor_contacts as (

    select c.* from contacts c join people p using (participant_id) where p.is_minor

),

sizes as (

    select contact_type, contact_value, count(distinct participant_id) as n_participants from minor_contacts group by 1, 2

),

usable as (

    select m.* from minor_contacts m join sizes s using (contact_type, contact_value) where s.n_participants <= {{ max_members }}

),

nodes as (select participant_id as node from people where is_minor),

edges as (

    select a.participant_id as a, b.participant_id as b
    from usable a join usable b
      on a.contact_type = b.contact_type and a.contact_value = b.contact_value and a.participant_id < b.participant_id

),

cc as {{ connected_components('nodes', 'edges') }},

assigned as (

    select node as participant_id, 'hh-' || md5(cluster_id) as household_id, false as is_adult_household from cc
    union all
    select participant_id, 'hh-' || md5(participant_id), true from people where not is_minor

)

select
    a.participant_id,
    a.household_id,
    a.is_adult_household,
    count(*) over (partition by a.household_id)                             as household_participants
from assigned a
