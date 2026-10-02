{{ config(tags=['phase4']) }}
-- EXEC share: reported headcount from school and recreation programs (Source E), year x country, with a year total (NULL country) and the
-- combined-reach RANGE beside it. These are program-place counts, NOT participants, and they are not added to unique_participants.
-- Small programs are small cells: a country-year with fewer than k_min reported programs is suppressed (reporting_programs is the count that
-- decides), and the headcounts and reach bounds are hidden whenever reporting_programs is small, because a handful of programs can be named.
with src as (

    select participation_year,
           case when country_code = 'ALL' then cast(null as varchar) else country_code end as country_code,
           program_count as reporting_programs, reported_headcount, voluntary_headcount as voluntary_program_headcount,
           combined_reach_low, combined_reach_high
    from {{ ref('mart_reported_headcount') }}

)

select participation_year, country_code, reporting_programs, reported_headcount, voluntary_program_headcount, combined_reach_low, combined_reach_high, suppressed
from {{ suppress_small_cells('src', ['participation_year', 'country_code'], ['reporting_programs'],
        rates={'reported_headcount': ['reporting_programs'], 'voluntary_program_headcount': ['reporting_programs'],
               'combined_reach_low': ['reporting_programs'], 'combined_reach_high': ['reporting_programs']}) }}
order by participation_year, country_code nulls first
