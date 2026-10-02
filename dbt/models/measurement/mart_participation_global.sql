-- Global participation by year, from the one counting engine (fct_participant_year). Rules C1-C3, C5, C11-C13.
-- unique_participants counts each person once however many leagues, divisions or countries they played in.
-- retention_rate = returning / the prior year's unique participants (defined from the second year).
with y as (select * from {{ ref('fct_participant_year') }}),

regs as (

    select participation_year, count(*) as registrations
    from {{ ref('fct_registration') }} where is_valid_registration group by 1

),

agg as (

    select
        participation_year,
        count(*)                                                            as unique_participants,
        count(*) filter (where is_multi_org)                                as multi_org_participants,
        count(*) filter (where is_multi_country)                            as multi_country_participants,
        count(*) filter (where status = 'NEW')                              as new_participants,
        count(*) filter (where status = 'RETURNING')                        as returning_participants,
        count(*) filter (where status = 'REACTIVATED')                      as reactivated_participants,
        count(*) filter (where status = 'CENSORED')                         as censored_participants
    from y group by 1

)

select
    a.participation_year,
    a.unique_participants,
    r.registrations,
    round(r.registrations * 1.0 / a.unique_participants, 4)                 as registrations_per_participant,
    a.multi_org_participants,
    a.multi_country_participants,
    a.new_participants,
    a.returning_participants,
    a.reactivated_participants,
    a.censored_participants,
    round(a.returning_participants * 1.0 / nullif(p.unique_participants, 0), 4) as retention_rate,
    '{{ var("methodology_version") }}'                                      as methodology_version
from agg a
join regs r using (participation_year)
left join agg p on p.participation_year = a.participation_year - 1
order by 1
