{{ config(tags=['phase4']) }}
-- Fan status per participant household: exactly one row and one status per household; every status is one of the defined ones; UNLINKED is exactly the households with no linked fan account
-- (never reclassified into a non-fan or any other status, and no linked household is UNLINKED); NET_NEW means the account was created on or after the registration month; the
-- windows come from fan_params (no literals): the seed must hold all three.
select 'household_with_no_or_two_statuses' as problem, household_id as detail
from {{ ref('fct_household_fan_status') }} group by household_id having count(*) <> 1
union all
select 'household_missing_from_the_status_table', household_id from {{ ref('int_household_profile') }}
where household_id not in (select household_id from {{ ref('fct_household_fan_status') }})
union all
select 'unknown_status', household_id from {{ ref('fct_household_fan_status') }}
where fan_status not in ('UNLINKED', 'NET_NEW', 'EXISTING_ACTIVE', 'EXISTING_COOLING', 'LAPSED_REACTIVATED', 'LAPSED_DORMANT', 'INSUFFICIENT_HISTORY')
union all
select 'unlinked_household_got_another_status', s.household_id from {{ ref('fct_household_fan_status') }} s
where s.fan_status <> 'UNLINKED' and s.household_id not in (select household_id from {{ ref('link_household_fan_account') }} where link_status = 'LINKED')
union all
select 'linked_household_called_unlinked', s.household_id from {{ ref('fct_household_fan_status') }} s
where s.fan_status = 'UNLINKED' and s.household_id in (select household_id from {{ ref('link_household_fan_account') }} where link_status = 'LINKED')
union all
select 'net_new_account_predates_the_registration', household_id from {{ ref('fct_household_fan_status') }} where fan_status = 'NET_NEW' and account_created_at < first_registration_month
union all
select 'flag_prompt_flag_on_a_non_net_new_household', household_id from {{ ref('fct_household_fan_status') }} where net_new_via_flag_prompt and fan_status <> 'NET_NEW'
union all
select 'fan_params_incomplete', param from (select unnest(['active_window_days', 'lapsed_window_days', 'reactivation_window_months']) as param)
where param not in (select param from {{ ref('fan_params') }})
union all
select 'active_window_not_shorter_than_the_lapsed_window', 'fan_params'
from (select (select value from {{ ref('fan_params') }} where param = 'active_window_days') as a, (select value from {{ ref('fan_params') }} where param = 'lapsed_window_days') as l) where a >= l
