-- RESTRICTED (schema `linkage`). One row per participant household x month-end, once the household has registered (first registration month on or before it): is it linked, which channels are
-- OPTED IN at that month end (from the consent history, guardian accounts only), is its account ACTIVE at that month end, and its trailing 12-month net spend (synthetic currency).
-- Consent is read as of the month end from the SCD2 (valid_from before the month end, and valid_to open or on or after it): an account with no line for a channel is NOT opted in (not captured is never TRUE).
-- UNLINKED households have no fan account and therefore no consent: they are never counted as contactable.
with months as (

    select unnest(generate_series(make_date(first_observed_year, 1, 1), make_date(last_observed_year, 12, 1), interval 1 month))::date as month
    from {{ ref('observation_window') }}

),

hh as (

    select s.household_id, s.fan_account_id, s.fan_status, s.first_registration_month,
           case when s.fan_status = 'UNLINKED' then 'UNLINKED'
                when s.fan_status = 'NET_NEW' and s.net_new_via_flag_prompt then 'NET_NEW_FLAG_PROMPT'
                when s.fan_status = 'NET_NEW' then 'NET_NEW_OTHER' else 'EXISTING_FAN' end as household_group
    from {{ ref('fct_household_fan_status') }} s

),

hm as (select hh.*, m.month, (m.month + interval 1 month)::timestamp as month_end from hh join months m on m.month >= hh.first_registration_month),

consent as (

    select hm.household_id, hm.month,
           bool_or(c.channel = 'email') as email, bool_or(c.channel = 'sms') as sms, bool_or(c.channel = 'push') as push
    from hm
    join {{ ref('fct_fan_consent_history') }} c on c.fan_account_id = hm.fan_account_id
    where hm.fan_status <> 'UNLINKED' and c.status = 'opt_in' and c.valid_from < hm.month_end and (c.valid_to is null or c.valid_to >= hm.month_end)
    group by 1, 2

),

spend as (

    select fan_account_id, event_month,
           sum(net_spend_total) over (partition by fan_account_id order by date_diff('month', date '2000-01-01', event_month)
                                      range between {{ fan_param('rfm_trailing_months') }} - 1 preceding and current row) as trailing_net_spend
    from {{ ref('int_fan_outcome_month') }}

)

select
    hm.household_id, hm.month, hm.household_group, hm.fan_status, hm.fan_status <> 'UNLINKED' as is_linked,
    coalesce(c.email, false) as opted_in_email, coalesce(c.sms, false) as opted_in_sms, coalesce(c.push, false) as opted_in_push,
    coalesce(c.email or c.sms or c.push, false) as is_contactable,
    coalesce(st.state = 'ACTIVE', false) as is_active,
    coalesce(sp.trailing_net_spend, 0) as trailing_net_spend
from hm
left join consent c on c.household_id = hm.household_id and c.month = hm.month
left join {{ ref('int_fan_account_month_state') }} st on st.fan_account_id = hm.fan_account_id and st.event_month = hm.month
left join spend sp on sp.fan_account_id = hm.fan_account_id and sp.event_month = hm.month
