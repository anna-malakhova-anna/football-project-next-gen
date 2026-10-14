{{ config(tags=['phase5']) }}
-- Purpose limitation, re-derived independently (spec section 8): a contact captured only for parental consent is not a marketing opt-in.
--  (1) only a MARKETING_OPT_IN or a REVOCATION event may name CLUB_MARKETING, and a form acceptance never grants it
--  (2) a blank marketing value produces no event (not captured is not FALSE)
--  (3) a household with no MARKETING_OPT_IN event is never GRANTED_* (league-communications consent does not make it one)
--  (4) the national count of households consenting to CLUB_MARKETING in the funnel equals an independent count: households whose latest relevant event (opt-in, or a revocation, up to Dec 31 of the
--      year) is a GRANTED opt-in with KNOWN_FULL provenance, among households with a valid contact and a KNOWN_FULL event
--      (the latest event wins; on a tie in time a denial wins, as in int_household_year_consent)
--  (5) no GRANTED_FULL household has a revocation dated on or before the year end
select 'a non-marketing event names CLUB_MARKETING' as problem, event_kind as detail from {{ ref('int_consent_event') }}
where list_contains(purposes, 'CLUB_MARKETING') and event_kind not in ('MARKETING_OPT_IN', 'REVOCATION')
union all
select 'a form acceptance grants club marketing or photo', consent_event_id from {{ ref('int_consent_event') }}
where event_kind = 'FORM_ACCEPTANCE' and (list_contains(purposes, 'CLUB_MARKETING') or list_contains(purposes, 'PHOTO_MEDIA'))
union all
select 'marketing event for a blank marketing value', e.consent_event_id
from {{ ref('int_consent_event') }} e join {{ ref('int_registrations_unioned') }} u on u.registration_key = e.registration_key
where e.event_kind = 'MARKETING_OPT_IN' and u.consent_marketing is null
union all
select 'household granted without a marketing opt-in event', s.household_id || '|' || s.participation_year
from {{ ref('int_household_year_consent') }} s
where s.marketing_status in ('GRANTED_FULL', 'GRANTED_INCOMPLETE')
  and not exists (select 1 from {{ ref('int_consent_event') }} e where e.household_id = s.household_id and e.event_kind = 'MARKETING_OPT_IN' and e.status = 'GRANTED')
union all
select 'revoked household still granted', s.household_id || '|' || s.participation_year
from {{ ref('int_household_year_consent') }} s
where s.marketing_status = 'GRANTED_FULL'
  and exists (select 1 from {{ ref('int_consent_event') }} e where e.household_id = s.household_id and e.event_kind = 'REVOCATION'
              and coalesce(cast(e.captured_at as date), make_date(e.season_year, 12, 31)) <= make_date(s.participation_year, 12, 31)
              and e.captured_at >= (select max(m.captured_at) from {{ ref('int_consent_event') }} m where m.household_id = s.household_id and m.event_kind = 'MARKETING_OPT_IN'
                                    and coalesce(cast(m.captured_at as date), make_date(m.season_year, 12, 31)) <= make_date(s.participation_year, 12, 31)))
union all
select 'funnel step 6 differs from the independent count', f.participation_year::varchar
from {{ ref('mart_activation_funnel') }} f
left join (
    select y.y as participation_year, count(*) as n
    from (select distinct participation_year as y from {{ ref('fct_participant_year') }}) y
    join {{ ref('int_household_year_consent') }} s on s.participation_year = y.y
    where s.has_contact and s.has_known_full and (
        select arg_max(case when e.event_kind = 'REVOCATION' then 'REVOKED' when e.status = 'GRANTED' and e.provenance_grade = 'KNOWN_FULL' then 'FULL' else 'OTHER' end,
                       (coalesce(e.captured_at, make_timestamp(e.season_year, 12, 31, 0, 0, 0)), (e.status = 'DENIED')::integer, (e.provenance_grade <> 'KNOWN_FULL')::integer))
        from {{ ref('int_consent_event') }} e where e.household_id = s.household_id and e.event_kind in ('MARKETING_OPT_IN', 'REVOCATION')
          and coalesce(cast(e.captured_at as date), make_date(e.season_year, 12, 31)) <= make_date(y.y, 12, 31)) = 'FULL'
    group by 1
) i on i.participation_year = f.participation_year
where f.market_id = 'ALL' and f.step_no = 6 and f.n <> coalesce(i.n, 0)
