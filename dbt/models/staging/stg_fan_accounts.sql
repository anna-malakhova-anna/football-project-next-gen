{{ config(tags=['phase4']) }}
-- Staging for Source D accounts (fan app / ticketing snapshot). 1:1 with raw grain: one row per account. Adults only.
-- Email and phone are normalized with the same macros the registrations use, so the household linkage compares like with like.
-- marketing_opt_in blank is NULL (not captured), never FALSE.
with raw as (select * from {{ source('raw', 'fan_accounts') }}),

typed as (

    select
        _source_file,
        _row_number,
        trim(account_id)                                                    as account_id,
        email                                                               as raw_email,
        {{ normalize_email('email') }}                                      as contact_email,
        {{ normalize_phone('phone', '1') }}                                 as contact_phone,
        nullif(trim(phone), '')                                             as raw_phone,
        nullif(trim(postal_prefix), '')                                     as postal_prefix,
        upper(trim(country))                                                as country_raw,
        try_cast(created_at as timestamp)                                   as created_at,
        {{ to_consent_boolean('marketing_opt_in') }}                        as marketing_opt_in
    from raw

),

mapped as (

    select t.*, c.country_code
    from typed t left join {{ ref('country_map') }} c on lower(t.country_raw) = lower(c.source_value)

)

select
    'FAN_ENGAGEMENT'                                                        as source_system,
    account_id                                                              as source_record_id,
    1                                                                       as record_occurrence,
    _source_file                                                            as source_file,
    _row_number                                                             as source_row,
    account_id,
    contact_email,
    contact_phone,
    postal_prefix,
    country_code,
    created_at,
    marketing_opt_in,
    list_filter([
        case when raw_email <> lower(trim(raw_email))               then 'email_case_whitespace' end,
        case when marketing_opt_in is null                          then 'marketing_opt_in_blank' end,
        case when country_code is null                              then 'unmapped_country' end
    ], _f -> _f is not null)                                                as dq_flags,
    raw_email,
    raw_phone,
    country_raw                                                             as raw_country,
    cast(null as varchar)                                                   as raw_dob,
    cast(null as varchar)                                                   as raw_last_name,
    cast(null as varchar)                                                   as raw_sex,
    cast(null as varchar)                                                   as raw_postal,
    cast(null as varchar)                                                   as raw_consent_photo,
    cast(null as varchar)                                                   as raw_consent_marketing,
    cast(null as varchar)                                                   as division_label_raw
from mapped
