-- RESTRICTED (schema `linkage`; aggregates only). SYNTHETIC AND ILLUSTRATIVE lifetime value of a fan over the horizon in fan_params (default 36 months, SYNTHETIC CURRENCY):
--   LTV = average monthly net spend per ACTIVE month x expected active months, where expected active months is the area under the Kaplan-Meier fan-survival curve up to the horizon
--   (the restricted mean survival time, sum of S(t) for t = 1 .. horizon). The range comes from the same area under the lower and upper edges of the survival interval.
-- Spend is net of refunds (fct_fan_transaction, orphan refunds excluded) over the months the account was engaged since its origin. This is a simple value, not a forecast: it assumes the
-- spend per active month stays what it was, and that survival beyond the longest observed spell is zero (curves shorter than the horizon are flagged, never extrapolated).
-- Unlinked or non-participant accounts are not participants: that group is shown for contrast and says nothing about non-participant fans as a population.
with s as (select * from {{ ref('mart_fan_survival') }}),

h as (select {{ fan_param('ltv_horizon_months') }} as horizon),

rmst as (

    select fan_group, market_type,
           sum(survival) filter (where months_since_origin <= (select horizon from h))   as expected_active_months,
           sum(ci_low) filter (where months_since_origin <= (select horizon from h))     as expected_active_months_low,
           sum(ci_high) filter (where months_since_origin <= (select horizon from h))    as expected_active_months_high,
           max(months_since_origin)                                                      as longest_observed_month
    from s group by 1, 2

),

spells as (select g.fan_account_id, g.fan_group, g.market_type, g.origin_month from {{ ref('int_fan_account_group') }} g where g.origin_month is not null),

spend as (

    select sp.fan_group, sp.market_type, sum(t.signed_amount) as net_spend, count(distinct t.fan_account_id) as spenders
    from spells sp join {{ ref('fct_fan_transaction') }} t on t.fan_account_id = sp.fan_account_id and t.txn_month >= sp.origin_month
    where t.is_in_net
    group by 1, 2

),

active_months as (

    select sp.fan_group, sp.market_type, count(*) as active_months, count(distinct sp.fan_account_id) as accounts
    from spells sp join {{ ref('fct_fan_engagement_month') }} f on f.fan_account_id = sp.fan_account_id and f.event_month >= sp.origin_month and f.is_active_month
    group by 1, 2

),

rows as (

    select a.fan_group, a.market_type, a.accounts, a.active_months, coalesce(p.net_spend, 0) as net_spend,
           coalesce(p.net_spend, 0) / a.active_months as spend_per_active_month
    from (
        select fan_group, market_type, active_months, accounts from active_months
        union all
        select fan_group, 'ALL', sum(active_months), sum(accounts) from active_months group by 1
    ) a
    left join (
        select fan_group, market_type, net_spend from spend
        union all
        select fan_group, 'ALL', sum(net_spend) from spend group by 1
    ) p using (fan_group, market_type)

)

select
    r.fan_group,
    r.market_type,
    r.accounts,
    round(r.spend_per_active_month, 3)                                      as net_spend_per_active_month,
    round(m.expected_active_months, 2)                                      as expected_active_months,
    round(r.spend_per_active_month * m.expected_active_months, 2)           as ltv,
    round(r.spend_per_active_month * m.expected_active_months_low, 2)       as ltv_low,
    round(r.spend_per_active_month * m.expected_active_months_high, 2)      as ltv_high,
    m.longest_observed_month >= (select horizon from h)                     as horizon_observed,
    (select horizon from h)                                                 as horizon_months,
    'synthetic currency, illustrative'                                      as label,
    '{{ var("methodology_version") }}'                                      as methodology_version
from rows r join rmst m using (fan_group, market_type)
order by r.fan_group, r.market_type
