{{ config(schema='linkage') }}
-- One row per fan account AFTER duplicate households are collapsed (int_fan_account_xref). Guardians only: every holder is an adult when the account is opened
-- (the contract makes anything else an ERROR, and a test checks it again here). Holds contact details, so it is not a share: nothing here reaches an audience.
with x as (select * from {{ ref('int_fan_account_xref') }}),

a as (select * from {{ ref('stg_fan_accounts') }}),

g as (select fan_account_id, count(*) as merged_accounts, min(a.created_at) as first_created_at
      from x join a using (account_id) group by 1)

select
    x.fan_account_id,
    g.merged_accounts,
    g.first_created_at,
    extract(year from g.first_created_at)::integer                          as created_year,
    a.acquisition_source,
    a.country_code,
    a.market_id,
    a.postal_prefix,
    a.holder_birth_year,
    extract(year from g.first_created_at)::integer - a.holder_birth_year    as holder_age_at_signup,
    a.contact_email,
    a.contact_phone
from x
join a on a.account_id = x.fan_account_id
join g on g.fan_account_id = x.fan_account_id
where not x.is_duplicate
