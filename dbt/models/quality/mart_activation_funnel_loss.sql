-- Why households leave the funnel, step by step and by type of loss (companion to mart_activation_funnel; counts only). National (market_id 'ALL') and per attributed market.
--   step 4 (valid contact)       NO_VALID_CONTACT                     DQ
--   step 5 (known provenance)    NO_CONSENT_RECORD / PROVENANCE_INCOMPLETE        DQ
--   step 6 (consenting)          MARKETING_CHOICE_NOT_CAPTURED / OPT_IN_EVIDENCE_INCOMPLETE   DQ;   DECLINED / REVOKED   PRIVACY
-- A household appears once, at the first step it fails. Counts are allocated (fractional) per CLUB market; the national row is a distinct count.
with pm as (

    select w.participation_year, w.club_market_id as market_id, w.participant_id, w.weight, h.household_id
    from {{ ref('int_participant_year_market') }} w join {{ ref('int_household') }} h on h.participant_id = w.participant_id

),

members as (select household_id, participation_year, count(distinct participant_id) as n from pm group by 1, 2),

hhw as (

    select pm.participation_year, pm.market_id, pm.household_id, sum(pm.weight) / any_value(m.n) as w
    from pm join members m on m.household_id = pm.household_id and m.participation_year = pm.participation_year group by all

),

hh as (

    select x.participation_year, x.market_id, x.household_id, x.w, s.has_contact, s.n_events, s.has_known_full, s.marketing_status
    from hhw x join {{ ref('int_household_year_consent') }} s on s.household_id = x.household_id and s.participation_year = x.participation_year

),

classified as (

    select *,
           case when not has_contact then 'NO_VALID_CONTACT'
                when not has_known_full and n_events = 0 then 'NO_CONSENT_RECORD'
                when not has_known_full then 'PROVENANCE_INCOMPLETE'
                when marketing_status = 'NOT_CAPTURED' then 'MARKETING_CHOICE_NOT_CAPTURED'
                when marketing_status = 'GRANTED_INCOMPLETE' then 'OPT_IN_EVIDENCE_INCOMPLETE'
                when marketing_status = 'DECLINED' then 'DECLINED'
                when marketing_status = 'REVOKED' then 'REVOKED'
                else 'CONSENTING' end as reason
    from hh

),

reasons as (

    select participation_year, market_id, reason, sum(w) as households from classified group by all
    union all
    select participation_year, 'ALL', reason, count(distinct household_id) from classified group by all

)

select
    participation_year, market_id, reason, households,
    case reason when 'NO_VALID_CONTACT' then 4 when 'NO_CONSENT_RECORD' then 5 when 'PROVENANCE_INCOMPLETE' then 5 else 6 end as step_no,
    case reason when 'CONSENTING' then 'RETAINED' when 'DECLINED' then 'PRIVACY' when 'REVOKED' then 'PRIVACY' else 'DQ' end as loss_type
from reasons
