{{ config(tags=['phase4']) }}
-- EXEC share: the cohort triangle for all entrants: entry cohort x years since entry, the share still registered, and the same share among players who have
-- not aged past the youth range. The first is NOT corrected for age-outs, which is why it falls for cohorts of older youth. Aggregate only, small cells suppressed.
with src as (

    select entry_year, years_since_entry, cohort_size as entry_cohort_size,
           retention_pct as cohort_retention_pct, retention_among_eligible as cohort_retention_among_eligible_pct
    from {{ ref('mart_retention_cohorts') }} where grain = 'ALL'

)

select entry_year, years_since_entry, entry_cohort_size, cohort_retention_pct, cohort_retention_among_eligible_pct, suppressed
from {{ suppress_small_cells('src', ['entry_year', 'years_since_entry'], ['entry_cohort_size'],
        rates={'cohort_retention_pct': ['entry_cohort_size'], 'cohort_retention_among_eligible_pct': ['entry_cohort_size']}) }}
order by entry_year, years_since_entry
