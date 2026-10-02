{{ config(tags=['phase4']) }}
-- ANALYST share: the event study at aggregate level, by month relative to a household's first registration (-12 to +18). Participants vs matched comparisons,
-- the effect and its standard error. AGGREGATE ONLY, from the restricted `linkage` schema (ADR-009): no household or account level data. A month with fewer
-- than k_min participant households behind it is suppressed. Linked households only.
with src as (

    select months_since_event,
           treated_households                  as fan_treated_households,
           treated_mean_events                 as fan_treated_mean_events,
           comparison_mean_events              as fan_comparison_mean_events,
           effect_pct                          as fan_event_study_effect_pct,
           diff_se                             as fan_event_study_diff_se
    from {{ ref('mart_fan_did') }}

)

select months_since_event, fan_treated_households, fan_treated_mean_events, fan_comparison_mean_events, fan_event_study_effect_pct, fan_event_study_diff_se, suppressed
from {{ suppress_small_cells('src', ['months_since_event'], ['fan_treated_households'],
        rates={'fan_treated_mean_events': ['fan_treated_households'], 'fan_comparison_mean_events': ['fan_treated_households'],
               'fan_event_study_effect_pct': ['fan_treated_households'], 'fan_event_study_diff_se': ['fan_treated_households']}) }}
order by months_since_event
