-- RESTRICTED (schema `linkage`). The activeness STATE of every fan account (canonical, duplicates collapsed) at the end of every month it exists, with the fan group:
--   ACTIVE   engaged in the last `active_window_months` calendar months (including this one)
--   AT_RISK  not in those, but in the `lapsed_window_months` before
--   LAPSED   no engagement in the whole lapsed window
--   NEW      younger than the lapsed window and no engagement yet (not judged)
-- Windows come from fan_params. Used by mart_fan_activeness and the addressable-audience models.
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

)

select fan_account_id, fan_group, event_month, mi, state from state
