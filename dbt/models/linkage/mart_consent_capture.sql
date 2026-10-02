-- RESTRICTED (schema `linkage`; counts only). CONSENT CAPTURE: how often an account says yes where it was asked. Two cuts of the same lines:
--   BY_CAPTURE_POINT   for each capture point (signup, checkout, flag_registration, preference_center) and channel: the consent lines, the opt-ins, and the opt-in rate (opt-ins / lines)
--   BY_SOURCE_SYSTEM / BY_PARTNER   for NET-NEW accounts that came through the flag registration prompt: the opt-in rate at that moment by the source system and by the PARTNER (organization) the household
--                      first registered with. Which partners' registration flows capture consent best? A partner with fewer than k_min lines is not reliable (`reliable`): rates there are noise.
-- An account that was never asked a channel has no line for it: not captured, never counted as a no. The opt-in rate is among the lines that exist (those who answered).
with e as (

    select x.fan_account_id, c.channel, c.status, c.capture_point
    from {{ ref('stg_fan_consent_events') }} c
    join {{ ref('int_fan_account_xref') }} x using (account_id)
    where c.record_occurrence = 1 and 'unmapped_consent_value' <> all(c.dq_flags) and 'orphan_consent_event' <> all(c.dq_flags)

),

by_point as (

    select 'BY_CAPTURE_POINT' as cut, capture_point as dimension_value, channel,
           count(*) as consent_lines, count(*) filter (where status = 'opt_in') as opt_ins
    from e group by 1, 2, 3

),

first_reg as (

    select s.household_id, s.fan_account_id,
           first_value(r.source_system) over w as source_system, first_value(r.organization_id) over w as organization_id
    from {{ ref('fct_household_fan_status') }} s
    join {{ ref('int_household') }} h using (household_id)
    join {{ ref('fct_registration') }} r on r.participant_id = h.participant_id and r.is_valid_registration
    where s.fan_status = 'NET_NEW' and s.net_new_via_flag_prompt
    window w as (partition by s.household_id order by r.participation_year, r.term_order, r.registration_key)

),

partner as (select distinct household_id, fan_account_id, source_system, organization_id from first_reg),

by_source as (

    select 'BY_SOURCE_SYSTEM' as cut, p.source_system as dimension_value, e.channel,
           count(*) as consent_lines, count(*) filter (where e.status = 'opt_in') as opt_ins
    from partner p join e on e.fan_account_id = p.fan_account_id and e.capture_point = 'flag_registration'
    group by 1, 2, 3

),

by_partner as (

    select 'BY_PARTNER' as cut, p.source_system || ' | ' || p.organization_id as dimension_value, e.channel,
           count(*) as consent_lines, count(*) filter (where e.status = 'opt_in') as opt_ins
    from partner p join e on e.fan_account_id = p.fan_account_id and e.capture_point = 'flag_registration'
    group by 1, 2, 3

)

select cut, dimension_value, channel, consent_lines, opt_ins, round(opt_ins * 1.0 / nullif(consent_lines, 0), 4) as opt_in_rate,
       consent_lines >= {{ privacy_param('k_min') }} as reliable, '{{ var("methodology_version") }}' as methodology_version
from (select * from by_point union all select * from by_source union all select * from by_partner)
order by cut, dimension_value, channel
