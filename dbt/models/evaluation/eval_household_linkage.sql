{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). Precision and recall of the household -> fan account links against the true households.
--   precision        correct links / links made (a link is correct when the account belongs to the household's true household)
--   recall           correctly linked participant households / participant households that have a fan account at all
--   recall_linkable  the same, among accounts whose email DOES match the registration email: what the email rule could ever reach
--   by_method        precision split by EMAIL and PHONE (phone is the weaker key: a number can be shared with another household)
--   false_links_*    false links, and how many of them are accounts that reuse a participant household's phone number
with truth_hh as (

    select b.participant_id, coalesce(max(pr.household_id), min(t.true_person_id)) as true_household
    from {{ ref('bridge_registration_participant') }} b
    join {{ ref('eval_record_truth') }} t on t.match_record_id = b.registration_key
    join {{ source('ground_truth', 'person_registry') }} pr on pr.true_person_id = t.true_person_id
    group by 1

),

obs_hh as (

    select h.household_id, mode(t.true_household) as true_household
    from {{ ref('int_household') }} h join truth_hh t using (participant_id) group by 1

),

links as (

    select l.household_id, l.account_id, l.link_method, o.true_household as hh_true, a.household_key as account_true, a.phone_shared,
           o.true_household = a.household_key as is_correct
    from {{ ref('link_household_fan_account') }} l
    join obs_hh o using (household_id)
    join {{ source('ground_truth', 'fan_account_truth') }} a on a.account_id = l.account_id
    where l.link_status = 'LINKED'

),

targets as (

    select a.account_id, a.household_key, a.email_differs
    from {{ source('ground_truth', 'fan_account_truth') }} a where a.is_participant_household and not a.is_duplicate_account

),

hit as (select distinct account_id from links where is_correct)

select 'links_made' as measure, count(*) as n, cast(null as double) as value from links
union all select 'links_correct', count(*) filter (where is_correct), null from links
union all select 'precision', count(*), count(*) filter (where is_correct) * 1.0 / count(*) from links
union all select 'precision_' || link_method, count(*), count(*) filter (where is_correct) * 1.0 / count(*) from links group by link_method
union all select 'false_links', count(*) filter (where not is_correct), null from links
union all select 'false_links_phone_shared_with_participant_household', count(*) filter (where not is_correct and phone_shared), null from links
union all select 'participant_households_with_an_account', count(*), null from targets
union all select 'recall', (select count(*) from targets t join hit using (account_id)), (select count(*) from targets t join hit using (account_id)) * 1.0 / count(*) from targets
union all select 'participant_accounts_with_matching_email', count(*) filter (where not email_differs), null from targets
union all select 'recall_linkable', (select count(*) from targets t join hit using (account_id) where not t.email_differs),
       (select count(*) from targets t join hit using (account_id) where not t.email_differs) * 1.0 / count(*) filter (where not email_differs) from targets
union all select 'link_rate_of_all_participant_households', (select count(*) from links where is_correct), (select count(*) from links where is_correct) * 1.0 / (select count(*) from obs_hh)
