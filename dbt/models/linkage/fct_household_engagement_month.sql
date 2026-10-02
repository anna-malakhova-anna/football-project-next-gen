-- RESTRICTED (schema `linkage`). Engagement by fan unit x month. A fan unit is one CANONICAL fan account (duplicate accounts of a household are collapsed first): a LINKED account stands for
-- its participant household (household_id set), every other account is a comparison unit (household_id NULL). Unlinked accounts include some participant households whose account could not
-- be linked; that contamination of the comparison group is real and cannot be removed without the truth (eval_fan_effect measures it).
-- Built on fct_fan_engagement_month, which counts each event once, in the month of its event_ts, and is dense from the account's first month with zeros. Spend is in fct_fan_transaction.
select
    f.fan_account_id                                                        as account_id,
    l.household_id,
    l.household_id is not null                                              as is_linked,
    f.event_month,
    f.events,
    f.app_opens,
    f.content_views,
    f.game_streams,
    f.newsletter_clicks,
    f.fantasy_activities,
    f.flag_content_views
from {{ ref('fct_fan_engagement_month') }} f
left join (select account_id, household_id from {{ ref('link_household_fan_account') }} where link_status = 'LINKED') l on l.account_id = f.fan_account_id
