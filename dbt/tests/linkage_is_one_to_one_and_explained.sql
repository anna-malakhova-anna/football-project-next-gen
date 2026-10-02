{{ config(tags=['phase4']) }}
-- Household -> fan account links: one to one, every link has a method and a reason, ambiguous candidates are never used, and no link exists
-- for a household or account that is not in the data. Nothing here is fuzzy: a link is either EMAIL or PHONE equality.
select 'household_with_two_links' as problem, household_id as detail
from {{ ref('link_household_fan_account') }} where link_status = 'LINKED' group by household_id having count(*) > 1
union all
select 'account_with_two_links', account_id
from {{ ref('link_household_fan_account') }} where link_status = 'LINKED' group by account_id having count(*) > 1
union all
select 'link_without_method_or_reason', household_id || '|' || account_id
from {{ ref('link_household_fan_account') }} where link_method not in ('EMAIL', 'PHONE') or reason is null
union all
select 'phone_link_for_household_with_email_link', l.household_id
from {{ ref('link_household_fan_account') }} l
where l.link_method = 'PHONE' and l.household_id in (select household_id from {{ ref('link_household_fan_account') }} where link_method = 'EMAIL')
union all
select 'link_to_unknown_account', account_id from {{ ref('link_household_fan_account') }}
where account_id not in (select account_id from {{ ref('stg_fan_accounts') }})
union all
select 'link_to_unknown_household', household_id from {{ ref('link_household_fan_account') }}
where household_id not in (select household_id from {{ ref('int_household_profile') }})
union all
select 'participant_in_two_households', participant_id from {{ ref('int_household') }} group by participant_id having count(*) > 1
union all
select 'adult_household_with_other_members', household_id from {{ ref('int_household') }}
where is_adult_household group by household_id having count(*) > 1
