{{ config(tags=['phase4']) }}
-- Reported headcount (Source E) by participation year x country, beside the youth participants it could overlap with, and the combined-reach
-- RANGE. This is the only model that sees both worlds, and it reports bounds, never a point estimate:
--   max_overlap   = min(reported headcount, resolved youth participants) per country: nobody can overlap more than either side holds
--   reach_low     = participants_low  + (reported - max_overlap)   (the most overlap possible)
--   reach_high    = participants_high + reported                    (no overlap at all)
-- Rows with country_code = 'ALL' are the global totals. Small programs are suppressed where shared, not here (share layer).
with h as (

    select participation_year, country_code,
           sum(headcount)                                       as reported_headcount,
           sum(headcount) filter (where is_voluntary)           as voluntary_headcount,
           count(*)                                             as program_count
    from {{ ref('fct_reported_headcount') }}
    group by 1, 2

),

youth as (

    select participation_year, attributed_country_code as country_code, count(*) as youth_participants
    from {{ ref('fct_participant_year') }} where is_youth group by 1, 2

),

u as (

    select participation_year, country_code, participants_low, participants_high
    from {{ ref('mart_identity_uncertainty') }} where grain = 'COUNTRY'

),

by_country as (

    select
        h.participation_year,
        h.country_code,
        h.reported_headcount,
        coalesce(h.voluntary_headcount, 0)                  as voluntary_headcount,
        h.program_count,
        coalesce(y.youth_participants, 0)                   as youth_participants,
        least(h.reported_headcount, coalesce(y.youth_participants, 0)) as max_overlap,
        coalesce(u.participants_low, 0)                     as participants_low,
        coalesce(u.participants_high, 0)                    as participants_high
    from h
    left join youth y using (participation_year, country_code)
    left join u using (participation_year, country_code)

),

global as (

    select
        participation_year, 'ALL' as country_code,
        sum(reported_headcount) as reported_headcount, sum(voluntary_headcount) as voluntary_headcount, sum(program_count) as program_count,
        sum(youth_participants) as youth_participants, sum(max_overlap) as max_overlap,
        -- global participants are distinct people, not the sum of the country counts (a mover is in two countries)
        max(g.participants_low) as participants_low, max(g.participants_high) as participants_high
    from by_country
    join {{ ref('mart_identity_uncertainty') }} g using (participation_year)
    where g.grain = 'GLOBAL' group by 1

)

select
    participation_year, country_code, reported_headcount, voluntary_headcount, program_count, youth_participants, max_overlap,
    participants_low, participants_high,
    participants_low + reported_headcount - max_overlap             as combined_reach_low,
    participants_high + reported_headcount                          as combined_reach_high,
    '{{ var("methodology_version") }}'                              as methodology_version
from (select * from by_country union all select * from global)
order by participation_year, country_code
