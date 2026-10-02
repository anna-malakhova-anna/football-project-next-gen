-- EXEC share: unique participants by growth status (new / returning / reactivated / censored) as a hierarchy: a year
-- total (status NULL) and its status cells, so secondary suppression can protect a hidden status count. Status counts
-- sum to the year total. CENSORED is the first data year, whose history is unknown.
with g as (

    select participation_year, unique_participants, new_participants, returning_participants,
           reactivated_participants, censored_participants
    from {{ ref('mart_participation_global') }}

),

src as (

    select participation_year, cast(null as varchar) as status, unique_participants as participants from g
    union all select participation_year, 'NEW', new_participants from g
    union all select participation_year, 'RETURNING', returning_participants from g
    union all select participation_year, 'REACTIVATED', reactivated_participants from g
    union all select participation_year, 'CENSORED', censored_participants from g

)

select participation_year, status, participants, suppressed
from {{ suppress_small_cells('src', ['participation_year', 'status'], ['participants']) }}
order by participation_year, status nulls first
