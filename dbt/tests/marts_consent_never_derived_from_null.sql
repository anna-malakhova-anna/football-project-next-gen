{{ config(tags=['phase2']) }}
-- Consent survivorship: a participant has a consent value only if one of its OWN registrations captured one.
-- Returns participants with TRUE/FALSE consent although every one of their registrations has NULL for it, or whose
-- value is not the most recent captured value among their own registrations.
with regs as (

    select b.participant_id, i.consent_photo, i.consent_marketing, i.season_year,
           i.season_year * 10 + case i.season_term when 'FALL' then 2 else 1 end as season_order, i.registered_at
    from {{ ref('bridge_registration_participant') }} b
    join {{ ref('idr_input_records') }} i on i.match_record_id = b.match_record_id
    where b.registration_key = b.match_record_id

),

own as (

    select participant_id,
           count(consent_photo) as photo_captured, count(consent_marketing) as marketing_captured,
           count(*) filter (where consent_photo) as photo_true, count(*) filter (where consent_photo is false) as photo_false,
           count(*) filter (where consent_marketing) as marketing_true, count(*) filter (where consent_marketing is false) as marketing_false
    from regs group by 1

)

select d.participant_id, 'photo' as field, d.consent_photo as value
from {{ ref('dim_participant') }} d join own o using (participant_id)
where d.consent_photo is not null and (o.photo_captured = 0
      or (d.consent_photo and o.photo_true = 0) or (not d.consent_photo and o.photo_false = 0))
union all
select d.participant_id, 'marketing', d.consent_marketing
from {{ ref('dim_participant') }} d join own o using (participant_id)
where d.consent_marketing is not null and (o.marketing_captured = 0
      or (d.consent_marketing and o.marketing_true = 0) or (not d.consent_marketing and o.marketing_false = 0))
union all
select d.participant_id, 'photo_should_be_null', null
from {{ ref('dim_participant') }} d join own o using (participant_id)
where d.consent_photo is null and o.photo_captured > 0
union all
select d.participant_id, 'marketing_should_be_null', null
from {{ ref('dim_participant') }} d join own o using (participant_id)
where d.consent_marketing is null and o.marketing_captured > 0
