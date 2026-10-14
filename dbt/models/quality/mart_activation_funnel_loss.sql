-- Why households leave the funnel, step by step and by type of loss (companion to mart_activation_funnel; counts only). National (market_id 'ALL') and per attributed market.
--   step 4 (valid contact)       NO_VALID_CONTACT                     DQ
--   step 5 (known provenance)    NO_CONSENT_RECORD / PROVENANCE_INCOMPLETE        DQ
--   step 6 (consenting)          MARKETING_CHOICE_NOT_CAPTURED / OPT_IN_EVIDENCE_INCOMPLETE   DQ;   DECLINED / REVOKED   PRIVACY
-- A household appears once, at the first step it fails.
with pm as (

    select f.participation_year, coalesce(f.market_id, 'UNATTRIBUTED') as market_id, h.household_id
    from {{ ref('fct_participant_year') }} f join {{ ref('int_household') }} h on h.participant_id = f.participant_id

),

hh as (

    select pm.participation_year, pm.market_id, pm.household_id, s.has_contact, s.n_events, s.has_known_full, s.marketing_status
    from (select distinct * from pm) pm join {{ ref('int_household_year_consent') }} s on s.household_id = pm.household_id and s.participation_year = pm.participation_year

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

    select participation_year, market_id, reason, count(*) as households from classified group by all
    union all
    select participation_year, 'ALL', reason, count(distinct household_id) from classified group by all

)

select
    participation_year, market_id, reason, households,
    case reason when 'NO_VALID_CONTACT' then 4 when 'NO_CONSENT_RECORD' then 5 when 'PROVENANCE_INCOMPLETE' then 5 else 6 end as step_no,
    case reason when 'CONSENTING' then 'RETAINED' when 'DECLINED' then 'PRIVACY' when 'REVOKED' then 'PRIVACY' else 'DQ' end as loss_type
from reasons
