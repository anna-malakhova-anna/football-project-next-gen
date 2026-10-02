-- Division flow year over year, from each division in year t to what the same player did in t+1. Descriptive.
--   STEADY          same division again
--   AGING_FORWARD   moved to the next older division, the one that matches their age in t+1
--   PLAYING_UP      moved to a division older than their age requires
--   MOVED_DOWN      moved to a younger division
--   ADULT_CHANGE    moved between adult divisions
--   YOUTH_TO_ADULT  was in a youth division in t and is in an adult division in t+1
--   NOT_RETURNED    no registration in t+1 and still youth-eligible (a churn event)
--   AGED_OUT        no registration in t+1, and aged past the youth range: neither churn nor transition, shown so the flow adds up
-- Only years where t+1 is observed. share_of_from is the share of everyone who started in that division in year t.
-- `division_rank` is the age order of the divisions; the age a division is meant for is the same rule the divisions use (ages 5-7 U6/U8 ... 14-17 U17).
{% set youth_max = privacy_param('youth_max_age') %}
with rank_map(division, division_rank, is_adult) as (

    values ('U6', 1, false), ('U8', 2, false), ('U10', 3, false), ('U12', 4, false), ('U14', 5, false), ('U17', 6, false),
           ('ADULT_W', 7, true), ('ADULT_M', 7, true), ('ADULT_MIXED', 7, true)

),

age_div(min_age, max_age, division_rank) as (

    values (0, 5, 1), (6, 7, 2), (8, 9, 3), (10, 11, 4), (12, 13, 5), (14, 17, 6), (18, 200, 7)

),

f as (select participant_id, participation_year, age_at_cutoff, primary_division from {{ ref('fct_participant_year') }}),

pairs as (

    select
        a.participation_year                                                as from_year,
        a.primary_division                                                  as from_division,
        a.age_at_cutoff                                                     as age_t,
        b.primary_division                                                  as to_division,
        a.participant_id
    from f a
    left join f b on b.participant_id = a.participant_id and b.participation_year = a.participation_year + 1
    where a.participation_year + 1 <= (select last_observed_year from {{ ref('observation_window') }})
      and a.age_at_cutoff is not null

),

classified as (

    select
        p.from_year, p.from_year + 1 as to_year, p.from_division,
        coalesce(p.to_division, case when p.age_t + 1 > {{ youth_max }} and p.age_t <= {{ youth_max }} then 'AGED_OUT' else 'NOT_RETURNED' end) as to_division,
        case
            when p.to_division is null and p.age_t <= {{ youth_max }} and p.age_t + 1 > {{ youth_max }} then 'AGED_OUT'
            when p.to_division is null then 'NOT_RETURNED'
            when p.to_division = p.from_division then 'STEADY'
            when not rf.is_adult and rt.is_adult then 'YOUTH_TO_ADULT'
            when rf.is_adult and rt.is_adult then 'ADULT_CHANGE'
            when rt.division_rank < rf.division_rank then 'MOVED_DOWN'
            when rt.division_rank = ad.division_rank then 'AGING_FORWARD'
            when rt.division_rank > ad.division_rank then 'PLAYING_UP'
            else 'AGING_FORWARD'
        end                                                                 as flow_type
    from pairs p
    left join rank_map rf on rf.division = p.from_division
    left join rank_map rt on rt.division = p.to_division
    left join age_div ad on p.age_t + 1 between ad.min_age and ad.max_age

)

select
    from_year,
    to_year,
    from_division,
    to_division,
    flow_type,
    count(*)                                                                as participants,
    round(count(*) * 1.0 / sum(count(*)) over (partition by from_year, from_division), 5) as share_of_from,
    '{{ var("methodology_version") }}'                                      as methodology_version
from classified
group by 1, 2, 3, 4, 5
order by from_year, from_division, flow_type, to_division
