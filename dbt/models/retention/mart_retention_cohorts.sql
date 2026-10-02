-- The classic cohort triangle: entry cohort x years since entry, with how many of the cohort were registered that year and what share that is.
-- This is the SIMPLE view (share of the cohort still registered). It is NOT corrected for age-outs, so it falls for cohorts of older youth even when
-- nobody chose to leave: `eligible` removes the players who have aged past the youth range, and `retention_among_eligible` is the fairer share.
-- Only cells that are observable are present (entry_year + k <= last observed year). Grains: ALL, COUNTRY (entry country, attributed) and SEX.
-- The entry cohort excludes the first data year (left-censored). Counts are internal (not a share): the exec share applies small-cell rules.
{% set youth_max = privacy_param('youth_max_age') %}
with s as (select * from {{ ref('retention_spells') }} where age_known),

ks as (select unnest(range(0, (select last_observed_year - first_observed_year + 1 from {{ ref('observation_window') }}))) as k),

cells as (

    select
        s.participant_id, s.entry_year, s.entry_country, s.entry_sex, ks.k,
        exists (select 1 from {{ ref('fct_participant_year') }} f
                where f.participant_id = s.participant_id and f.participation_year = s.entry_year + ks.k)   as active,
        (s.entry_age + ks.k <= {{ youth_max }} or s.entry_age > {{ youth_max }})                         as eligible
    from s join ks on s.entry_year + ks.k <= (select last_observed_year from {{ ref('observation_window') }})

),

g as (

    select
        entry_year, k,
        entry_country, entry_sex,
        grouping(entry_country, entry_sex)                                  as gid,
        count(*)                                                            as cohort_size,
        count(*) filter (where active)                                      as active_count,
        count(*) filter (where eligible)                                    as eligible_count,
        count(*) filter (where active and eligible)                         as active_eligible_count
    from cells
    group by grouping sets ((entry_year, k), (entry_year, k, entry_country), (entry_year, k, entry_sex))

)

select
    entry_year,
    k                                                                       as years_since_entry,
    case gid when 3 then 'ALL' when 2 then 'SEX' else 'COUNTRY' end         as grain,
    entry_country                                                           as country_code,
    entry_sex                                                               as sex,
    cohort_size,
    active_count,
    round(active_count * 1.0 / cohort_size, 5)                              as retention_pct,
    eligible_count,
    round(active_eligible_count * 1.0 / nullif(eligible_count, 0), 5)       as retention_among_eligible,
    '{{ var("methodology_version") }}'                                      as methodology_version
from g
where gid in (3, 2, 1)
order by entry_year, grain, country_code, sex, k
