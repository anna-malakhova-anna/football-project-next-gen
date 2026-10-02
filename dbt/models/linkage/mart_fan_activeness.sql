-- RESTRICTED (schema `linkage`; counts only). Fan ACTIVENESS by month-end and fan group: how many fan accounts are active, at risk or lapsed, and how many moved between those states from the
-- month before. Windows come from fan_params in months: ACTIVE = engaged in the last `active_window_months` calendar months (including this one); AT_RISK = not in those but in the
-- `lapsed_window_months` before; LAPSED = none in the whole lapsed window; NEW = the account is younger than the lapsed window and has not engaged yet (not judged).
-- Only accounts that exist at the month end are counted. Groups are int_fan_account_group's (UNLINKED_OR_NON_PARTICIPANT is not "non-participant fans").
-- Transitions: from_state -> to_state for accounts present in both months; a count of accounts, never a person.
with e as (

    select f.fan_account_id, g.fan_group, f.event_month, f.is_active_month,
           date_diff('month', make_date((select first_observed_year from {{ ref('observation_window') }}), 1, 1), f.event_month) as mi
    from {{ ref('fct_fan_engagement_month') }} f join {{ ref('int_fan_account_group') }} g using (fan_account_id)

),

c as (

    select *,
           sum(case when is_active_month then 1 else 0 end) over w_active                                                  as in_active_window,
           sum(case when is_active_month then 1 else 0 end) over w_lapsed                                                  as in_lapsed_window,
           count(*) over w_lapsed                                                                                          as months_observed
    from e
    window w_active as (partition by fan_account_id order by mi range between {{ fan_param('active_window_months') }} - 1 preceding and current row),
           w_lapsed as (partition by fan_account_id order by mi range between {{ fan_param('lapsed_window_months') }} - 1 preceding and current row)

),

state as (

    select fan_account_id, fan_group, event_month, mi,
           case
               when in_active_window > 0 then 'ACTIVE'
               when in_lapsed_window > 0 then 'AT_RISK'
               when months_observed < {{ fan_param('lapsed_window_months') }} then 'NEW'
               else 'LAPSED'
           end as state
    from c

),

counts as (

    select event_month, fan_group, state, count(*) as accounts from state group by 1, 2, 3

),

moves as (

    select a.event_month, a.fan_group, b.state as from_state, a.state as to_state, count(*) as accounts
    from state a join state b on b.fan_account_id = a.fan_account_id and b.mi = a.mi - 1
    group by 1, 2, 3, 4

)

select 'STATE' as section, event_month, fan_group, state as from_state, cast(null as varchar) as to_state, accounts, '{{ var("methodology_version") }}' as methodology_version from counts
union all
select 'TRANSITION', event_month, fan_group, from_state, to_state, accounts, '{{ var("methodology_version") }}' from moves
order by 1, 2, 3, 4, 5
