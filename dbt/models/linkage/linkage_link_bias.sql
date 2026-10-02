-- RESTRICTED (schema `linkage`). Who gets linked? Linked households are not a random sample of the program's households, so any analysis on the
-- linked set describes the linked households. This compares linked and unlinked households on country, years active, number of children (participants in the household, including those who have since aged out) and the
-- first year in the data. Counts and shares only, by dimension value.
with h as (

    select
        p.household_id,
        p.country_code,
        p.participants,
        case when p.is_adult_household then 'ADULT_PLAYER' when p.participants >= 3 then '3+' else cast(p.participants as varchar) end as children_band,
        p.last_year - p.first_year + 1                                      as years_active,
        p.first_year,
        l.household_id is not null                                          as is_linked
    from {{ ref('int_household_profile') }} p
    left join (select household_id from {{ ref('link_household_fan_account') }} where link_status = 'LINKED') l using (household_id)

),

long as (

    select 'country' as dimension, country_code as value, is_linked from h
    union all select 'years_active', cast(years_active as varchar), is_linked from h
    union all select 'children', children_band, is_linked from h
    union all select 'first_year', cast(first_year as varchar), is_linked from h

),

g as (

    select dimension, value,
           count(*) filter (where is_linked)       as linked,
           count(*) filter (where not is_linked)   as unlinked
    from long group by 1, 2

)

select
    dimension,
    value,
    linked,
    unlinked,
    linked + unlinked                                                       as households,
    round(linked * 1.0 / (linked + unlinked), 4)                            as link_rate,
    round(linked * 1.0 / sum(linked) over (partition by dimension), 4)      as share_of_linked,
    round((linked + unlinked) * 1.0 / sum(linked + unlinked) over (partition by dimension), 4) as share_of_all_households,
    round(linked * 1.0 / sum(linked) over (partition by dimension) - (linked + unlinked) * 1.0 / sum(linked + unlinked) over (partition by dimension), 4)
                                                                            as share_gap
from g
order by dimension, value
