{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). The observed fan status of each participant household against the status the generator knows. Truth statuses:
-- NO_ACCOUNT (never a fan account holder), NET_NEW, EXISTING_ACTIVE, BORDERLINE (lapsed 3 to 6 months before), LAPSED_REACTIVATED, LAPSED_DORMANT.
-- The point: UNLINKED is not NO_ACCOUNT. A large share of UNLINKED households do have an account under a different email, which is why UNLINKED is its own line.
with truth_hh as (

    select b.participant_id, coalesce(max(pr.household_id), min(t.true_person_id)) as true_household
    from {{ ref('bridge_registration_participant') }} b
    join {{ ref('eval_record_truth') }} t on t.match_record_id = b.registration_key
    join {{ source('ground_truth', 'person_registry') }} pr on pr.true_person_id = t.true_person_id
    group by 1

),

obs as (

    -- Ties go to the most members, then the true household key: mode() picks an arbitrary value on a tie (differs between machines)
    select h.household_id, t.true_household
    from {{ ref('int_household') }} h join truth_hh t using (participant_id) group by 1, 2
    qualify row_number() over (partition by h.household_id order by count(*) desc, t.true_household) = 1

)

select
    s.fan_status,
    coalesce(f.truth_status, 'UNKNOWN') as truth_status,
    count(*)                            as households,
    count(*) filter (where not s.is_left_censored) as households_not_left_censored
from {{ ref('fct_household_fan_status') }} s
join obs o using (household_id)
left join {{ source('ground_truth', 'fan_truth') }} f on f.household_key = o.true_household and f.is_participant_household
group by 1, 2
order by 1, 2
