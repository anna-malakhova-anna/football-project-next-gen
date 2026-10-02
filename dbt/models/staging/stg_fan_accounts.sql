{{ config(tags=['phase4']) }}
-- Staging for Source D accounts (fan app / ticketing snapshot). 1:1 with raw grain: one row per account. Adults only.
-- Email and phone are normalized with the same macros the registrations use, so the household linkage compares like with like.
-- Consent no longer arrives on the account: it is a stream of events (fan_consent_events), so there is no consent column here.
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
        nullif(trim(acquisition_source), '')                                as acquisition_source,
        try_cast(birth_year as integer)                                     as holder_birth_year
    from raw

),

mapped as (

    select t.*, c.country_code, coalesce(g.market_id, cm.market_id) as market_id
    from typed t
    left join {{ ref('country_map') }} c on lower(t.country_raw) = lower(c.source_value)
    left join {{ ref('market_geo_map') }} g on g.prefix = upper(t.postal_prefix)
    left join (select country_code, any_value(market_id) as market_id from {{ ref('market_map') }} where region_code = '' group by 1) cm
        on cm.country_code = c.country_code and t.postal_prefix is null

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
    market_id,
    created_at,
    acquisition_source,
    holder_birth_year,
    list_filter([
        case when raw_email <> lower(trim(raw_email))               then 'email_case_whitespace' end,
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
