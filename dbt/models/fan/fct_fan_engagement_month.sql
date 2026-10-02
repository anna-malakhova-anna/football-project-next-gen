-- Engagement by fan account (duplicates collapsed) x month, dense from the account's first month to the last month of the data, with zeros: a quiet month is information.
--   * events are counted once per event_id (the first delivery); a duplicate delivery never counts
--   * an event belongs to the month of its event_ts, never the month of the file that delivered it (a late arrival lands where it happened)
--   * events that fall before the account's first month (a clock-skewed timestamp) are not counted: at most a handful
-- is_active_month is "at least one event". Spend lives in fct_fan_transaction.
with ev as (

    select x.fan_account_id, e.event_month, e.event_type
    from {{ ref('stg_fan_events') }} e
    join {{ ref('int_fan_account_xref') }} x using (account_id)
    where not e.is_duplicate and 'orphan_event' <> all(e.dq_flags) and 'unmapped_event_type' <> all(e.dq_flags)

),

by_month as (

    select
        fan_account_id, event_month,
        count(*)                                                            as events,
        count(*) filter (where event_type = 'app_open')                     as app_opens,
        count(*) filter (where event_type = 'content_view')                 as content_views,
        count(*) filter (where event_type = 'game_stream')                  as game_streams,
        count(*) filter (where event_type = 'newsletter_click')             as newsletter_clicks,
        count(*) filter (where event_type = 'fantasy_activity')             as fantasy_activities,
        count(*) filter (where event_type = 'flag_content_view')            as flag_content_views
    from ev group by 1, 2

),

grid as (

    select d.fan_account_id, d.market_id, m.month as event_month
    from {{ ref('dim_fan_account') }} d
    join (
        select unnest(generate_series(
            make_date((select first_observed_year from {{ ref('observation_window') }}), 1, 1),
            make_date((select last_observed_year from {{ ref('observation_window') }}), 12, 1), interval 1 month))::date as month
    ) m on m.month >= date_trunc('month', d.first_created_at)::date

)

select
    g.fan_account_id,
    g.market_id,
    g.event_month,
    coalesce(b.events, 0)                                                   as events,
    coalesce(b.app_opens, 0)                                                as app_opens,
    coalesce(b.content_views, 0)                                            as content_views,
    coalesce(b.game_streams, 0)                                             as game_streams,
    coalesce(b.newsletter_clicks, 0)                                        as newsletter_clicks,
    coalesce(b.fantasy_activities, 0)                                       as fantasy_activities,
    coalesce(b.flag_content_views, 0)                                       as flag_content_views,
    coalesce(b.events, 0) > 0                                               as is_active_month
from grid g
left join by_month b on b.fan_account_id = g.fan_account_id and b.event_month = g.event_month
