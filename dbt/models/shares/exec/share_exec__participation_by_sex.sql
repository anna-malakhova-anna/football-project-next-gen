-- EXEC share: unique participants by registration-reported sex (F, M, U) with a year total. U (not captured) is its own
-- category and is never imputed. A small U cell is primary-suppressed and, with the year total published, the next
-- smallest sex cell is suppressed too so U cannot be recovered by subtraction.
with s as (select participation_year, sex, participants, grouping_id from {{ ref('mart_participation_segments') }}),

src as (

    select participation_year, sex, participants from s where grouping_id in (31, 29)

)

select participation_year, sex, participants, suppressed
from {{ suppress_small_cells('src', ['participation_year', 'sex'], ['participants']) }}
order by participation_year, sex nulls first
