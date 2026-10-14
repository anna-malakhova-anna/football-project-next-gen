{{ config(tags=['phase5']) }}
-- PRIVACY share: how identifying is the analyst share as published? Equivalence classes over (year, birth year, postal prefix, sex, country), the same quasi-identifiers the
-- share_analyst_k_anonymity_warning test counts. One row per year. Aggregates only.
with c as (

    select participation_year, birth_year, postal_prefix, sex, attributed_country_code, count(*) as class_size
    from {{ ref('share_analyst__participant_year') }}
    group by all

)

select
    participation_year,
    sum(class_size)                                                                         as participant_years,
    count(*)                                                                                as equivalence_classes,
    min(class_size)                                                                         as smallest_class,
    round(sum(class_size) * 1.0 / count(*), 2)                                              as average_class_size,
    round(100.0 * sum(class_size) filter (where class_size = 1) / sum(class_size), 2)      as pct_unique,
    round(100.0 * sum(class_size) filter (where class_size < {{ privacy_param('analyst_k_warn') }}) / sum(class_size), 2) as pct_rows_below_k_warn,
    round(100.0 * sum(class_size) filter (where class_size < {{ privacy_param('k_min') }}) / sum(class_size), 2)           as pct_rows_below_k_min
from c
group by participation_year
order by participation_year
