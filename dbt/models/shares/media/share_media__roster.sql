-- MEDIA share: a photo / video CLEARANCE roster. Only participants whose most recent captured photo consent is TRUE appear;
-- the list means "cleared". Anyone absent is NOT cleared, including everyone whose consent is NULL (not captured) or FALSE.
-- Participants in a cluster with an open integrity issue are excluded: their consent may belong to someone else.
-- One row per participant x organization x season. Name, organization and season only.
select distinct
    d.first_name,
    d.last_name,
    f.organization_id,
    r.organization_name,
    f.participation_year                                                    as season_year,
    f.season_term,
    true                                                                    as consent_photo
from {{ ref('fct_registration') }} f
join {{ ref('dim_participant') }} d on d.participant_id = f.participant_id
join {{ ref('int_registrations_unioned') }} r on r.registration_key = f.registration_key
where f.is_valid_registration
  and d.consent_photo is true
  and not d.has_open_integrity_issue
