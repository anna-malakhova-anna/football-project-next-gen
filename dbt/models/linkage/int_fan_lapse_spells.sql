-- RESTRICTED (schema `linkage`). One fan SPELL per account in a survival group (int_fan_account_group.origin_month not null): time in months from the origin to the account's first LAPSE.
-- A lapse is `lapsed_window_months` (default 6) calendar months without a single event: the lapse month is the last engaged month plus that window. An account that never engages from its
-- origin has no first engagement and is left out. A spell still engaged (or whose quiet run has not yet lasted the window) at the end of the data is CENSORED at the end, not a lapse.
-- Time t is in months since the origin (>= 1). The same censoring discipline as player retention: the end of the data is unknown follow-up.
with g as (select * from {{ ref('int_fan_account_group') }} where origin_month is not null),

bounds as (select date_diff('month', make_date(first_observed_year, 1, 1), make_date(last_observed_year, 12, 1)) as last_mi from {{ ref('observation_window') }}),

e as (

    select g.fan_account_id, g.fan_group, g.market_type, g.origin_month,
           date_diff('month', make_date((select first_observed_year from {{ ref('observation_window') }}), 1, 1), f.event_month) as mi,
           date_diff('month', make_date((select first_observed_year from {{ ref('observation_window') }}), 1, 1), g.origin_month) as origin_mi
    from g join {{ ref('fct_fan_engagement_month') }} f on f.fan_account_id = g.fan_account_id
    where f.is_active_month and f.event_month >= g.origin_month

),

gaps as (

    select *, lead(mi) over (partition by fan_account_id order by mi) as next_mi from e

),

lapse as (

    select fan_account_id,
           min(mi + {{ fan_param('lapsed_window_months') }}) filter (
               where coalesce(next_mi, (select last_mi from bounds) + 1) - mi > {{ fan_param('lapsed_window_months') }}
                 and mi + {{ fan_param('lapsed_window_months') }} <= (select last_mi from bounds)) as lapse_mi
    from gaps group by 1

),

first_eng as (select fan_account_id, any_value(fan_group) as fan_group, any_value(market_type) as market_type, any_value(origin_mi) as origin_mi, min(mi) as first_mi from e group by 1)

select
    f.fan_account_id,
    f.fan_group,
    f.market_type,
    f.origin_mi,
    greatest(1, coalesce(l.lapse_mi, (select last_mi from bounds)) - f.origin_mi)                           as t,
    l.lapse_mi is not null                                                  as event,
    l.lapse_mi - {{ fan_param('lapsed_window_months') }} + 1                as onset_mi          -- the first quiet month: when the lapse BEGAN (it is confirmed a window later)
from first_eng f left join lapse l using (fan_account_id)
