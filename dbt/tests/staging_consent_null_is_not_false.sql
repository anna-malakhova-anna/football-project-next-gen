-- NULL means "not captured" and must never be coerced to TRUE or FALSE.
-- Returns staging rows where a blank / absent raw consent value became a non-NULL boolean.
select 'US_LEAGUE' as source_system, source_record_id, 'photo' as field from {{ ref('stg_us_registrations') }}
    where nullif(trim(raw_consent_photo), '') is null and consent_photo is not null
union all
select 'US_LEAGUE', source_record_id, 'marketing' from {{ ref('stg_us_registrations') }}
    where nullif(trim(raw_consent_marketing), '') is null and consent_marketing is not null
union all
select 'CA_CLUB', source_record_id, 'photo' from {{ ref('stg_ca_registrations') }}
    where raw_consent_photo is null and consent_photo is not null
union all
select 'CA_CLUB', source_record_id, 'marketing' from {{ ref('stg_ca_registrations') }}
    where raw_consent_marketing is null and consent_marketing is not null
union all
select 'INTL_FED', source_record_id, 'photo' from {{ ref('stg_intl_registrations') }}
    where nullif(trim(raw_consent_photo), '') is null and consent_photo is not null
union all
select 'INTL_FED', source_record_id, 'marketing' from {{ ref('stg_intl_registrations') }}
    where consent_marketing is not null          -- INTL never captures marketing consent
