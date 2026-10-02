{{ config(tags=['phase4']) }}
-- fct_household_engagement_month: one row per account x month; no event_id is counted twice; a late-arriving event is counted in the month of its
-- event_ts, not the month of the file that delivered it; and (almost) every distinct event lands in the fact. The few that do not are events whose
-- (clock-skewed) timestamp falls before the account's creation month: at most 0.01% of events.
with fact as (select account_id, event_month, events from {{ ref('fct_household_engagement_month') }}),

expected as (

    select account_id, event_month, count(*) as events
    from {{ ref('stg_fan_events') }}
    where not is_duplicate and 'orphan_event' <> all(dq_flags) and 'unmapped_event_type' <> all(dq_flags)
    group by 1, 2

)

select 'account_month_twice' as problem, account_id || '|' || cast(event_month as varchar) as detail
from fact group by account_id, event_month having count(*) > 1
union all
select 'event_counted_in_the_wrong_month', e.account_id || '|' || cast(e.event_month as varchar)
from expected e left join fact f using (account_id, event_month)
where coalesce(f.events, 0) <> e.events and e.event_month >= (select date_trunc('month', created_at)::date from {{ ref('stg_fan_accounts') }} a where a.account_id = e.account_id)
union all
select 'too_many_events_lost', cast(lost as varchar)
from (select (select count(*) from {{ ref('stg_fan_events') }} where not is_duplicate) - (select sum(events) from fact) as lost,
             (select count(*) from {{ ref('stg_fan_events') }} where not is_duplicate) as total)
where lost > 0.0001 * total
union all
select 'duplicate_event_id_in_staging_not_flagged', event_id
from {{ ref('stg_fan_events') }} where not is_duplicate group by event_id having count(*) > 1
