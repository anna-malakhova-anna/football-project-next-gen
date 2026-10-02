{{ config(tags=['phase4']) }}
-- EXEC share: does registering a child change a household's fan engagement? The naive and the matched estimate side by side, with a caveat on every row.
-- AGGREGATE ONLY, built from the restricted `linkage` schema (ADR-009): no household, account or contact leaves it. Small cells are suppressed: if fewer
-- than k_min households stand behind an estimate, the estimate and its interval are hidden. The result describes LINKED households only.
with src as (

    select estimator,
           estimate_pct                        as fan_uplift_pct,
           ci_low_pct                          as fan_uplift_ci_low_pct,
           ci_high_pct                         as fan_uplift_ci_high_pct,
           treated_matched                     as fan_treated_households,
           match_rate                          as fan_match_rate
    from {{ ref('mart_fan_outcomes_summary') }}
    where estimator in ('NAIVE', 'DID_ADDITIVE')

)

select estimator, fan_uplift_pct, fan_uplift_ci_low_pct, fan_uplift_ci_high_pct, fan_treated_households, fan_match_rate, suppressed,
       case estimator
           when 'NAIVE' then 'Not a valid estimate: compares households that chose to enroll with those that did not. Shown to be read against the matched estimate. Linked households only.'
           else 'Matched before/after comparison. Describes households linked to a fan account (mostly North American), not all participants. Synthetic data.'
       end as caveat
from {{ suppress_small_cells('src', ['estimator'], ['fan_treated_households'],
        rates={'fan_uplift_pct': ['fan_treated_households'], 'fan_uplift_ci_low_pct': ['fan_treated_households'],
               'fan_uplift_ci_high_pct': ['fan_treated_households'], 'fan_match_rate': ['fan_treated_households']}) }}
order by estimator
