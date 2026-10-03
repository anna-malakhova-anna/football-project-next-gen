{{ config(tags=['phase4']) }}
-- EXEC share: does registering a child change what existing fans do and spend? Matched before/after difference per household-month, by status group and outcome, with the naive percentage next to it.
-- A percentage is shown only where the baseline is large enough for it to be stable (otherwise the per-month difference is the headline). AGGREGATE ONLY (restricted `linkage` schema, ADR-009).
-- Describes LINKED households only; money is SYNTHETIC CURRENCY.
with src as (

    select status_group as uplift_status_group, outcome as uplift_outcome, outcome_kind as uplift_outcome_kind, treated_households as uplift_households,
           did_per_month as uplift_per_month, did_ci_low_per_month as uplift_ci_low_per_month, did_ci_high_per_month as uplift_ci_high_per_month,
           case when pct_is_stable then did_pct end as uplift_pct, naive_pct as uplift_naive_pct
    from {{ ref('mart_fan_value_uplift') }}

)

select uplift_status_group, uplift_outcome, uplift_outcome_kind, uplift_households, uplift_per_month, uplift_ci_low_per_month, uplift_ci_high_per_month, uplift_pct, uplift_naive_pct, suppressed
from {{ suppress_small_cells('src', ['uplift_status_group', 'uplift_outcome'], ['uplift_households'],
        rates={'uplift_per_month': ['uplift_households'], 'uplift_ci_low_per_month': ['uplift_households'], 'uplift_ci_high_per_month': ['uplift_households'],
               'uplift_pct': ['uplift_households'], 'uplift_naive_pct': ['uplift_households']}, passthrough=['uplift_outcome_kind']) }}
order by uplift_status_group, uplift_outcome
