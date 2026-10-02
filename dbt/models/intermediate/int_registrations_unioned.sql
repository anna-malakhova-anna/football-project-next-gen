-- Common schema across all three sources: one row per registration record (duplicates flagged, not removed).
-- Phase 1 stops here: no identity resolution (Phase 2) and no participant counting (Phase 3).
with unioned as (

    select * from {{ ref('stg_us_registrations') }}
    union all by name
    select * from {{ ref('stg_ca_registrations') }}
    union all by name
    select * from {{ ref('stg_intl_registrations') }}

)

select
    -- exact double-submits repeat their source_record_id, so the occurrence number is part of the key
    md5(source_system || '|' || source_record_id || '|' || record_occurrence)   as registration_key,
    source_system,
    source_record_id,
    source_person_id,

    season_label,
    cast(season_year as integer)                                                as season_year,
    season_term,

    organization_id,
    organization_name,
    cast(country_code as varchar(2))                                            as country_code,
    region_code,

    first_name,
    last_name,
    first_name_key,
    last_name_key,

    dob,
    cast(birth_year as integer)                                                 as birth_year,
    dob_precision,
    cast(sex as varchar(1))                                                     as sex,
    cast(age_at_cutoff as integer)                                              as age_at_cutoff,
    canonical_division,
    is_minor,

    contact_email,
    contact_phone,
    postal_code,

    consent_photo,
    consent_marketing,

    registered_at,
    dq_flags,

    -- lineage and DQ helpers (not part of the business schema)
    cast(record_occurrence as integer)                                          as record_occurrence,
    source_file,
    cast(source_row as integer)                                                 as source_row,
    is_exact_duplicate,
    is_near_duplicate,
    is_impossible_dob
from unioned
