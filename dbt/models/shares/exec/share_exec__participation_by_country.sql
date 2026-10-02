-- EXEC share: year x country in both labelled views. A NULL country is the year total (additive attributed view only; the
-- presence view is non-additive, so it has no total). participants_present is never used for a global figure.
with c as (select participation_year, country_code, participants_attributed, participants_present from {{ ref('mart_participation_by_country') }}),

src as (

    select participation_year, cast(null as varchar) as country_code,
           unique_participants as participants_attributed, cast(null as bigint) as participants_present
    from {{ ref('mart_participation_global') }}
    union all
    select participation_year, country_code, participants_attributed, participants_present from c

)

select participation_year, country_code, participants_attributed, participants_present, suppressed
from {{ suppress_small_cells('src', ['participation_year', 'country_code'], ['participants_attributed', 'participants_present'],
        secondary_col='participants_attributed') }}
order by participation_year, country_code nulls first
