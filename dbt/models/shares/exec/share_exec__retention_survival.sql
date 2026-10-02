{{ config(tags=['phase4']) }}
-- EXEC share: Kaplan-Meier retention by segment (sex, entry age band, entry country, multi-org at entry, entry division) and years since entry, with 95%
-- intervals. A player who turns 18 or whose follow-up ends with the data is CENSORED, not counted as gone (see the metric catalog). Aggregate only: a step
-- with fewer than k_min entrants at risk, or a segment with fewer than k_min entrants, is suppressed.
with src as (

    select segment_type, segment_value, years_since_entry,
           n_entrants as entry_cohort_size, at_risk as km_at_risk,
           survival as km_survival, ci_low as km_survival_ci_low, ci_high as km_survival_ci_high
    from {{ ref('mart_retention_survival') }}

)

select segment_type, segment_value, years_since_entry, entry_cohort_size, km_at_risk, km_survival, km_survival_ci_low, km_survival_ci_high, suppressed
from {{ suppress_small_cells('src', ['segment_type', 'segment_value', 'years_since_entry'], ['km_at_risk', 'entry_cohort_size'],
        rates={'km_survival': ['km_at_risk'], 'km_survival_ci_low': ['km_at_risk'], 'km_survival_ci_high': ['km_at_risk']}) }}
order by segment_type, segment_value, years_since_entry
