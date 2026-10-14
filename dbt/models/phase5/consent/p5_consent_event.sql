-- RESTRICTED. One row per consent event captured on a registration, keyed by household (parent side) and never by child.
--   OPERATIONS_CONSENT  the consent / waiver / terms captured with the registration: purposes read through p5_consent_wording_map (an ASSUMPTION per row there)
--   MARKETING_OPT_IN    an explicit marketing box (matrix_export, vendor_reg_a). Blank = not captured = NO EVENT, never FALSE. Only this kind can grant NFL_CLUB_MARKETING.
-- Provenance, scored per event, asks three questions: WHAT did the parent agree to, WHEN, on WHICH wording. Method is recorded when a feed says (none does).
--   what_known    the purposes are known: the wording is in the map, or the event is an explicit marketing box
--   when_known    the event has a timestamp
--   which_known   the event names a wording version, or the captured string is the wording itself (p5_consent_wording_map.wording_is_full_text)
--   REVOCATION          the parent withdrew consent (raw.p5_revocations): DENIED for every purpose
-- household_id is NULL for an event on a record with no usable email: the consent exists but belongs to nobody we can contact.
with recs as (

    select s.*, rp.contact_email
    from {{ ref('stg_p5_registrations') }} s
    join {{ ref('p5_record_person') }} rp on rp.feed = s.feed and rp.source_record_id = s.source_record_id
    where s.is_flag and not s.is_exact_duplicate_row

),

ops as (

    select
        r.feed, r.source_record_id, 'OPERATIONS_CONSENT' as event_kind, r.contact_email, r.registered_at, r.season_year,
        case when w.meaning is null then 'UNKNOWN' else w.meaning end                                       as status,
        string_split(w.purposes_covered, '|')                                                               as purposes,
        r.consent_text                                                                                      as wording_text,
        r.consent_version                                                                                   as wording_version,
        r.consent_ts                                                                                        as event_ts,
        w.meaning is not null                                                                               as what_known,
        coalesce(w.wording_is_full_text, false)                                                             as wording_is_full_text
    from recs r
    left join {{ ref('p5_consent_wording_map') }} w
        on w.source_feed = r.feed and lower(w.raw_value) = lower(trim(r.consent_text))
    where r.has_consent_record and (nullif(trim(r.consent_text), '') is not null or r.consent_ts is not null or r.consent_version is not null)

),

marketing as (

    select
        r.feed, r.source_record_id, 'MARKETING_OPT_IN', r.contact_email, r.registered_at, r.season_year,
        case when r.consent_marketing then 'GRANTED' else 'DENIED' end,
        ['NFL_CLUB_MARKETING'],
        cast(null as varchar),
        r.consent_version,
        r.consent_ts,
        true,
        false
    from recs r
    where r.consent_marketing is not null

),

revocations as (

    -- a parent withdrew consent: a DENIED event for every purpose at the time of the request. Provenance is deliberately NOT "fully known" (a revocation names no wording), so
    -- it never counts toward the funnel's known-provenance stage; because the latest event decides, it overrides any earlier grant.
    select
        'revocation' as feed, cast(null as varchar) as source_record_id, 'REVOCATION' as event_kind, {{ normalize_email('parent_email') }} as contact_email,
        try_cast(revoked_at as timestamp) as registered_at, cast(null as integer) as season_year,
        'DENIED' as status, (select list(purpose_id order by purpose_id) from {{ ref('p5_consent_purposes') }}) as purposes,
        cast(null as varchar) as wording_text, cast(null as varchar) as wording_version, try_cast(revoked_at as timestamp) as event_ts,
        true as what_known, false as wording_is_full_text
    from {{ source('raw_p5', 'p5_revocations') }}

),

unioned as (select * from ops union all select * from marketing union all select * from revocations)

select
    md5(u.feed || '|' || coalesce(u.source_record_id, u.contact_email || '|' || u.registered_at::varchar) || '|' || u.event_kind)                                         as consent_event_id,
    h.household_id,
    u.feed                                                                                                  as source_feed,
    u.source_record_id,
    u.event_kind,
    u.status,
    u.purposes,
    u.wording_text,
    u.wording_version,
    u.event_ts,
    u.registered_at,
    u.season_year,
    cast(null as varchar)                                                                                   as method,
    u.what_known,
    u.event_ts is not null                                                                                  as when_known,
    (u.wording_version is not null or u.wording_is_full_text)                                               as which_known,
    (u.what_known::integer + (u.event_ts is not null)::integer + (u.wording_version is not null or u.wording_is_full_text)::integer) as provenance_score,
    u.what_known and u.event_ts is not null and (u.wording_version is not null or u.wording_is_full_text)   as provenance_known
from unioned u
left join {{ ref('p5_household') }} h on h.contact_email = u.contact_email
