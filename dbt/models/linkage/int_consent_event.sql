{{ config(tags=['phase5']) }}
-- depends_on: {{ ref('p5_params') }}
-- depends_on: {{ ref('consent_purposes') }}
-- RESTRICTED (schema `linkage`). One row per consent event captured on a registration of the modelled sources, keyed by HOUSEHOLD (the parent side), with the source record kept for audit.
--   FORM_ACCEPTANCE  the parent accepted the registration form: grants the form's bundled purposes (LEAGUE_OPS, LEAGUE_COMMS where the wording version names them). If the wording is unknown, WHAT was
--                    accepted is unknown: status UNKNOWN, no purposes. It NEVER grants CLUB_MARKETING or PHOTO_MEDIA, which have their own boxes.
--   PHOTO_OPT         the photo / media box: GRANTED or DENIED for PHOTO_MEDIA. A blank is no event (not captured, never FALSE).
--   MARKETING_OPT_IN  the marketing box: GRANTED or DENIED for CLUB_MARKETING. A blank is no event. A consent for league emails or a waiver is NOT this.
--   REVOCATION        the parent withdrew consent (raw.p5_revocations, matched through the registration contact): DENIED for every purpose from that moment.
-- Provenance, per event, asks three questions: which wording version (consent_text_version, or UNKNOWN), when (captured_at: the registration time, under the configured assumption that a form carries its
-- consent in the same submission; Canada's own consent timestamp IS its registration time) and whether the wording names the event's purpose. KNOWN_FULL = all three; KNOWN_PARTIAL = at least one;
-- UNKNOWN = none. method is not captured by any source: UNKNOWN. A marketing opt-in on a wording version with no club-marketing purpose is therefore at best KNOWN_PARTIAL: it is not evidence of that consent.
with versions as (select consent_text_version, string_split(purposes, '|') as purposes from {{ ref('consent_text_versions') }}),

regs as (

    select
        h.household_id, f.participation_year as season_year, u.registration_key, u.source_system, u.source_record_id, u.registered_at,
        u.consent_text_version, u.consent_photo, u.consent_marketing,
        (u.source_system = 'CA_CLUB' and not list_contains(u.dq_flags, 'missing_consents_object')) as ca_consents_present,
        coalesce(v.purposes, []) as form_purposes
    from {{ ref('int_registrations_unioned') }} u
    join {{ ref('fct_registration') }} f on f.registration_key = u.registration_key and f.is_valid_registration
    join {{ ref('int_household') }} h on h.participant_id = f.participant_id
    left join versions v on v.consent_text_version = u.consent_text_version
    where not coalesce(u.is_exact_duplicate, false)

),

stamped as (

    select *,
           case when lower({{ p5_param('consent_time_from_registration') }}::varchar) = 'true' or source_system = 'CA_CLUB' then registered_at end as captured_at
    from regs

),

events as (

    -- the form was accepted
    select household_id, season_year, registration_key, source_system, source_record_id, 'FORM_ACCEPTANCE' as event_kind,
           case when consent_text_version is null then 'UNKNOWN' else 'GRANTED' end as status,
           list_filter(form_purposes, p -> p in ('LEAGUE_OPS', 'LEAGUE_COMMS')) as purposes,
           consent_text_version, captured_at,
           len(list_filter(form_purposes, p -> p in ('LEAGUE_OPS', 'LEAGUE_COMMS'))) > 0 as purpose_named
    from stamped
    where consent_text_version is not null or ca_consents_present or consent_photo is not null or consent_marketing is not null
    union all
    select household_id, season_year, registration_key, source_system, source_record_id, 'PHOTO_OPT',
           case when consent_photo then 'GRANTED' else 'DENIED' end, ['PHOTO_MEDIA'], consent_text_version, captured_at, list_contains(form_purposes, 'PHOTO_MEDIA')
    from stamped where consent_photo is not null
    union all
    select household_id, season_year, registration_key, source_system, source_record_id, 'MARKETING_OPT_IN',
           case when consent_marketing then 'GRANTED' else 'DENIED' end, ['CLUB_MARKETING'], consent_text_version, captured_at, list_contains(form_purposes, 'CLUB_MARKETING')
    from stamped where consent_marketing is not null

),

revoked as (

    -- the parent's contact email on a registration identifies the household; one event per household per request
    select distinct h.household_id, extract(year from try_cast(r.revoked_at as timestamp))::integer as season_year, try_cast(r.revoked_at as timestamp) as captured_at
    from {{ source('raw_p5', 'p5_revocations') }} r
    join {{ ref('int_registrations_unioned') }} u on u.contact_email = {{ normalize_email('r.parent_email') }}
    join {{ ref('bridge_registration_participant') }} b on b.registration_key = u.registration_key
    join {{ ref('int_household') }} h on h.participant_id = b.participant_id

),

unioned as (

    select household_id, season_year, registration_key, source_system, source_record_id, event_kind, status, purposes, consent_text_version, captured_at, purpose_named from events
    union all
    select household_id, season_year, cast(null as varchar), cast(null as varchar), cast(null as varchar), 'REVOCATION', 'DENIED',
           (select list(purpose_id order by purpose_id) from {{ ref('consent_purposes') }}), cast(null as varchar), captured_at, true
    from revoked

)

select
    registration_key,
    md5(coalesce(source_system, 'revocation') || '|' || coalesce(source_record_id, household_id || '|' || captured_at::varchar) || '|' || event_kind)  as consent_event_id,
    household_id, season_year, source_system, source_record_id, event_kind, status, purposes,
    coalesce(consent_text_version, 'UNKNOWN')                               as consent_text_version,
    captured_at,
    'UNKNOWN'                                                               as method,
    consent_text_version is not null                                        as has_version,
    captured_at is not null                                                 as has_timestamp,
    purpose_named                                                           as has_purpose_coverage,
    case when event_kind = 'REVOCATION' then 'KNOWN_PARTIAL'
         when consent_text_version is not null and captured_at is not null and purpose_named then 'KNOWN_FULL'
         when consent_text_version is not null or captured_at is not null or purpose_named then 'KNOWN_PARTIAL'
         else 'UNKNOWN' end                                                 as provenance_grade
from unioned
