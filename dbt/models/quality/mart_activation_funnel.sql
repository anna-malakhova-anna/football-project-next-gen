-- depends_on: {{ ref('consent_purposes') }}
-- depends_on: {{ ref('mart_activation_funnel_loss') }}
-- The activation funnel, per participation year and club-market attribution (phase-5-spec section 8): registrations, resolved participants, households, households with a valid contact, households with
-- known consent provenance, households consenting to CLUB_MARKETING. COUNTS ONLY: no participant, household or record identifier is in this table, and the child entity is never joined to its output.
-- Each step after the first says what kind of loss it is:
--   (loss_type is the larger of the two at step 6; lost_dq and lost_privacy give the exact split; steps 2 and 3 are UNIT: a person registers more than once a year and siblings share a household)
--   DQ        the data cannot say: duplicates, no valid contact, consent not recorded, provenance incomplete, an opt-in on a form that never named the purpose, a marketing choice never captured
--   PRIVACY   the family said no or withdrew: declined, revoked. This is the loss a data fix cannot, and must not, recover.
--   UNIT      a change of counting unit (children to households), not a loss.
-- The distinction is the bridge between the two audiences: DQ losses are the data steward's to fix; PRIVACY losses are the privacy lead's to protect. mart_activation_funnel_loss splits each step by reason.
-- market_id is a CLUB market (club_market_map: a project approximation). Counts are ALLOCATED, so fractional where a ZIP3 is shared: a participant counts across the markets of their ZIP3 by weight, and a household's weight in a market
-- is the average of its active members'. OUTSIDE_US holds Canadian and international households. The national row is market_id = 'ALL' and is a plain distinct count.
with pm as (

    -- a participant-year in a CLUB market with its allocation weight (int_participant_year_market); a household's weight in a market is the average of its active members' weights
    select w.participation_year, w.club_market_id as market_id, w.participant_id, w.weight, h.household_id
    from {{ ref('int_participant_year_market') }} w join {{ ref('int_household') }} h on h.participant_id = w.participant_id

),

members as (select household_id, participation_year, count(distinct participant_id) as n from pm group by 1, 2),

hhw as (

    select pm.participation_year, pm.market_id, pm.household_id, sum(pm.weight) / any_value(m.n) as w
    from pm join members m on m.household_id = pm.household_id and m.participation_year = pm.participation_year group by all

),

regs as (

    select f.participation_year, w.club_market_id as market_id, sum(w.weight) as registrations
    from {{ ref('fct_registration') }} f join {{ ref('int_participant_year_market') }} w on w.participant_id = f.participant_id and w.participation_year = f.participation_year
    where f.is_valid_registration group by 1, 2

),

hh as (

    select x.participation_year, x.market_id, x.household_id, x.w, s.has_contact, s.has_known_full, s.marketing_status
    from hhw x join {{ ref('int_household_year_consent') }} s on s.household_id = x.household_id and s.participation_year = x.participation_year

),

per_market as (

    select participation_year, market_id,
           sum(w)                                                                                                      as households,
           coalesce(sum(w) filter (where has_contact), 0)                                                              as households_with_contact,
           coalesce(sum(w) filter (where has_contact and has_known_full), 0)                                           as households_known_provenance,
           coalesce(sum(w) filter (where has_contact and has_known_full and marketing_status = 'GRANTED_FULL'), 0)     as households_consenting
    from hh group by all

),

part as (select participation_year, market_id, sum(weight) as participants from pm group by all),

national as (

    select participation_year, 'ALL' as market_id,
           (select count(*) from {{ ref('fct_registration') }} f where f.is_valid_registration and f.participation_year = h.participation_year) as registrations,
           (select count(distinct participant_id) from pm where pm.participation_year = h.participation_year) as participants,
           count(distinct household_id)                                                             as households,
           count(distinct household_id) filter (where has_contact)                                  as households_with_contact,
           count(distinct household_id) filter (where has_contact and has_known_full)               as households_known_provenance,
           count(distinct household_id) filter (where has_contact and has_known_full and marketing_status = 'GRANTED_FULL') as households_consenting
    from hh h group by participation_year

),

wide as (

    select p.participation_year, p.market_id, coalesce(r.registrations, 0) as registrations, p.participants, m.households, m.households_with_contact,
           m.households_known_provenance, m.households_consenting
    from part p join per_market m using (participation_year, market_id) left join regs r using (participation_year, market_id)
    union all
    select * from national

),

steps as (

    select participation_year, market_id, 1 as step_no, 'registrations' as step, 'registrations' as unit, registrations as n from wide
    union all select participation_year, market_id, 2, 'resolved participants', 'participants', participants from wide
    union all select participation_year, market_id, 3, 'households', 'households', households from wide
    union all select participation_year, market_id, 4, 'households with a valid contact', 'households', households_with_contact from wide
    union all select participation_year, market_id, 5, 'households with known consent provenance', 'households', households_known_provenance from wide
    union all select participation_year, market_id, 6, 'households consenting to CLUB_MARKETING', 'households', households_consenting from wide

)

select
    s.participation_year, s.market_id, s.step_no, s.step, s.unit, s.n,
    lag(s.n) over (partition by s.participation_year, s.market_id order by s.step_no)                      as previous_n,
    lag(s.n) over (partition by s.participation_year, s.market_id order by s.step_no) - s.n                as lost,
    -- the loss split by type: UNIT is a change of counting unit (a person registers more than once a year, siblings share a household), not a loss; steps 4 and 5 are DQ; step 6 is both
    case s.step_no when 2 then lag(s.n) over (partition by s.participation_year, s.market_id order by s.step_no) - s.n when 3 then lag(s.n) over (partition by s.participation_year, s.market_id order by s.step_no) - s.n else 0 end as lost_unit,
    case s.step_no when 4 then lag(s.n) over (partition by s.participation_year, s.market_id order by s.step_no) - s.n when 5 then lag(s.n) over (partition by s.participation_year, s.market_id order by s.step_no) - s.n
                   when 6 then coalesce(l.lost_dq, 0) else 0 end                                                                        as lost_dq,
    case s.step_no when 6 then coalesce(l.lost_privacy, 0) else 0 end                                                                   as lost_privacy,
    case s.step_no when 1 then null when 2 then 'UNIT' when 3 then 'UNIT' when 4 then 'DQ' when 5 then 'DQ'
                   when 6 then case when coalesce(l.lost_privacy, 0) >= coalesce(l.lost_dq, 0) then 'PRIVACY' else 'DQ' end end                as loss_type
from steps s
left join (
    select participation_year, market_id, sum(households) filter (where loss_type = 'DQ' and step_no = 6) as lost_dq, sum(households) filter (where loss_type = 'PRIVACY') as lost_privacy
    from {{ ref('mart_activation_funnel_loss') }} group by all
) l on l.participation_year = s.participation_year and l.market_id = s.market_id and s.step_no = 6
