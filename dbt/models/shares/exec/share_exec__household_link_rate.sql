{{ config(tags=['phase4']) }}
-- EXEC share: how many program households can be reached through a fan account, by country, with a total (NULL country). Counts and a rate only, small
-- cells suppressed. Linked households are not a random sample of households (ADR-009): this table shows who is reachable, which is why every
-- result built on the linkage is labelled "linked households only".
with src as (

    select case when dimension = 'country' then value end as country_code,
           households as program_households, linked as linked_households, link_rate as household_link_rate
    from {{ ref('linkage_link_bias') }} where dimension = 'country'
    union all
    select cast(null as varchar), sum(households), sum(linked), sum(linked) * 1.0 / sum(households)
    from {{ ref('linkage_link_bias') }} where dimension = 'country'

)

select country_code, program_households, linked_households, household_link_rate, suppressed
from {{ suppress_small_cells('src', ['country_code'], ['program_households', 'linked_households'],
        rates={'household_link_rate': ['program_households', 'linked_households']}) }}
order by country_code nulls first
