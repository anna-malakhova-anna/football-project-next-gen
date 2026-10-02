-- Duplicate fan accounts for one household, collapsed by deterministic rules (rework spec 4.1): two accounts are the same household when they share a normalized EMAIL, or the
-- same normalized PHONE and postal prefix. Connected components over those edges give the groups; the canonical account is the earliest created (ties: the smaller account_id).
-- No fuzzy matching: a rule a person can check by eye. A phone number alone is NOT enough (a number reused across households has a different postal prefix).
-- One row per account: account_id -> fan_account_id (the canonical account), whether it is a duplicate, and why it was merged.
with a as (select account_id, contact_email, contact_phone, postal_prefix, created_at from {{ ref('stg_fan_accounts') }}),

email_edges as (

    select x.account_id as a, y.account_id as b, 'EMAIL' as reason
    from a x join a y on x.contact_email = y.contact_email and x.account_id < y.account_id
    where x.contact_email is not null

),

phone_edges as (

    select x.account_id as a, y.account_id as b, 'PHONE_POSTAL' as reason
    from a x join a y on x.contact_phone = y.contact_phone and x.postal_prefix = y.postal_prefix and x.account_id < y.account_id
    where x.contact_phone is not null and x.postal_prefix is not null

),

edges as (select a, b from email_edges union select a, b from phone_edges),

nodes as (select account_id as node from a),

cc as {{ connected_components('nodes', 'edges') }},

canon as (

    select cc.node as account_id, cc.cluster_id, cc.cluster_size,
           first_value(cc.node) over (partition by cc.cluster_id order by a.created_at, cc.node) as fan_account_id
    from cc join a on a.account_id = cc.node

),

reasons as (

    select account_id, list_sort(list_distinct(list(reason))) as reasons
    from (select a as account_id, reason from email_edges union all select b, reason from email_edges
          union all select a, reason from phone_edges union all select b, reason from phone_edges)
    group by 1

)

select
    c.account_id,
    c.fan_account_id,
    c.account_id <> c.fan_account_id                                        as is_duplicate,
    c.cluster_size                                                          as accounts_in_household,
    coalesce(r.reasons, [])                                                 as merge_reasons
from canon c left join reasons r using (account_id)
