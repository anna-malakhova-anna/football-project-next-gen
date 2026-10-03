-- RESTRICTED (schema `linkage`; counts only). HOUSEHOLD SHAPE against fan status and value (rework spec 5.6), as of the last month of the data: adult-player households vs youth households with one
-- child vs several, by years active (1, 2, 3 or more). For each shape: households, how many are linked, net-new fans, active fans, monetized fans (trailing 12-month net spend above zero), and the
-- mean trailing 12-month net spend of the LINKED households (SYNTHETIC CURRENCY). UNLINKED households are in the denominators and are never called non-fans.
with a as (select * from {{ ref('int_household_audience_month') }} where month = (select max(month) from {{ ref('int_household_audience_month') }})),

hp as (select household_id, is_adult_household, participants, years_span from {{ ref('int_household_profile') }}),

j as (

    select
        case when hp.is_adult_household then 'ADULT_PLAYER' when hp.participants >= 2 then 'YOUTH_MULTI_CHILD' else 'YOUTH_ONE_CHILD' end as shape,
        case when hp.years_span >= 3 then '3+' else cast(hp.years_span as varchar) end as years_active,
        a.is_linked, a.fan_status = 'NET_NEW' as is_net_new, a.is_active, a.trailing_net_spend > 0 as is_monetized, a.trailing_net_spend
    from a join hp using (household_id)

)

select
    shape, years_active,
    count(*)                                                                as households,
    count(*) filter (where is_linked)                                       as linked_households,
    count(*) filter (where is_net_new)                                      as net_new_households,
    count(*) filter (where is_active)                                       as active_households,
    count(*) filter (where is_monetized)                                    as monetized_households,
    round(count(*) filter (where is_linked) * 1.0 / count(*), 4)            as link_rate,
    round(count(*) filter (where is_net_new) * 1.0 / count(*), 4)           as net_new_rate,
    round(avg(trailing_net_spend) filter (where is_linked), 2)              as mean_trailing_net_spend_linked,
    '{{ var("methodology_version") }}'                                      as methodology_version
from j group by 1, 2 order by 1, 2
