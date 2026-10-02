{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). Did the observed households (participants grouped by shared guardian contact) match the true households?
--   pure     every member of the observed household belongs to one true household (a mixed household would join two families)
--   split    a true household's participants ended up in more than one observed household (siblings whose contacts never overlapped)
with truth as (

    select b.participant_id, coalesce(max(pr.household_id), min(t.true_person_id)) as true_household
    from {{ ref('bridge_registration_participant') }} b
    join {{ ref('eval_record_truth') }} t on t.match_record_id = b.registration_key
    join {{ source('ground_truth', 'person_registry') }} pr on pr.true_person_id = t.true_person_id
    group by 1

),

m as (select h.household_id, h.participant_id, t.true_household from {{ ref('int_household') }} h join truth t using (participant_id)),

obs as (select household_id, count(distinct true_household) as true_households from m group by 1),

tru as (select true_household, count(distinct household_id) as observed_households from m group by 1)

select 'observed_households' as measure, count(*) as n, cast(null as double) as share from obs
union all select 'observed_households_pure', count(*) filter (where true_households = 1), count(*) filter (where true_households = 1) * 1.0 / count(*) from obs
union all select 'true_households_in_data', count(*), null from tru
union all select 'true_households_split', count(*) filter (where observed_households > 1), count(*) filter (where observed_households > 1) * 1.0 / count(*) from tru
