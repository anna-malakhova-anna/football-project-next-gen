-- RESTRICTED (schema `linkage`; counts only). THE ADDRESSABLE AUDIENCE over time (rework spec 5.5), by month end and household group (ALL, EXISTING_FAN, NET_NEW_FLAG_PROMPT, NET_NEW_OTHER, UNLINKED):
--   participant households registered by then -> linked -> contactable (at least one channel opted in, guardian account) -> by channel (email, sms, push)
--   the CONSENT GAP: households whose account is ACTIVE at the month end but with NO channel opted in. They are engaged and we cannot talk to them.
--   consent_gap_value: the gap valued, SYNTHETIC CURRENCY and ILLUSTRATIVE, at the MEDIAN trailing 12-month net spend of the monetized linked households that month (so it is an opportunity size,
--   not revenue: it assumes a household we could contact would spend like a typical monetized one).
-- Governance sets the size of the marketable audience: a household with no recorded opt-in is not contactable, and a household with no consent record at all is not "no". UNLINKED households have
-- no account and so no consent: never counted as contactable. Guardians only: every account holder is an adult (a contract ERROR and a test).
with a as (select * from {{ ref('int_household_audience_month') }}),

median_spend as (

    select month, quantile_cont(trailing_net_spend, 0.5) as median_monetized_spend
    from a where is_linked and trailing_net_spend > 0 group by 1

),

g as (

    select
        month, household_group,
        count(*)                                                            as households_registered,
        count(*) filter (where is_linked)                                   as linked_households,
        count(*) filter (where is_contactable)                              as contactable_households,
        count(*) filter (where opted_in_email)                              as contactable_email,
        count(*) filter (where opted_in_sms)                                as contactable_sms,
        count(*) filter (where opted_in_push)                               as contactable_push,
        count(*) filter (where is_active)                                   as active_households,
        count(*) filter (where is_active and not is_contactable)            as consent_gap_households
    from a group by grouping sets ((month, household_group), (month))

)

select
    g.month,
    coalesce(g.household_group, 'ALL')                                      as household_group,
    households_registered, linked_households, contactable_households, contactable_email, contactable_sms, contactable_push, active_households, consent_gap_households,
    round(contactable_households * 1.0 / nullif(linked_households, 0), 4)   as contactable_share_of_linked,
    round(contactable_households * 1.0 / nullif(households_registered, 0), 4) as contactable_share_of_registered,
    round(consent_gap_households * 1.0 / nullif(active_households, 0), 4)   as consent_gap_share_of_active,
    round(m.median_monetized_spend, 2)                                      as median_monetized_spend,
    round(consent_gap_households * m.median_monetized_spend, 0)             as consent_gap_value,
    'synthetic currency, illustrative'                                      as label,
    '{{ var("methodology_version") }}'                                      as methodology_version
from g left join median_spend m using (month)
order by month, household_group
