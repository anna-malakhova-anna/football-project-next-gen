-- RESTRICTED (schema `linkage`; counts only, no household leaves it). The fan acquisition funnel by registration cohort year x market type x segment x fan status:
--   participant households -> linked -> contactable -> active -> monetized -> retained
-- Stages are cumulative (each is a subset of the one before) and measured at the end of the cohort year (int_household_funnel_base). Rows exist for every fan status plus 'ALL'; UNLINKED is its own line and
-- is never dropped. Segments overlap (a household can be a girls' household and a multi-child household), so rows of different segments are not added together. market_type 'ALL' rolls up team and non-team.
-- Each conversion is a step rate: stage / the stage before. `retained` is defined only where the 12-month date is inside the data (households_retention_observable); its rate divides by the monetized
-- households that can be observed. The unconditional counts (`*_regardless`) say how many households have the property whatever the earlier stages (for example active households that cannot be
-- contacted): the gap between them and the nested stage is the cost of the funnel's order.
with b as (select * from {{ ref('int_household_funnel_base') }}),

staged as (

    select
        *,
        st_linked                                                                                   as s_linked,
        st_linked and st_contactable_alone                                                          as s_contactable,
        st_linked and st_contactable_alone and st_active_alone                                      as s_active,
        st_linked and st_contactable_alone and st_active_alone and st_monetized_alone               as s_monetized,
        st_linked and st_contactable_alone and st_active_alone and st_monetized_alone and st_retained_alone and retention_observable as s_retained
    from b

),

segs as (

    select cohort_year, is_left_censored, fan_status, case when is_team_market then 'TEAM' else 'NON_TEAM' end as market_type, unnest(list_filter([
        'ALL',
        case when is_girls_household then 'GIRLS_HOUSEHOLD' end,
        case when is_international then 'INTERNATIONAL' end,
        case when is_adult_household then 'ADULT_PLAYER_HOUSEHOLD' end,
        case when is_multi_child_household then 'MULTI_CHILD_HOUSEHOLD' end
    ], _x -> _x is not null)) as segment,
    s_linked, s_contactable, s_active, s_monetized, s_retained, retention_observable, st_contactable_alone, st_active_alone, st_monetized_alone
    from staged

),

g as (

    select
        cohort_year, market_type, segment, fan_status,
        count(*)                                                            as households,
        count(*) filter (where s_linked)                                    as linked_households,
        count(*) filter (where s_contactable)                               as contactable_households,
        count(*) filter (where s_active)                                    as active_households,
        count(*) filter (where s_monetized)                                 as monetized_households,
        count(*) filter (where s_retained)                                  as retained_households,
        count(*) filter (where s_monetized and retention_observable)        as monetized_retention_observable,
        count(*) filter (where retention_observable)                        as households_retention_observable,
        count(*) filter (where s_linked and st_contactable_alone)           as contactable_regardless,
        count(*) filter (where s_linked and st_active_alone)                as active_regardless,
        count(*) filter (where s_linked and st_monetized_alone)             as monetized_regardless,
        bool_or(is_left_censored)                                           as cohort_is_left_censored,
        grouping(market_type, fan_status)                                   as gid
    from segs
    group by grouping sets ((cohort_year, market_type, segment, fan_status), (cohort_year, segment, fan_status), (cohort_year, market_type, segment), (cohort_year, segment))

)

select
    cohort_year,
    coalesce(market_type, 'ALL')                                            as market_type,
    segment,
    coalesce(fan_status, 'ALL')                                             as fan_status,
    households,
    linked_households,
    contactable_households,
    active_households,
    monetized_households,
    retained_households,
    monetized_retention_observable,
    households_retention_observable,
    contactable_regardless,
    active_regardless,
    monetized_regardless,
    round(linked_households * 1.0 / nullif(households, 0), 4)               as link_rate,
    round(contactable_households * 1.0 / nullif(linked_households, 0), 4)   as contactable_rate,
    round(active_households * 1.0 / nullif(contactable_households, 0), 4)   as active_rate,
    round(monetized_households * 1.0 / nullif(active_households, 0), 4)     as monetized_rate,
    round(retained_households * 1.0 / nullif(monetized_retention_observable, 0), 4) as retained_rate,
    cohort_is_left_censored,
    '{{ var("methodology_version") }}'                                      as methodology_version
from g
order by cohort_year, segment, market_type, fan_status
