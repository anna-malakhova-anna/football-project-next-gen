{{ config(tags=['phase4']) }}
-- EXEC share: how long do fan accounts stay active? Kaplan-Meier survival by fan group and months since the account's origin, with a 95% interval. A lapse is a long gap in engagement (fan_params);
-- accounts still active at the end of the data are censored, not counted as lapsed. AGGREGATE ONLY (restricted `linkage` schema, ADR-009). Months with fewer than k_min accounts at risk are suppressed.
with src as (

    select fan_group, months_since_origin, at_risk as survival_at_risk, survival as fan_survival, ci_low as fan_survival_ci_low, ci_high as fan_survival_ci_high
    from {{ ref('mart_fan_survival') }}
    where market_type = 'ALL' and reliable

)

select fan_group, months_since_origin, survival_at_risk, fan_survival, fan_survival_ci_low, fan_survival_ci_high, suppressed
from {{ suppress_small_cells('src', ['fan_group', 'months_since_origin'], ['survival_at_risk'],
        rates={'fan_survival': ['survival_at_risk'], 'fan_survival_ci_low': ['survival_at_risk'], 'fan_survival_ci_high': ['survival_at_risk']}) }}
order by fan_group, months_since_origin
