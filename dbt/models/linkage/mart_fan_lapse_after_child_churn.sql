-- RESTRICTED (schema `linkage`; counts only). ASSOCIATION ONLY: does a household's fan lapse rate change when its child stops playing? Person-time is split at the month the household's last
-- child season ends (int_participant_household_timeline.churn_month): months while a child plays vs months after. For linked households with an existing or net-new account that had not lapsed
-- at the first registration, each month from the registration month is at risk until the account's first lapse (6 quiet months) or the end of the data, and is counted in exactly one period.
-- rate = lapses per 1,000 at-risk account-months; rate_ratio = after / while. Splitting person-time (rather than comparing households that churned with those that did not) avoids crediting
-- the households that stayed engaged longer with a head start. A lapse is confirmed `lapsed_window_months` after the last engagement, so its ONSET (the first quiet month) is used to put it in a period. It says nothing about WHY the rate changes: households whose child stops playing may differ in other ways.
with hh as (

    select s.household_id, s.fan_account_id, s.first_registration_month as start_month, t.churn_month
    from {{ ref('fct_household_fan_status') }} s
    join {{ ref('int_participant_household_timeline') }} t using (household_id)
    where s.fan_status in ('EXISTING_ACTIVE', 'EXISTING_COOLING', 'NET_NEW')
),

bounds as (select date_diff('month', make_date(first_observed_year, 1, 1), make_date(last_observed_year, 12, 1)) as last_mi, make_date(first_observed_year, 1, 1) as d0 from {{ ref('observation_window') }}),

lapse as (

    select fan_account_id, any_value(origin_mi) as origin_mi, any_value(origin_mi + t) as end_mi, any_value(onset_mi) as onset_mi, bool_or(event) as lapsed
    from {{ ref('int_fan_lapse_spells') }} group by 1

),

risk as (

    select
        h.household_id,
        date_diff('month', (select d0 from bounds), greatest(h.start_month, (select d0 from bounds)))           as from_mi,
        case when l.fan_account_id is not null and l.lapsed then l.onset_mi when l.fan_account_id is not null then l.end_mi else (select last_mi from bounds) end as to_mi,
        coalesce(l.lapsed, false)                                                                              as lapsed,
        case when h.churn_month is null then null else date_diff('month', (select d0 from bounds), h.churn_month) end as churn_mi
    from hh h left join lapse l on l.fan_account_id = h.fan_account_id

),

months as (

    select r.household_id, k.mi, r.lapsed and k.mi = r.to_mi as is_lapse,
           case when r.churn_mi is not null and k.mi >= r.churn_mi then 'AFTER_CHILD_STOPPED' else 'WHILE_CHILD_PLAYS' end as period
    from risk r cross join lateral (select unnest(range(r.from_mi, r.to_mi + 1)) as mi) k
    where r.to_mi >= r.from_mi

),

g as (

    select period, count(*) as at_risk_account_months, count(*) filter (where is_lapse) as lapses from months group by 1

)

select
    period,
    at_risk_account_months,
    lapses,
    round(lapses * 1000.0 / at_risk_account_months, 3)                      as lapses_per_1000_account_months,
    round((select lapses * 1.0 / at_risk_account_months from g where period = 'AFTER_CHILD_STOPPED')
          / (select lapses * 1.0 / at_risk_account_months from g where period = 'WHILE_CHILD_PLAYS'), 3) as rate_ratio_after_vs_while,
    '{{ var("methodology_version") }}'                                      as methodology_version
from g
order by period
