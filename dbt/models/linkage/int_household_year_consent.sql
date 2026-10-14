{{ config(tags=['phase5']) }}
-- RESTRICTED (schema `linkage`). Where does each household stand at the END of each participation year? One row per household and year in which it has a participant.
--   has_contact           some member's valid registration that year carries a well-formed email or a phone
--   n_events, has_known_full   consent events dated on or before Dec 31 of the year, and whether any non-revocation event is KNOWN_FULL (which wording, when, and the purpose named)
--   marketing_status      the latest CLUB_MARKETING-relevant event decides (a REVOCATION counts, and a later one wins; a denial wins a tie):
--                           (ties in time: a denial wins, then incomplete evidence wins over full: the conservative reading)
--                           GRANTED_FULL        an opt-in whose provenance is KNOWN_FULL (the household may be contacted by a club)
--                           GRANTED_INCOMPLETE  an opt-in whose provenance is not KNOWN_FULL (for example the wording names no club-marketing purpose): NOT evidence of that consent
--                           DECLINED            the parent said no
--                           REVOKED             the parent withdrew consent
--                           NOT_CAPTURED        no marketing choice was ever recorded (a blank is not a no)
-- A consent for league operations or league communications never produces GRANTED_*: purpose limitation.
with years as (select distinct participation_year as y from {{ ref('fct_participant_year') }}),

members as (

    select distinct h.household_id, f.participation_year as y
    from {{ ref('fct_participant_year') }} f join {{ ref('int_household') }} h on h.participant_id = f.participant_id

),

contact as (

    select h.household_id, f.participation_year as y,
           bool_or(regexp_matches(u.contact_email, '^[^@\s]+@[^@\s]+\.[a-z]{2,}$') or u.contact_phone is not null) as has_contact
    from {{ ref('fct_registration') }} f
    join {{ ref('int_registrations_unioned') }} u on u.registration_key = f.registration_key
    join {{ ref('int_household') }} h on h.participant_id = f.participant_id
    where f.is_valid_registration group by 1, 2

),

ev as (

    select e.*, y.y
    from {{ ref('int_consent_event') }} e cross join years y
    where coalesce(cast(e.captured_at as date), make_date(e.season_year, 12, 31)) <= make_date(y.y, 12, 31)

),

marketing as (

    select household_id, y, event_kind, status, provenance_grade,
           row_number() over (partition by household_id, y order by coalesce(captured_at, make_timestamp(season_year, 12, 31, 0, 0, 0)) desc, (status = 'DENIED') desc, (provenance_grade <> 'KNOWN_FULL') desc) as rn
    from ev where (event_kind = 'MARKETING_OPT_IN') or event_kind = 'REVOCATION'

),

agg as (

    select household_id, y, count(*) filter (where event_kind <> 'REVOCATION') as n_events,
           bool_or(provenance_grade = 'KNOWN_FULL') filter (where event_kind <> 'REVOCATION') as has_known_full
    from ev group by 1, 2

)

select
    m.household_id, m.y as participation_year,
    coalesce(c.has_contact, false)                                          as has_contact,
    coalesce(a.n_events, 0)                                                 as n_events,
    coalesce(a.has_known_full, false)                                       as has_known_full,
    case when k.event_kind = 'REVOCATION' then 'REVOKED'
         when k.status = 'GRANTED' and k.provenance_grade = 'KNOWN_FULL' then 'GRANTED_FULL'
         when k.status = 'GRANTED' then 'GRANTED_INCOMPLETE'
         when k.status = 'DENIED' then 'DECLINED'
         else 'NOT_CAPTURED' end                                            as marketing_status
from members m
left join contact c using (household_id, y)
left join agg a using (household_id, y)
left join (select * from marketing where rn = 1) k using (household_id, y)
