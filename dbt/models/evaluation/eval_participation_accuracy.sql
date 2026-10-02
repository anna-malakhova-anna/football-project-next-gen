{{ config(tags=['phase3']) }}
-- GROUND TRUTH (evaluation only; the only Phase 3 model allowed to read it). Did the label-free identity bounds
-- contain the synthetic truth? Per year (GLOBAL) and per attributed country (COUNTRY): true participants vs low / point /
-- high, and whether truth falls inside [low, high]. Also the true vs predicted counts of multi-country and multi-org
-- participants. The memo reports the bounds and, separately and labelled, how they compared with this synthetic truth.
with truth as (

    select r.participation_year, t.true_person_id, r.country_code, r.organization_id, r.term_order, r.registered_at, r.registration_key,
           row_number() over (partition by t.true_person_id, r.participation_year
                              order by r.term_order desc, r.registered_at desc nulls last, r.registration_key) as recency_rank
    from {{ ref('fct_registration') }} r
    join {{ ref('eval_record_truth') }} t on t.match_record_id = r.registration_key
    where r.is_valid_registration

),

true_global as (

    select participation_year, null as country_code, 'GLOBAL' as grain, count(distinct true_person_id) as true_participants
    from truth group by participation_year

),

true_country as (

    select participation_year, country_code, 'COUNTRY' as grain, count(*) as true_participants
    from truth where recency_rank = 1 group by participation_year, country_code

),

true_counts as (select * from true_global union all select * from true_country),

true_multi as (

    select participation_year,
           count(*) filter (where n_countries > 1) as true_multi_country,
           count(*) filter (where n_orgs > 1) as true_multi_org
    from (select participation_year, true_person_id, count(distinct country_code) as n_countries, count(distinct organization_id) as n_orgs
          from truth group by 1, 2) group by 1

),

predicted_multi as (

    select participation_year, count(*) filter (where is_multi_country) as predicted_multi_country,
           count(*) filter (where is_multi_org) as predicted_multi_org
    from {{ ref('fct_participant_year') }} group by 1

)

select
    u.participation_year,
    u.grain,
    u.country_code,
    t.true_participants,
    u.participants_low,
    u.participants_point,
    u.participants_high,
    t.true_participants between u.participants_low and u.participants_high as truth_within_range,
    u.participants_point - t.true_participants                              as point_error,
    round((u.participants_point - t.true_participants) * 100.0 / t.true_participants, 3) as point_error_pct,
    round((u.participants_high - u.participants_low) * 100.0 / u.participants_point, 3) as range_pct,
    case when u.grain = 'GLOBAL' then m.true_multi_country end              as true_multi_country_participants,
    case when u.grain = 'GLOBAL' then pm.predicted_multi_country end        as predicted_multi_country_participants,
    case when u.grain = 'GLOBAL' then m.true_multi_org end                  as true_multi_org_participants,
    case when u.grain = 'GLOBAL' then pm.predicted_multi_org end            as predicted_multi_org_participants
from {{ ref('mart_identity_uncertainty') }} u
join true_counts t on t.participation_year = u.participation_year and t.grain = u.grain and t.country_code is not distinct from u.country_code
left join true_multi m on m.participation_year = u.participation_year
left join predicted_multi pm on pm.participation_year = u.participation_year
order by u.participation_year, u.grain desc, u.country_code
