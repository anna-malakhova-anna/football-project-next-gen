{{ config(tags=['phase4']) }}
-- Staging for Source D consent events: one row per consent line (1:1 with raw grain). Bad rows are flagged, never dropped.
--   NO EVENT means "not captured": there is no row for a channel the account never answered. Absence is never turned into FALSE.
--   consent_out_of_order  an opt-out through the preference centre that is NOT preceded (by timestamp) by an opt-in on that account and channel. A preference-centre opt-out can only
--                         follow an opt-in, so its timestamp is wrong. The consent history resolves by timestamp, as specified, and keeps the flag.
--   orphan_consent_event  the account is not in the accounts snapshot
--   unmapped_consent_value  status, channel or capture point is not one of the contract's values
with raw as (

    select
        _source_file,
        _line_number,
        json_extract_string(record_json, '$.account_id')                    as account_id,
        json_extract_string(record_json, '$.channel')                       as channel,
        json_extract_string(record_json, '$.status')                        as status,
        try_cast(replace(replace(json_extract_string(record_json, '$.event_ts'), 'T', ' '), 'Z', '') as timestamp) as event_ts,
        json_extract_string(record_json, '$.capture_point')                 as capture_point
    from {{ source('raw', 'fan_consent_events') }}

),

numbered as (

    select
        *,
        row_number() over (partition by account_id, channel, event_ts order by _source_file, _line_number)      as record_occurrence,
        count(*) filter (where status = 'opt_in') over (
            partition by account_id, channel order by event_ts, status rows between unbounded preceding and 1 preceding) as earlier_opt_ins
    from raw

)

select
    'FAN_ENGAGEMENT'                                                        as source_system,
    account_id || '|' || channel || '|' || strftime(event_ts, '%Y-%m-%dT%H:%M:%SZ') as source_record_id,
    record_occurrence,
    _source_file                                                            as source_file,
    _line_number                                                            as source_row,
    account_id,
    channel,
    status,
    event_ts,
    capture_point,
    list_filter([
        case when status = 'opt_out' and capture_point = 'preference_center' and coalesce(earlier_opt_ins, 0) = 0 then 'consent_out_of_order' end,
        case when account_id not in (select account_id from {{ ref('stg_fan_accounts') }}) then 'orphan_consent_event' end,
        case when status not in ('opt_in', 'opt_out') or channel not in ('email', 'sms', 'push')
                  or capture_point not in ('signup', 'checkout', 'preference_center', 'flag_registration') or status is null or channel is null or capture_point is null
             then 'unmapped_consent_value' end
    ], _f -> _f is not null)                                                as dq_flags,
    cast(null as varchar)                                                   as raw_email,
    cast(null as varchar)                                                   as raw_country,
    cast(null as varchar)                                                   as raw_dob,
    cast(null as varchar)                                                   as raw_last_name,
    cast(null as varchar)                                                   as raw_sex,
    cast(null as varchar)                                                   as raw_postal,
    cast(null as varchar)                                                   as raw_consent_photo,
    cast(null as varchar)                                                   as raw_consent_marketing,
    cast(null as varchar)                                                   as division_label_raw
from numbered
