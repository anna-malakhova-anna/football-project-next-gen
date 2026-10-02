-- RESTRICTED (schema `linkage`). Which kind of fan each canonical fan account is, for the activeness, survival, value and RFM analyses (rework spec 5.4):
--   NET_NEW_FLAG_PROMPT   a linked NET_NEW household whose account came through the flag registration prompt
--   NET_NEW_OTHER         a linked NET_NEW household whose account came another way
--   EXISTING_FAN          a linked household whose account already existed at the first registration (active, cooling, lapsed or without enough history)
--   UNLINKED_OR_NON_PARTICIPANT   every other account: it may belong to a participant household we could not link, so this is NOT "non-participant fan"
-- `origin_month` is where a fan spell starts (NULL when the account is not in a survival group): the account's first month for new accounts (NET_NEW and accounts created in the data window),
-- the first registration month for EXISTING_FAN accounts that were not lapsed then (time since registration). Accounts opened before the data starts cannot be followed from their first engagement.
with d as (select * from {{ ref('dim_fan_account') }}),

s as (select household_id, fan_account_id, fan_status, net_new_via_flag_prompt, first_registration_month from {{ ref('fct_household_fan_status') }} where fan_status <> 'UNLINKED'),

w as (select make_date(first_observed_year, 1, 1) as first_day from {{ ref('observation_window') }})

select
    d.fan_account_id,
    case
        when s.fan_status = 'NET_NEW' and s.net_new_via_flag_prompt then 'NET_NEW_FLAG_PROMPT'
        when s.fan_status = 'NET_NEW' then 'NET_NEW_OTHER'
        when s.fan_status is not null then 'EXISTING_FAN'
        else 'UNLINKED_OR_NON_PARTICIPANT'
    end                                                                     as fan_group,
    s.household_id,
    s.fan_status,
    coalesce(m.is_team_market = 'Y', false)                                 as is_team_market,
    case when m.is_team_market = 'Y' then 'TEAM' else 'NON_TEAM' end        as market_type,
    case
        when s.fan_status = 'NET_NEW' then date_trunc('month', d.first_created_at)::date
        when s.fan_status in ('EXISTING_ACTIVE', 'EXISTING_COOLING') then s.first_registration_month
        when s.fan_status is null and d.first_created_at >= (select first_day from w) then date_trunc('month', d.first_created_at)::date
    end                                                                     as origin_month
from d
left join s on s.fan_account_id = d.fan_account_id
left join {{ ref('market_map') }} m on m.market_id = d.market_id
