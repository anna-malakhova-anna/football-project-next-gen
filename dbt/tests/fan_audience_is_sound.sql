{{ config(tags=['phase4']) }}
-- The addressable audience: UNLINKED households are never contactable (they have no account and no consent); registered >= linked >= contactable; each channel <= contactable; the consent gap <= active
-- households; the household groups add up to ALL; contactable households really hold an opted-in interval at the month end; every contactable household is a GUARDIAN account (the holder was an adult
-- at signup: the contract's ERROR rule, checked again here); and nothing in the audience marts is household-level (only counts and shares).
select 'unlinked_household_is_contactable' as problem, cast(month as varchar) as detail from {{ ref('mart_addressable_audience') }} where household_group = 'UNLINKED' and (contactable_households > 0 or linked_households > 0)
union all
select 'funnel_order_broken', cast(month as varchar) || '|' || household_group from {{ ref('mart_addressable_audience') }}
where linked_households > households_registered or contactable_households > linked_households or contactable_email > contactable_households
   or contactable_sms > contactable_households or contactable_push > contactable_households or consent_gap_households > active_households or active_households > linked_households
union all
select 'groups_do_not_add_up_to_all', cast(month as varchar)
from {{ ref('mart_addressable_audience') }} group by month
having sum(households_registered) filter (where household_group <> 'ALL') <> sum(households_registered) filter (where household_group = 'ALL')
    or sum(contactable_households) filter (where household_group <> 'ALL') <> sum(contactable_households) filter (where household_group = 'ALL')
union all
select 'contactable_without_an_opted_in_interval', a.household_id || '|' || cast(a.month as varchar)
from {{ ref('int_household_audience_month') }} a
where a.is_contactable and not exists (
    select 1 from {{ ref('fct_household_fan_status') }} s join {{ ref('fct_fan_consent_history') }} c on c.fan_account_id = s.fan_account_id
    where s.household_id = a.household_id and c.status = 'opt_in' and c.valid_from < (a.month + interval 1 month)::timestamp and (c.valid_to is null or c.valid_to >= (a.month + interval 1 month)::timestamp))
union all
select 'contactable_account_held_by_a_minor', s.household_id
from {{ ref('int_household_audience_month') }} a join {{ ref('fct_household_fan_status') }} s using (household_id) join {{ ref('dim_fan_account') }} d on d.fan_account_id = s.fan_account_id
where a.is_contactable and (d.holder_age_at_signup < 18 or d.holder_age_at_signup is null)
union all
select 'consent_gap_value_not_synthetic_label', cast(month as varchar) from {{ ref('mart_addressable_audience') }} where label <> 'synthetic currency, illustrative'
union all
select 'capture_rate_out_of_range', cut || '|' || dimension_value || '|' || channel from {{ ref('mart_consent_capture') }} where opt_in_rate not between 0 and 1 or opt_ins > consent_lines
union all
select 'opt_out_rate_negative', channel || '|' || engagement_band from {{ ref('mart_opt_out_after_contact') }} where opt_outs > opted_in_account_months or opt_outs_per_1000_account_months < 0
