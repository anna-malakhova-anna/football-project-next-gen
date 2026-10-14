{{ config(tags=['phase5']) }}
-- GROUND TRUTH (evaluation only). Two checks on the parent side of Phase 5:
--   household       pairwise precision and recall of children grouped into households, against the true household
--   activation      of the households marked eligible, how many contain a child whose parent really opted in to marketing (false eligibility = a privacy incident),
--                   and how many households the careless reading would have admitted that never opted in
-- Marketing opt-in in the feeds is generated from the person registry, so a correct pipeline finds no false eligibility.
with child_truth as (

    select r.p5_person_id, min(t.true_person_id) as true_person_id, min(t.household_id) as true_household_id
    from {{ ref('p5_record_person') }} r
    join {{ source('ground_truth', 'p5_registration_truth') }} t on t.feed = r.feed and t.source_record_id = r.source_record_id
    group by 1

),

hh as (select c.household_id, c.p5_person_id, t.true_household_id, t.true_person_id from {{ ref('p5_household_child') }} c join child_truth t using (p5_person_id)),

pairs as (

    -- all pairs of resolved children among the contactable ones; "together" = same predicted household, "should be" = same true household
    select
        count(*) filter (where a.household_id = b.household_id)                                             as predicted_pairs,
        count(*) filter (where a.household_id = b.household_id and a.true_household_id = b.true_household_id) as true_positive_pairs,
        count(*) filter (where a.true_household_id = b.true_household_id)                                  as true_pairs
    from (select distinct p5_person_id, household_id, true_household_id from hh) a
    join (select distinct p5_person_id, household_id, true_household_id from hh) b on a.p5_person_id < b.p5_person_id

),

hh_optin as (

    select h.household_id, bool_or(p.marketing_opt_in) as any_true_opt_in
    from hh h
    join {{ source('ground_truth', 'person_registry') }} p on p.true_person_id = h.true_person_id
    group by 1

)

select
    (select predicted_pairs from pairs)                                     as household_predicted_pairs,
    (select true_positive_pairs from pairs)                                 as household_true_positive_pairs,
    round((select true_positive_pairs from pairs)::double / nullif((select predicted_pairs from pairs), 0), 4) as household_precision,
    round((select true_positive_pairs from pairs)::double / nullif((select true_pairs from pairs), 0), 4) as household_recall,
    count(*) filter (where a.eligible_for_club_activation)                  as eligible_households,
    count(*) filter (where a.eligible_for_club_activation and not coalesce(o.any_true_opt_in, false)) as falsely_eligible_households,
    count(*) filter (where a.league_comms_granted and not a.eligible_for_club_activation and not coalesce(o.any_true_opt_in, false)) as blocked_households_that_never_opted_in,
    count(*) filter (where a.league_comms_granted and not a.eligible_for_club_activation) as blocked_households
from {{ ref('p5_household_activation') }} a
left join hh_optin o using (household_id)
