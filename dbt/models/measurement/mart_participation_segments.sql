-- Participation by year and segment, with subtotals from the SAME query (GROUPING SETS), so a subtotal can never
-- disagree with its parts. Every participant sits in exactly one cell of every grouping set, so within one
-- (year, grouping_id) the cells sum to the global unique participants. Dimensions are never NULL in the data
-- (age unknown is 'UNKNOWN'), so a NULL dimension in the output means "rolled up", and grouping_id (a bitmask: bit set =
-- dimension rolled up, in the order country, age_band, primary_division, sex, age_group) says which.
-- Girls' share of youth participation is on every row: youth girls / youth participants among the cell's members
-- (sex F over sex F, M and U; U is never imputed, rule C9). Youth = 17 or under at December 31 (rule C10).
with p as (

    select
        participation_year,
        attributed_country_code                                             as country_code,
        age_band,
        primary_division,
        sex,
        case when is_youth then 'YOUTH' when is_youth is false then 'ADULT' else 'UNKNOWN' end as age_group
    from {{ ref('fct_participant_year') }}

),

cells as (

    select
        participation_year,
        country_code,
        age_band,
        primary_division,
        sex,
        age_group,
        grouping(country_code, age_band, primary_division, sex, age_group)  as grouping_id,
        count(*)                                                            as participants,
        count(*) filter (where age_group = 'YOUTH')                         as youth_participants,
        count(*) filter (where age_group = 'YOUTH' and sex = 'F')           as youth_girls_participants
    from p
    group by grouping sets (
        (participation_year),
        (participation_year, country_code),
        (participation_year, age_group),
        (participation_year, sex),
        (participation_year, primary_division),
        (participation_year, age_band),
        (participation_year, country_code, age_group),
        (participation_year, country_code, age_band),
        (participation_year, country_code, sex),
        (participation_year, age_group, sex),
        (participation_year, country_code, age_group, sex),
        (participation_year, country_code, age_band, sex),
        (participation_year, country_code, age_band, primary_division, sex, age_group)
    )

)

select
    participation_year,
    country_code,
    age_band,
    primary_division,
    sex,
    age_group,
    grouping_id,
    concat_ws(' x ', 'year',
        case when country_code is not null then 'country' end,
        case when age_band is not null then 'age_band' end,
        case when primary_division is not null then 'division' end,
        case when sex is not null then 'sex' end,
        case when age_group is not null then 'age_group' end)               as grouping_label,
    participants,
    youth_participants,
    youth_girls_participants,
    round(youth_girls_participants * 1.0 / nullif(youth_participants, 0), 4) as girls_share_of_youth,
    '{{ var("methodology_version") }}'                                      as methodology_version
from cells
order by participation_year, grouping_id, country_code, age_band, primary_division, sex, age_group
