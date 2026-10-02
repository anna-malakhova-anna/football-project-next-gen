{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). Did the combined-reach RANGE (reported headcount + participants, with the overlap bounded) contain the
-- true combined reach, and how wrong would the naive sum have been? Per participation year, global.
--   true_overlap_memberships  registered participants who sit in a program (per program: one membership)
--   true_combined_reach       true distinct participants + true program headcount - true overlap memberships
--   naive_sum                 participants (point) + reported headcount, i.e. pretending the two do not overlap
-- The bounds are label-free; truth is read here only to grade them. Labelled synthetic.
with truth_programs as (

    select year as participation_year, sum(true_total) as true_headcount, sum(overlap_count) as true_overlap_memberships,
           count(*) as true_programs
    from {{ source('ground_truth', 'school_truth') }} group by 1

),

true_people as (

    select participation_year, true_participants
    from {{ ref('eval_participation_accuracy') }} where grain = 'GLOBAL'

),

m as (select * from {{ ref('mart_reported_headcount') }} where country_code = 'ALL'),

u as (select participation_year, participants_point from {{ ref('mart_identity_uncertainty') }} where grain = 'GLOBAL')

select
    m.participation_year,
    t.true_programs,
    t.true_headcount,
    m.reported_headcount,
    m.reported_headcount - t.true_headcount                                 as headcount_error,
    t.true_overlap_memberships,
    m.max_overlap,
    t.true_overlap_memberships <= m.max_overlap                             as overlap_within_bound,
    p.true_participants + t.true_headcount - t.true_overlap_memberships     as true_combined_reach,
    m.combined_reach_low,
    m.combined_reach_high,
    (p.true_participants + t.true_headcount - t.true_overlap_memberships) between m.combined_reach_low and m.combined_reach_high
                                                                            as truth_inside_range,
    u.participants_point + m.reported_headcount                             as naive_sum,
    (u.participants_point + m.reported_headcount) - (p.true_participants + t.true_headcount - t.true_overlap_memberships)
                                                                            as naive_sum_error
from m
join truth_programs t using (participation_year)
join true_people p using (participation_year)
join u using (participation_year)
order by 1
