{{ config(tags=['phase4']) }}
-- EXEC share: the fan funnel by flag-football cohort year, household segment and fan status (ALL = rolled up, shown as NULL): registered households -> linked to a fan account
-- -> contactable (opted in, guardian account) -> active -> monetized. Counts and step rates, small cells suppressed. AGGREGATE ONLY, built from the restricted `linkage` schema
-- (ADR-009). UNLINKED means unknown, not "not a fan". Linked households only for every step after the first.
with src as (

    select cohort_year,
           nullif(segment, 'ALL')                 as segment,
           nullif(fan_status, 'ALL')              as fan_status,
           households                             as funnel_households,
           linked_households                      as funnel_linked,
           contactable_households                 as funnel_contactable,
           active_households                      as funnel_active,
           monetized_households                   as funnel_monetized,
           link_rate                              as funnel_link_rate,
           contactable_rate                       as funnel_contactable_rate,
           active_rate                            as funnel_active_rate,
           monetized_rate                         as funnel_monetized_rate
    from {{ ref('mart_fan_funnel') }}
    where market_type = 'ALL'

)

select cohort_year, segment, fan_status, funnel_households, funnel_linked, funnel_contactable, funnel_active, funnel_monetized,
       funnel_link_rate, funnel_contactable_rate, funnel_active_rate, funnel_monetized_rate, suppressed
from {{ suppress_small_cells('src', ['cohort_year', 'segment', 'fan_status'],
        ['funnel_households', 'funnel_linked', 'funnel_contactable', 'funnel_active', 'funnel_monetized'],
        rates={'funnel_link_rate': ['funnel_households', 'funnel_linked'], 'funnel_contactable_rate': ['funnel_linked', 'funnel_contactable'],
               'funnel_active_rate': ['funnel_linked', 'funnel_active'], 'funnel_monetized_rate': ['funnel_active', 'funnel_monetized']}) }}
order by cohort_year, segment nulls first, fan_status nulls first
