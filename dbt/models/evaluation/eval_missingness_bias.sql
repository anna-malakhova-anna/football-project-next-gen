{{ config(tags=['phase5']) }}
-- GROUND TRUTH (evaluation only). Girls' share of youth participants against the three figures of mart_missingness_bias: the true share among the true people with a valid registration that
-- year and a youth age at the Dec 31 cutoff (person_registry), the known-only value and its bound interval. Expected: the known-only value differs from the truth by an amount the bounds
-- cover, and the truth lies inside [bound_low, bound_high]. How big the bias is depends on how much is missing: at participant level a child with another record that names the sex is no longer
-- unknown, so the bound interval can be narrow. Reported as found.
with people as (

    select distinct r.participation_year, t.true_person_id
    from {{ ref('fct_registration') }} r join {{ ref('eval_record_truth') }} t on t.match_record_id = r.registration_key where r.is_valid_registration

),

truth as (

    select p.participation_year, count(*) as true_youth,
           count(*) filter (where pr.sex = 'F') as true_girls,
           count(*) filter (where pr.sex = 'F')::double / count(*) as true_share
    from people p join {{ source('ground_truth', 'person_registry') }} pr using (true_person_id)
    where {{ age_at_cutoff('pr.dob', 'p.participation_year') }} < 18
    group by 1

)

select
    b.participation_year,
    t.true_youth, round(t.true_share, 4) as true_girls_share,
    b.value_phase3, b.value_known_only, b.bound_low, b.bound_high, b.missing_share,
    round(b.value_known_only - t.true_share, 4)                             as known_only_error,
    round(b.value_phase3 - t.true_share, 4)                                 as phase3_error,
    b.bound_low - 0.0005 <= t.true_share and t.true_share <= b.bound_high + 0.0005 as truth_inside_bounds,
    abs(b.value_known_only - t.true_share) < abs(b.value_phase3 - t.true_share) as known_only_closer_than_phase3,
    b.missingness_verdict
from {{ ref('mart_missingness_bias') }} b
join truth t on t.participation_year = b.participation_year
where b.kpi = 'girls_share_of_youth' and b.segment_value = 'ALL'
