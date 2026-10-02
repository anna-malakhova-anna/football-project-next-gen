-- The outcomes of the value-uplift analysis, by fan account x month (dense from the account's first month, with zeros): engagement by type (events) and NET spend by category (purchases less
-- refunds; orphan refunds excluded), SYNTHETIC CURRENCY. Built from fct_fan_engagement_month and fct_fan_transaction.
with t as (

    select fan_account_id, txn_month as event_month,
           sum(signed_amount) filter (where category = 'ticket')           as net_spend_ticket,
           sum(signed_amount) filter (where category = 'merch')            as net_spend_merch,
           sum(signed_amount) filter (where category = 'subscription')     as net_spend_subscription,
           sum(signed_amount) filter (where category = 'other')            as net_spend_other,
           sum(signed_amount)                                              as net_spend_total
    from {{ ref('fct_fan_transaction') }} where is_in_net group by 1, 2

)

select
    f.fan_account_id,
    f.event_month,
    f.events, f.app_opens, f.content_views, f.content_views + f.flag_content_views as all_content_views, f.game_streams, f.newsletter_clicks, f.fantasy_activities, f.flag_content_views,
    coalesce(t.net_spend_ticket, 0)                                         as net_spend_ticket,
    coalesce(t.net_spend_merch, 0)                                          as net_spend_merch,
    coalesce(t.net_spend_subscription, 0)                                   as net_spend_subscription,
    coalesce(t.net_spend_other, 0)                                          as net_spend_other,
    coalesce(t.net_spend_total, 0)                                          as net_spend_total
from {{ ref('fct_fan_engagement_month') }} f
left join t on t.fan_account_id = f.fan_account_id and t.event_month = f.event_month
