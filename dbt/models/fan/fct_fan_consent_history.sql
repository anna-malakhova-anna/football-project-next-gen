-- Consent as a history: a Type 2 slowly changing dimension per fan account x channel. An interval says what the account's consent for the channel WAS from valid_from until valid_to
-- (open-ended = current). Built from every consent line of every account in the household (duplicates are collapsed to the canonical account), resolved BY TIMESTAMP as specified.
--   * A channel with no line has NO interval: not captured, never FALSE.
--   * Lines with the same timestamp keep one: an opt-out wins (fail closed). Consecutive lines with the same status do not open a new interval.
--   * `has_out_of_order_flag`: the interval starts at a line staging flagged as out of order (an opt-out timestamped before the opt-in it follows). Resolving by timestamp trusts
--     that timestamp; the flag keeps the doubt visible, and eval_consent_history measures what it costs.
-- No overlapping intervals per account x channel, and valid_from < valid_to or open-ended: both tested.
with ev as (

    select
        x.fan_account_id,
        c.channel,
        c.status,
        c.event_ts,
        c.capture_point,
        'consent_out_of_order' = any(c.dq_flags)                            as out_of_order
    from {{ ref('stg_fan_consent_events') }} c
    join {{ ref('int_fan_account_xref') }} x using (account_id)
    where c.record_occurrence = 1 and 'unmapped_consent_value' <> all(c.dq_flags) and 'orphan_consent_event' <> all(c.dq_flags)

),

one_per_instant as (

    select * from ev
    qualify row_number() over (partition by fan_account_id, channel, event_ts order by case status when 'opt_out' then 0 else 1 end, capture_point) = 1

),

changes as (

    select *, lag(status) over (partition by fan_account_id, channel order by event_ts) as prev_status
    from one_per_instant

),

steps as (select * from changes where prev_status is distinct from status)

select
    fan_account_id,
    channel,
    status,
    event_ts                                                                as valid_from,
    lead(event_ts) over (partition by fan_account_id, channel order by event_ts) as valid_to,
    capture_point,
    out_of_order                                                            as has_out_of_order_flag,
    lead(event_ts) over (partition by fan_account_id, channel order by event_ts) is null as is_current
from steps
