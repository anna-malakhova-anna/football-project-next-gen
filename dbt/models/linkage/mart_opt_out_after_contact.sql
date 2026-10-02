-- RESTRICTED (schema `linkage`; counts only). Do fans opt out when they are contacted more? A proxy, because contact itself is not in the data: engagement volume that month stands in for how much a
-- fan hears from us. For every account-month in which a channel was OPTED IN at the start of the month, did the account opt that channel out during the month? The rate is opt-outs per 1,000
-- opted-in account-months, by channel and by the account's engagement volume that month (0, 1 to 2, 3 to 5, 6 or more events). An association only: heavily engaged fans may differ in other ways.
with c as (

    select h.fan_account_id, h.channel, h.status, h.valid_from, h.valid_to
    from {{ ref('fct_fan_consent_history') }} h

),

months as (

    select unnest(generate_series(make_date(first_observed_year, 1, 1), make_date(last_observed_year, 12, 1), interval 1 month))::date as month from {{ ref('observation_window') }}

),

at_risk as (

    select c.fan_account_id, c.channel, m.month,
           c.valid_to is not null and c.valid_to >= m.month::timestamp and c.valid_to < (m.month + interval 1 month)::timestamp as opted_out_in_month
    from c join months m on c.status = 'opt_in' and c.valid_from < m.month::timestamp and (c.valid_to is null or c.valid_to >= m.month::timestamp)

),

banded as (

    select a.channel, a.opted_out_in_month,
           case when coalesce(f.events, 0) = 0 then '0' when f.events <= 2 then '1-2' when f.events <= 5 then '3-5' else '6+' end as engagement_band
    from at_risk a left join {{ ref('fct_fan_engagement_month') }} f on f.fan_account_id = a.fan_account_id and f.event_month = a.month

),

g as (

    select channel, engagement_band, count(*) as opted_in_account_months, count(*) filter (where opted_out_in_month) as opt_outs from banded group by grouping sets ((channel, engagement_band), (channel))

)

select
    channel, coalesce(engagement_band, 'ALL') as engagement_band, opted_in_account_months, opt_outs,
    round(opt_outs * 1000.0 / opted_in_account_months, 3)                   as opt_outs_per_1000_account_months,
    '{{ var("methodology_version") }}'                                      as methodology_version
from g order by channel, engagement_band
