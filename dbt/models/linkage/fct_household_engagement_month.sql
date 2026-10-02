-- RESTRICTED (schema `linkage`). Engagement by fan unit x month. Spend is NOT here: purchases are transactions now (fct_fan_transaction, rework step 4). A fan unit is one account: a LINKED account stands for its participant household
-- (household_id set), every other account is a comparison unit (household_id NULL). Unlinked accounts include some participant households whose
-- account could not be linked; that contamination of the comparison group is real and cannot be removed without the truth (eval_fan_effect measures it).
--   * events are counted once per event_id (the first delivery): a duplicate delivery never counts
--   * an event belongs to the month of its event_ts, never the month of the file that delivered it (late arrivals land where they happened)
--   * every month from the account's creation month to the last observed month is present, with zeros: a quiet month is information
with ev as (

    select account_id, event_month, event_type, value
    from {{ ref('stg_fan_events') }}
    where not is_duplicate and 'orphan_event' <> all(dq_flags) and 'unmapped_event_type' <> all(dq_flags)

),

by_month as (

    select
        account_id,
        event_month,
        count(*)                                                            as events,
        count(*) filter (where event_type = 'app_open')                     as app_opens,
        count(*) filter (where event_type = 'content_view')                 as content_views,
        count(*) filter (where event_type = 'game_stream')                  as game_streams,
        count(*) filter (where event_type = 'newsletter_click')             as newsletter_clicks,
        count(*) filter (where event_type = 'fantasy_activity')             as fantasy_activities,
        count(*) filter (where event_type = 'flag_content_view')            as flag_content_views
    from ev group by 1, 2

),

units as (

    select
        a.account_id,
        date_trunc('month', a.created_at)::date                             as created_month,
        l.household_id
    from {{ ref('stg_fan_accounts') }} a
    left join (select account_id, household_id from {{ ref('link_household_fan_account') }} where link_status = 'LINKED') l using (account_id)

),

grid as (

    select u.account_id, u.household_id, u.household_id is not null as is_linked, m.month as event_month
    from units u
    join (
        select unnest(generate_series(
            make_date((select first_observed_year from {{ ref('observation_window') }}), 1, 1),
            make_date((select last_observed_year from {{ ref('observation_window') }}), 12, 1), interval 1 month))::date as month
    ) m on m.month >= u.created_month

)

select
    g.account_id,
    g.household_id,
    g.is_linked,
    g.event_month,
    coalesce(b.events, 0)                                                   as events,
    coalesce(b.app_opens, 0)                                                as app_opens,
    coalesce(b.content_views, 0)                                            as content_views,
    coalesce(b.game_streams, 0)                                             as game_streams,
    coalesce(b.newsletter_clicks, 0)                                        as newsletter_clicks,
    coalesce(b.fantasy_activities, 0)                                       as fantasy_activities,
    coalesce(b.flag_content_views, 0)                                       as flag_content_views
from grid g
left join by_month b on b.account_id = g.account_id and b.event_month = g.event_month
