-- EXEC share: a hierarchy year -> country -> age band, with the girls' share of youth participation at every level.
-- NULL country / age band = rolled up. Counts and the share are suppressed per macro suppress_small_cells; the share is
-- hidden whenever its youth or youth-girls count is small.
with s as (

    select participation_year, country_code, age_band, participants, youth_participants, youth_girls_participants,
           girls_share_of_youth, grouping_id
    from {{ ref('mart_participation_segments') }}

),

src as (

    select participation_year, country_code, age_band, participants, youth_participants, youth_girls_participants, girls_share_of_youth
    from s where grouping_id in (31, 15, 7)

)

select participation_year, country_code, age_band, participants, girls_share_of_youth, suppressed
from {{ suppress_small_cells('src', ['participation_year', 'country_code', 'age_band'], ['participants'],
        rates={'girls_share_of_youth': ['youth_girls_participants', 'youth_participants']}) }}
order by participation_year, country_code nulls first, age_band nulls first
