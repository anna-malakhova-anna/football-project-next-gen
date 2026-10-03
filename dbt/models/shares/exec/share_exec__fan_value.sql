{{ config(tags=['phase4']) }}
-- EXEC share: what is a fan worth? Lifetime value per account over the horizon, with a range, by fan group. SYNTHETIC CURRENCY, ILLUSTRATIVE: a modelled expectation (net spend per
-- active month x expected active months from a Kaplan-Meier lapse curve), not revenue. AGGREGATE ONLY (restricted `linkage` schema, ADR-009); groups with fewer than k_min accounts are suppressed.
with src as (

    select fan_group, accounts as value_accounts, net_spend_per_active_month, expected_active_months, ltv as fan_ltv, ltv_low as fan_ltv_low, ltv_high as fan_ltv_high,
           horizon_months, label as currency_label
    from {{ ref('mart_fan_ltv') }}
    where market_type = 'ALL'

)

select fan_group, value_accounts, net_spend_per_active_month, expected_active_months, fan_ltv, fan_ltv_low, fan_ltv_high, horizon_months, currency_label, suppressed
from {{ suppress_small_cells('src', ['fan_group'], ['value_accounts'],
        rates={'net_spend_per_active_month': ['value_accounts'], 'expected_active_months': ['value_accounts'], 'fan_ltv': ['value_accounts'],
               'fan_ltv_low': ['value_accounts'], 'fan_ltv_high': ['value_accounts']},
        passthrough=['horizon_months', 'currency_label']) }}
order by fan_group
