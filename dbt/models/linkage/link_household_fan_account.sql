-- RESTRICTED (schema `linkage`). Deterministic links from an observed participant household to a fan account. No fuzzy matching, on purpose:
-- a wrong link here puts a family's fan behaviour next to their children's registrations, so the rule must be one a person can check by eye
-- (ADR-009). The order is fixed and every link carries its reason:
--   1. EMAIL   the household's normalized guardian email equals the account's normalized email
--   2. PHONE   only for households AND accounts that have no email link: the normalized phone numbers are equal
-- A link is made only when it is one to one. If a contact value reaches several households or several accounts the candidates are kept with
-- status AMBIGUOUS and NOT used (a shared inbox is not a family). Households with no account are simply unlinked: absence of a link is the
-- common case (the account email often differs from the registration email) and is reported as the link rate, never imputed.
with hh_contacts as (

    select household_id, 'EMAIL' as contact_type, unnest(emails) as contact_value from {{ ref('int_household_profile') }}
    union all
    select household_id, 'PHONE', unnest(phones) from {{ ref('int_household_profile') }}

),

acct as (

    select account_id, 'EMAIL' as contact_type, contact_email as contact_value from {{ ref('stg_fan_accounts') }} where contact_email is not null
    union all
    select account_id, 'PHONE', contact_phone from {{ ref('stg_fan_accounts') }} where contact_phone is not null

),

cand as (

    select distinct h.household_id, a.account_id, h.contact_type
    from hh_contacts h join acct a on a.contact_type = h.contact_type and a.contact_value = h.contact_value

),

email_cand as (

    select household_id, account_id,
           count(*) over (partition by household_id) as accounts_per_household,
           count(*) over (partition by account_id)   as households_per_account
    from cand where contact_type = 'EMAIL'

),

email_links as (

    select household_id, account_id, 'EMAIL' as link_method,
           case when accounts_per_household = 1 and households_per_account = 1 then 'LINKED' else 'AMBIGUOUS' end as link_status
    from email_cand

),

phone_cand as (

    -- the phone fallback is a project switch (var linkage_phone_fallback, default true): ADR-009 reports its measured precision
    select c.household_id, c.account_id,
           count(*) over (partition by c.household_id) as accounts_per_household,
           count(*) over (partition by c.account_id)   as households_per_account
    from cand c
    where c.contact_type = 'PHONE'
      and {{ 'true' if var('linkage_phone_fallback') else 'false' }}
      and c.household_id not in (select household_id from email_links)
      and c.account_id not in (select account_id from email_links)

),

phone_links as (

    select household_id, account_id, 'PHONE' as link_method,
           case when accounts_per_household = 1 and households_per_account = 1 then 'LINKED' else 'AMBIGUOUS' end as link_status
    from phone_cand

),

all_links as (

    select * from email_links
    union all
    select * from phone_links

)

select household_id, account_id, link_method, link_status,
       case link_method when 'EMAIL' then 'normalized guardian email equals normalized account email'
                        else 'no email link; normalized phone numbers are equal' end
       || case link_status when 'AMBIGUOUS' then '; the value reaches more than one household or account, so no link is made' else '' end as reason
from all_links
