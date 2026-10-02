-- Staging for Source B (Canadian club API dump). 1:1 with raw grain: one row per API record.
-- Flattens the nested JSON. Birth year only: dob stays NULL (dob_precision = YEAR).
-- A record is identified by member_uuid + season_year; pagination overlap repeats a record on two pages.
with raw as (

    select
        _page,
        _source_file,
        md5(record_json::varchar)                                          as row_hash,
        json_extract_string(record_json, '$.member_uuid')                  as member_uuid,
        json_extract_string(record_json, '$.club.club_code')               as club_code,
        json_extract_string(record_json, '$.club.club_name')               as club_name,
        json_extract_string(record_json, '$.club.province')                as province,
        json_extract_string(record_json, '$.season_year')                  as season_year_raw,
        json_extract_string(record_json, '$.program')                      as program,
        json_extract_string(record_json, '$.participant.prenom_first')     as prenom_first,
        json_extract_string(record_json, '$.participant.nom_last')         as nom_last,
        json_extract_string(record_json, '$.participant.birth_year')       as birth_year_raw,
        json_extract_string(record_json, '$.participant.sex')              as sex_raw,
        json_extract_string(record_json, '$.guardian.email')               as guardian_email,
        json_extract_string(record_json, '$.guardian.phone')               as guardian_phone,
        json_extract_string(record_json, '$.postal_code')                  as postal_raw,
        -- a missing `consents` object is different from a present object holding null values
        json_extract(record_json, '$.consents') is null                    as consents_object_missing,
        json_extract_string(record_json, '$.consents.casl_marketing')      as casl_marketing_raw,
        json_extract_string(record_json, '$.consents.photo_media')         as photo_media_raw,
        json_extract_string(record_json, '$.consents.consent_captured_at') as consent_captured_at_raw,
        json_extract_string(record_json, '$.updated_at')                   as updated_at_raw
    from {{ source('raw', 'ca_club_records') }}

),

cleaned as (

    select
        'CA_CLUB'                                                           as source_system,
        r.member_uuid || '|' || r.season_year_raw                           as source_record_id,
        row_number() over (partition by r.member_uuid, r.season_year_raw order by r._page)
                                                                            as record_occurrence,
        r._source_file                                                      as source_file,
        cast(null as integer)                                               as source_row,
        r.member_uuid                                                       as source_person_id,

        r.season_year_raw                                                   as season_label,
        cast(r.season_year_raw as integer)                                  as season_year,
        'ANNUAL'                                                            as season_term,

        r.club_code                                                         as organization_id,
        {{ blank_to_null('r.club_name') }}                                  as organization_name,
        'CA'                                                                as country_code,
        r.province                                                          as region_code,

        {{ normalize_name('r.prenom_first') }}                              as first_name,
        {{ normalize_name('r.nom_last') }}                                  as last_name,
        {{ name_key('r.prenom_first') }}                                    as first_name_key,
        {{ name_key('r.nom_last') }}                                        as last_name_key,

        cast(null as date)                                                  as dob,
        case when regexp_matches(r.birth_year_raw, '^\d{4}$') then 'YEAR_ONLY' else 'UNPARSEABLE' end
                                                                            as dob_parse_status,
        r.birth_year_raw                                                    as raw_dob,
        case when regexp_matches(r.birth_year_raw, '^\d{4}$') then cast(r.birth_year_raw as integer) end
                                                                            as birth_year,
        'YEAR'                                                              as dob_precision,

        coalesce(g.sex_code, 'U')                                           as sex,
        r.sex_raw                                                           as raw_sex,

        r.program                                                           as division_label_raw,
        d.canonical_division,

        {{ normalize_email('r.guardian_email') }}                           as contact_email,
        r.guardian_email                                                    as raw_email,
        {{ normalize_phone('r.guardian_phone', '1') }}                      as contact_phone,
        {{ normalize_ca_postal('r.postal_raw') }}                           as postal_code,
        r.postal_raw                                                        as raw_postal,

        {{ to_consent_boolean('r.photo_media_raw') }}                       as consent_photo,
        {{ to_consent_boolean('r.casl_marketing_raw') }}                    as consent_marketing,
        r.photo_media_raw                                                   as raw_consent_photo,
        r.casl_marketing_raw                                                as raw_consent_marketing,
        cast(null as boolean)                                               as waiver_signed,

        -- consent capture time is the closest thing the API has to a registration time
        try_cast(r.consent_captured_at_raw as timestamp)                    as registered_at,
        try_cast(r.updated_at_raw as timestamp)                             as record_updated_at,
        r.row_hash,
        cast(null as varchar)                                               as raw_country,
        cast(null as varchar)                                               as sheet_country_code,
        r.consents_object_missing,
        r.nom_last                                                          as raw_last_name

    from raw r
    left join {{ ref('gender_map') }} g
        on lower(trim(r.sex_raw)) = lower(g.source_value)
    left join {{ ref('division_map') }} d
        on d.source_system = 'CA_CLUB' and trim(r.program) = d.source_label

),

aged as (

    select
        *,
        {{ age_at_cutoff_from_birth_year('birth_year', 'season_year') }}   as age_at_cutoff
    from cleaned

),

flagged as (

    select
        *,
        age_at_cutoff < 18                                                  as is_minor,
        row_number() over (partition by row_hash order by source_file, source_record_id) > 1
                                                                            as is_exact_duplicate,
        false                                                               as is_near_duplicate,
        age_at_cutoff < 0 or age_at_cutoff > 80                             as is_impossible_dob,
        false                                                               as is_junk_row
    from aged

)

select
    * exclude (row_hash, consents_object_missing),
    list_filter([
        case when is_exact_duplicate then 'pagination_overlap_duplicate' end,
        case when is_impossible_dob then 'impossible_dob' end,
        case when dob_parse_status = 'UNPARSEABLE' then 'dob_unparseable' end,
        case when sex = 'U' then 'unmapped_gender' end,
        case when raw_last_name = upper(raw_last_name) and regexp_matches(raw_last_name, '[A-Za-zÀ-ÿ]{2}') then 'all_caps_names' end,
        case when raw_postal is not null and not regexp_matches(raw_postal, '^[A-Z]\d[A-Z] \d[A-Z]\d$') then 'postal_code_format' end,
        case when consents_object_missing then 'missing_consents_object' end,
        case when not consents_object_missing and raw_consent_photo is null then 'null_photo_media' end,
        case when not consents_object_missing and raw_consent_marketing is null then 'null_casl_marketing' end,
        case when canonical_division is null then 'unmapped_division' end
    ], _f -> _f is not null)                                                as dq_flags
from flagged
