{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). The resolved consent history (fct_fan_consent_history, resolved by timestamp) against each account's intended final consent per channel (fan_consent_truth).
-- Compared on households with ONE account (a merged household has two accounts' consent that the truth keeps apart). A mismatch is where the current open interval differs from the intended final status
-- ('none' = no line at all). The unsafe direction is the history saying opt_in where the account opted out: those come from consent lines timestamped out of order, and every one should carry the
-- out-of-order flag so a contact use can fail closed on them.
with cur as (

    select fan_account_id, channel, status, has_out_of_order_flag
    from {{ ref('fct_fan_consent_history') }} where valid_to is null

),

flagged as (

    -- an account-channel is DOUBTFUL when any interval in its history starts at an out-of-order line
    select fan_account_id, channel, bool_or(has_out_of_order_flag) as doubtful from {{ ref('fct_fan_consent_history') }} group by 1, 2

),

single as (select fan_account_id from {{ ref('int_fan_account_xref') }} group by 1 having count(*) = 1),

t as (

    select a.account_id as fan_account_id, a.channel, a.final_status,
           coalesce(c.status, 'none') as resolved_status, coalesce(f.doubtful, false) as doubtful
    from {{ source('ground_truth', 'fan_consent_truth') }} a
    join single s on s.fan_account_id = a.account_id
    left join cur c on c.fan_account_id = a.account_id and c.channel = a.channel
    left join flagged f on f.fan_account_id = a.account_id and f.channel = a.channel

)

select
    count(*)                                                                as account_channels_compared,
    count(*) filter (where resolved_status <> final_status)                 as mismatches,
    count(*) filter (where resolved_status = 'opt_in' and final_status = 'opt_out')   as unsafe_mismatches,
    count(*) filter (where resolved_status <> final_status and doubtful)    as mismatches_flagged_as_doubtful,
    count(*) filter (where resolved_status = 'opt_in' and final_status = 'opt_out' and doubtful)  as unsafe_mismatches_flagged_as_doubtful,
    round(count(*) filter (where resolved_status <> final_status) * 1.0 / count(*), 5)   as mismatch_rate,
    count(*) filter (where doubtful)                                        as doubtful_account_channels
from t
