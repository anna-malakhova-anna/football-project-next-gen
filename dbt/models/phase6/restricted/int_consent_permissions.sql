-- RESTRICTED (schema `phase6_restricted`). For each household (the guardian side) and purpose: is the household's contact permitted for that purpose, and why? As of the household's LAST participation year.
-- The rule that governs is the one for the MOST RESTRICTIVE child: the youngest minor in the household that year (an adult household is governed by its adult row). A message such as "your child plays in our
-- league" is about the child, so the youngest child's tier decides. A household's permission is evaluated for the GUARDIAN and is never inherited by a child; this model carries no participant column.
--   permitted = Y  only when the rules allow the purpose for that tier AND the purpose is covered: league operations by the registration itself, every other purpose by a GUARDIAN consent on record whose
--                  provenance is fully known. A blank is never a yes (the Phase 1 to 3 NULL rule): NOT_CAPTURED, DECLINED, REVOKED and INCOMPLETE provenance all give N.
--   CLUB_MARKETING reads the same status as the activation funnel (int_household_year_consent), so the two cannot disagree; the other purposes read the latest consent event that names them.
--   Unknown age uses the strictest minor row. Whether a club is a third party is NOT decided here (an open question for counsel).
with members as (

    select h.household_id, a.participant_id, a.participation_year, a.age_at_cutoff, a.age_tier, a.jurisdiction
    from {{ ref('int_household') }} h join {{ ref('int_participant_age_tier') }} a on a.participant_id = h.participant_id

),

last_year as (select household_id, max(participation_year) as y from members group by 1),

governing as (

    -- most restrictive: minors before adults, then the youngest (unknown age counts as the youngest), then a stable tie-break
    select m.household_id, l.y as as_of_year, m.age_tier as governing_tier, m.jurisdiction, coalesce(m.age_at_cutoff, 0) as governing_age,
           row_number() over (partition by m.household_id order by (m.age_tier = 'ADULT'), coalesce(m.age_at_cutoff, 0), m.participant_id) as rn
    from members m join last_year l on l.household_id = m.household_id and l.y = m.participation_year

),

g as (select * from governing where rn = 1),

purposes as (select distinct unnest(string_split(allowed_purposes, '|')) as purpose from {{ ref('age_consent_rules') }} where age_min >= {{ var('age_tier_adult_from') }}),

rule as (

    select g.household_id, g.as_of_year, g.governing_tier, g.jurisdiction, r.who_consents, r.allowed_purposes, r.prohibited_purposes
    from g join {{ ref('age_consent_rules') }} r on r.jurisdiction = g.jurisdiction and g.governing_age between r.age_min and r.age_max

),

ev as (

    select e.household_id, p.purpose, e.event_kind, e.status, e.provenance_grade,
           row_number() over (partition by e.household_id, p.purpose
                              order by coalesce(e.captured_at, make_timestamp(e.season_year, 12, 31, 0, 0, 0)) desc, (e.status = 'DENIED') desc, (e.provenance_grade <> 'KNOWN_FULL') desc) as rn
    from {{ ref('int_consent_event') }} e
    cross join unnest(e.purposes) as p(purpose)
    join g on g.household_id = e.household_id
    where e.status in ('GRANTED', 'DENIED') and coalesce(cast(e.captured_at as date), make_date(e.season_year, 12, 31)) <= make_date(g.as_of_year, 12, 31)

),

status as (

    select r.household_id, p.purpose,
           case when p.purpose = 'CLUB_MARKETING' then coalesce(y.marketing_status, 'NOT_CAPTURED')
                when e.event_kind = 'REVOCATION' then 'REVOKED'
                when e.status = 'GRANTED' and e.provenance_grade = 'KNOWN_FULL' then 'GRANTED_FULL'
                when e.status = 'GRANTED' then 'GRANTED_INCOMPLETE'
                when e.status = 'DENIED' then 'DECLINED'
                else 'NOT_CAPTURED' end                                     as consent_status
    from rule r cross join purposes p
    left join (select * from ev where rn = 1) e on e.household_id = r.household_id and e.purpose = p.purpose
    left join {{ ref('int_household_year_consent') }} y on y.household_id = r.household_id and y.participation_year = r.as_of_year

)

select
    r.household_id,
    r.as_of_year,
    s.purpose,
    r.governing_tier,
    r.jurisdiction,
    r.who_consents,
    s.consent_status,
    case when s.purpose = 'LEAGUE_OPS' then 'REGISTRATION' when s.consent_status = 'GRANTED_FULL' then 'GUARDIAN_CONSENT' else 'NONE' end as basis,
    list_contains(string_split(r.allowed_purposes, '|'), s.purpose) and not list_contains(string_split(coalesce(r.prohibited_purposes, ''), '|'), s.purpose) as rule_allows,
    case when list_contains(string_split(r.allowed_purposes, '|'), s.purpose) and not list_contains(string_split(coalesce(r.prohibited_purposes, ''), '|'), s.purpose)
              and (s.purpose = 'LEAGUE_OPS' or s.consent_status = 'GRANTED_FULL') then 'Y' else 'N' end as permitted,
    case when not (list_contains(string_split(r.allowed_purposes, '|'), s.purpose) and not list_contains(string_split(coalesce(r.prohibited_purposes, ''), '|'), s.purpose)) then 'NOT ALLOWED FOR THIS AGE TIER UNDER THE RULES'
         when s.purpose = 'LEAGUE_OPS' then 'COVERED BY REGISTRATION (not a consent)'
         when s.consent_status = 'GRANTED_FULL' then 'CONSENT ON RECORD WITH FULL PROVENANCE'
         when s.consent_status = 'GRANTED_INCOMPLETE' then 'CONSENT ON RECORD BUT PROVENANCE INCOMPLETE (not evidence)'
         when s.consent_status = 'DECLINED' then 'DECLINED'
         when s.consent_status = 'REVOKED' then 'REVOKED'
         else 'NOT CAPTURED (a blank is not a yes)' end                     as reason
from rule r join status s on s.household_id = r.household_id
