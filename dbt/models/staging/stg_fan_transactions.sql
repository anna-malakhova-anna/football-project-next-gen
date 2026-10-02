{{ config(tags=['phase4']) }}
-- Staging for Source D transactions: one row per transaction line (1:1 with raw grain). Synthetic currency. Bad rows are flagged, never dropped or repaired.
--   duplicate_txn           the same txn_id delivered again (every extra delivery; the fact never counts it)
--   refund_without_original a refund whose original_txn_id matches no non-refund transaction: excluded from revenue by the fact and counted in the DQ log
--   orphan_transaction      the account is not in the accounts snapshot
--   unmapped_txn_category / non_numeric_amount   the contract's values and types
with raw as (

    select
        _source_file,
        _line_number,
        json_extract_string(record_json, '$.txn_id')                        as txn_id,
        json_extract_string(record_json, '$.account_id')                    as account_id,
        try_cast(replace(replace(json_extract_string(record_json, '$.txn_ts'), 'T', ' '), 'Z', '') as timestamp) as txn_ts,
        json_extract_string(record_json, '$.category')                      as category,
        try_cast(json_extract_string(record_json, '$.amount') as double)    as amount,
        json_extract_string(record_json, '$.amount')                        as amount_raw,
        coalesce(try_cast(json_extract_string(record_json, '$.is_refund') as boolean), false) as is_refund,
        nullif(trim(json_extract_string(record_json, '$.original_txn_id')), '') as original_txn_id
    from {{ source('raw', 'fan_transactions') }}

),

numbered as (

    select *, row_number() over (partition by txn_id order by _source_file, _line_number) as record_occurrence from raw

),

originals as (select distinct txn_id from numbered where not is_refund)

select
    'FAN_ENGAGEMENT'                                                        as source_system,
    n.txn_id                                                                as source_record_id,
    n.record_occurrence,
    n._source_file                                                          as source_file,
    n._line_number                                                          as source_row,
    n.txn_id,
    n.account_id,
    n.txn_ts,
    date_trunc('month', n.txn_ts)::date                                     as txn_month,
    n.category,
    n.amount,
    n.is_refund,
    n.original_txn_id,
    n.record_occurrence > 1                                                 as is_duplicate,
    n.is_refund and (n.original_txn_id is null or n.original_txn_id not in (select txn_id from originals)) as is_orphan_refund,
    list_filter([
        case when n.record_occurrence > 1                                   then 'duplicate_txn' end,
        case when n.is_refund and (n.original_txn_id is null or n.original_txn_id not in (select txn_id from originals)) then 'refund_without_original' end,
        case when n.account_id not in (select account_id from {{ ref('stg_fan_accounts') }}) then 'orphan_transaction' end,
        case when n.category not in ('ticket', 'merch', 'subscription', 'other') or n.category is null then 'unmapped_txn_category' end,
        case when n.amount is null                                          then 'non_numeric_amount' end
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
from numbered n
