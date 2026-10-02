-- RESTRICTED (schema `linkage`; counts only). Fan ACTIVENESS by month-end and fan group: how many fan accounts are active, at risk or lapsed, and how many moved between those states from the
-- month before. Windows come from fan_params in months: ACTIVE = engaged in the last `active_window_months` calendar months (including this one); AT_RISK = not in those but in the
-- `lapsed_window_months` before; LAPSED = none in the whole lapsed window; NEW = the account is younger than the lapsed window and has not engaged yet (not judged).
-- Only accounts that exist at the month end are counted. Groups are int_fan_account_group's (UNLINKED_OR_NON_PARTICIPANT is not "non-participant fans").
-- Transitions: from_state -> to_state for accounts present in both months; a count of accounts, never a person.
with state as (select fan_account_id, fan_group, event_month, mi, state from {{ ref('int_fan_account_month_state') }}),

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
