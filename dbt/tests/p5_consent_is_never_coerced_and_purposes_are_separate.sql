{{ config(tags=['phase5']) }}
-- (1) A blank marketing box is NOT captured: it produces no event, so no MARKETING_OPT_IN event may exist for a record whose marketing value is NULL, and none may be DENIED because of a blank.
-- (2) Only a MARKETING_OPT_IN event can carry NFL_CLUB_MARKETING: a consent / waiver event never does (purpose limitation).
-- (3) A household is eligible only if its latest NFL_CLUB_MARKETING status is GRANTED.
select 'marketing event for a blank marketing value' as problem, e.consent_event_id as id
from {{ ref('p5_consent_event') }} e
join {{ ref('stg_p5_registrations') }} s on s.feed = e.source_feed and s.source_record_id = e.source_record_id
where e.event_kind = 'MARKETING_OPT_IN' and s.consent_marketing is null
union all
select 'consent event grants club marketing', consent_event_id
from {{ ref('p5_consent_event') }} where event_kind = 'OPERATIONS_CONSENT' and list_contains(purposes, 'NFL_CLUB_MARKETING')
union all
select 'eligible without a granted marketing status', a.household_id
from {{ ref('p5_household_activation') }} a
left join {{ ref('p5_household_purpose_status') }} p on p.household_id = a.household_id and p.purpose = 'NFL_CLUB_MARKETING'
where a.eligible_for_club_activation and coalesce(p.status, '') <> 'GRANTED'
