{{ config(tags=['phase4'], materialized='table') }}
-- Staging for Source D events: one row per DELIVERED line (1:1 with raw grain). Bad rows are flagged, never dropped.
--   duplicate_event      the same event_id delivered again (record_occurrence > 1): `is_duplicate` marks every extra delivery, which the fact never counts
--   late_arriving_event  delivered in a later month's file than the month of event_ts: the event belongs to the month of event_ts, not the file
--   orphan_event         account_id is not in the accounts snapshot
--   unmapped_event_type  event_type is not one of the six known engagement event types (purchases are transactions now, not events)
-- event_month comes from event_ts (UTC), never from the file. Clock skew cannot be seen from the data and is not flagged.
with raw as (

    select
        _source_file,
        _line_number,
        json_extract_string(record_json, '$.event_id')                       as event_id,
        json_extract_string(record_json, '$.account_id')                     as account_id,
        json_extract_string(record_json, '$.event_type')                     as event_type,
        try_cast(replace(replace(json_extract_string(record_json, '$.event_ts'), 'T', ' '), 'Z', '') as timestamp) as event_ts,
        try_cast(json_extract_string(record_json, '$.value') as double)      as value,
        make_date(cast(regexp_extract(_source_file, 'events_(\d{4})_(\d{2})\.jsonl$', 1) as integer),
                  cast(regexp_extract(_source_file, 'events_(\d{4})_(\d{2})\.jsonl$', 2) as integer), 1) as delivered_month
    from {{ source('raw', 'fan_events') }}

),

numbered as (

    select
        *,
        row_number() over (partition by event_id order by _source_file, _line_number)   as record_occurrence,
        date_trunc('month', event_ts)::date                                              as event_month
    from raw

)

select
    'FAN_ENGAGEMENT'                                                        as source_system,
    event_id                                                                as source_record_id,
    record_occurrence,
    _source_file                                                            as source_file,
    _line_number                                                            as source_row,
    event_id,
    account_id,
    event_type,
    event_ts,
    event_month,
    delivered_month,
    value,
    record_occurrence > 1                                                   as is_duplicate,
    delivered_month > event_month                                           as is_late,
    list_filter([
        case when record_occurrence > 1                                     then 'duplicate_event' end,
        case when record_occurrence = 1 and delivered_month > event_month   then 'late_arriving_event' end,
        case when account_id not in (select account_id from {{ ref('stg_fan_accounts') }}) then 'orphan_event' end,
        case when event_type not in ('app_open', 'content_view', 'game_stream', 'newsletter_click', 'fantasy_activity', 'flag_content_view')
                  or event_type is null                                     then 'unmapped_event_type' end
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
