-- Staging for Source A (US league CSVs). 1:1 with raw grain: one row per CSV data row.
-- Types, trims and standardizes; flags bad records but never drops them.
with raw as (

    select
        *,
        md5(concat_ws('|', registration_id, league_id, league_name, season, division, player_first_name,
            player_last_name, player_dob, player_gender, guardian_name, guardian_email, guardian_phone,
            zip, team_name, registered_at, waiver_signed, photo_consent, marketing_opt_in)) as row_hash
    from {{ source('raw', 'us_league_registrations') }}

),

cleaned as (

    select
        'US_LEAGUE'                                                         as source_system,
        r.registration_id                                                   as source_record_id,
        row_number() over (partition by r._source_file, r.registration_id order by r._row_number)
                                                                            as record_occurrence,
        r._source_file                                                      as source_file,
        r._row_number                                                       as source_row,
        cast(null as varchar)                                               as source_person_id,

        r.season                                                            as season_label,
        cast(regexp_extract(r.season, '(\d{4})', 1) as integer)             as season_year,
        upper(regexp_extract(r.season, '^(\w+)', 1))                        as season_term,

        r.league_id                                                         as organization_id,
        {{ blank_to_null('r.league_name') }}                                as organization_name,
        'US'                                                                as country_code,
        split_part(r.league_id, '-', 2)                                     as region_code,

        {{ normalize_name('r.player_first_name') }}                         as first_name,
        {{ normalize_name('r.player_last_name') }}                          as last_name,
        {{ name_key('r.player_first_name') }}                               as first_name_key,
        {{ name_key('r.player_last_name') }}                                as last_name_key,

        {{ parse_flexible_date('r.player_dob', 'MDY') }}                    as dob,
        {{ parse_flexible_date_status('r.player_dob', 'MDY') }}             as dob_parse_status,
        r.player_last_name                                                  as raw_last_name,
        r.player_dob                                                        as raw_dob,
        'DAY'                                                               as dob_precision,

        coalesce(g.sex_code, 'U')                                           as sex,
        r.player_gender                                                     as raw_sex,

        r.division                                                          as division_label_raw,
        d.canonical_division,

        {{ normalize_email('r.guardian_email') }}                           as contact_email,
        r.guardian_email                                                    as raw_email,
        {{ normalize_phone('r.guardian_phone', '1') }}                      as contact_phone,
        {{ normalize_us_zip('r.zip') }}                                     as postal_code,
        r.zip                                                               as raw_postal,

        {{ to_consent_boolean('r.photo_consent') }}                         as consent_photo,
        {{ to_consent_boolean('r.marketing_opt_in') }}                      as consent_marketing,
        r.photo_consent                                                     as raw_consent_photo,
        r.marketing_opt_in                                                  as raw_consent_marketing,
        {{ to_consent_boolean('r.waiver_signed') }}                         as waiver_signed,

        try_cast(r.registered_at as timestamp)                              as registered_at,
        r.row_hash,
        cast(null as varchar)                                               as raw_country,
        cast(null as varchar)                                               as sheet_country_code,
        cast(null as timestamp)                                             as record_updated_at

    from raw r
    left join {{ ref('gender_map') }} g
        on lower(trim(r.player_gender)) = lower(g.source_value)
    left join {{ ref('division_map') }} d
        on d.source_system = 'US_LEAGUE' and trim(r.division) = d.source_label

),

aged as (

    select
        *,
        extract(year from dob)::integer                                     as birth_year,
        {{ age_at_cutoff('dob', 'season_year') }}                           as age_at_cutoff
    from cleaned

),

flagged as (

    select
        *,
        age_at_cutoff < 18                                                  as is_minor,
        row_number() over (partition by row_hash order by source_file, source_row) > 1
                                                                            as is_exact_duplicate,
        age_at_cutoff < 0 or age_at_cutoff > 80                             as is_impossible_dob,
        false                                                               as is_junk_row
    from aged

),

near as (

    -- same person (name keys), league and season registered twice under different ids;
    -- exact duplicates are excluded so the two defects are not double counted
    select
        *,
        (not is_exact_duplicate)
            and row_number() over (
                partition by organization_id, season_label, first_name_key, last_name_key, is_exact_duplicate
                order by registered_at, source_record_id
            ) > 1                                                           as is_near_duplicate
    from flagged

)

select
    * exclude (row_hash),
    list_filter([
        case when is_exact_duplicate then 'exact_duplicate' end,
        case when is_near_duplicate then 'near_duplicate' end,
        case when is_impossible_dob then 'impossible_dob' end,
        case when dob_parse_status in ('AMBIGUOUS', 'UNPARSEABLE', 'BLANK') then 'dob_unparseable' end,
        case when {{ blank_to_null('raw_sex') }} is null then 'missing_gender'
             when sex = 'U' then 'unmapped_gender' end,
        case when {{ blank_to_null('raw_consent_photo') }} is null then 'missing_photo_consent' end,
        case when {{ blank_to_null('raw_consent_marketing') }} is null then 'missing_marketing_opt_in' end,
        case when raw_email <> lower(trim(raw_email)) then 'guardian_email_case_whitespace' end,
        case when regexp_matches(trim(raw_postal), '^\d{4}$') then 'zip_leading_zero_dropped' end,
        case when canonical_division is null then 'unmapped_division' end
    ], _f -> _f is not null)                                                as dq_flags
from near
