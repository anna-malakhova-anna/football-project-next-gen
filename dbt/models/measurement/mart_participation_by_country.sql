-- Participation by year and country, in BOTH views (rule C6), each labelled:
--   participants_attributed  ADDITIVE: a person is assigned to the country of their most recent registration in the year,
--                            so the countries sum to the global unique participants
--   participants_present     NON-ADDITIVE: a person is counted in every country they played in, so the countries sum to
--                            MORE than the global count; use it for "who played here", never for a global total
--   registrations            ADDITIVE: valid registrations in the country (sums to the global registrations)
with attributed as (

    select participation_year, attributed_country_code as country_code, count(*) as participants_attributed
    from {{ ref('fct_participant_year') }} group by 1, 2

),

present as (

    select participation_year, country_code, count(*) as participants_present
    from (select participation_year, participant_id, unnest(countries_played) as country_code from {{ ref('fct_participant_year') }})
    group by 1, 2

),

regs as (

    select participation_year, country_code, count(*) as registrations
    from {{ ref('fct_registration') }} where is_valid_registration group by 1, 2

)

select
    coalesce(a.participation_year, p.participation_year)                    as participation_year,
    coalesce(a.country_code, p.country_code)                                as country_code,
    coalesce(a.participants_attributed, 0)                                  as participants_attributed,
    coalesce(p.participants_present, 0)                                     as participants_present,
    coalesce(r.registrations, 0)                                            as registrations,
    '{{ var("methodology_version") }}'                                      as methodology_version
from attributed a
full outer join present p on p.participation_year = a.participation_year and p.country_code = a.country_code
left join regs r on r.participation_year = coalesce(a.participation_year, p.participation_year)
                and r.country_code = coalesce(a.country_code, p.country_code)
order by 1, 2
