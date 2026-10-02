-- Staging for Source C (international federation XLSX returns). 1:1 with raw grain for real player rows.
-- Drops ONLY true junk (title, blank, header and summary rows); dq_defect_log logs every dropped row.
-- Raw is positional: c1 Player ID, c2 Full Name, c3 Date of Birth, c4 Gender, c5 Category, c6 Club,
-- c7 Country, c8 Email, c9 Media Consent.
{% set family_first = var('intl_family_name_first_countries') %}

with players as (

    select
        *,
        cast(regexp_extract(_source_file, '(\d{4})\.xlsx$', 1) as integer)  as season_year,
        md5(concat_ws('|', c1, c2, c3, c4, c5, c6, c7, c8, c9))             as row_hash
    from {{ intl_classified_rows() }}
    where junk_reason is null

),

sheet as (

    select
        p.*,
        s.country_code                                                      as sheet_country_code,
        {{ _clean_ws('p.c2') }}                                             as full_name_clean
    from players p
    left join {{ ref('country_map') }} s on lower(trim(p._sheet_name)) = lower(s.source_value)

),

-- "Full Name" is one field. Split at the first space when the sheet gives the family name first
-- (Japan), otherwise at the last space. Particles and multi-word surnames therefore split imperfectly;
-- that limit is deliberate and documented (see data dictionary).
split as (

    select
        *,
        case
            when sheet_country_code in ({{ family_first | map('tojson') | join(', ') | replace('"', "'") }})
                then regexp_extract(full_name_clean, '^(\S+)', 1)
            else regexp_extract(full_name_clean, '(\S+)$', 1)
        end                                                                 as family_raw,
        case
            when full_name_clean not like '% %' then null
            when sheet_country_code in ({{ family_first | map('tojson') | join(', ') | replace('"', "'") }})
                then regexp_replace(full_name_clean, '^\S+\s+', '')
            else regexp_replace(full_name_clean, '\s+\S+$', '')
        end                                                                 as given_raw
    from sheet

),

country_counts as (

    select _source_file, _sheet_name, c7, count(*) as n
    from players
    group by 1, 2, 3

),

country_mode as (

    -- the dominant Country spelling on each sheet; rows that differ are flagged as inconsistent
    select _source_file, _sheet_name, c7 as mode_country
    from country_counts
    qualify row_number() over (partition by _source_file, _sheet_name order by n desc, c7) = 1

),

cleaned as (

    select
        'INTL_FED'                                                          as source_system,
        trim(s.c1) || '|' || s.season_year                                  as source_record_id,
        1                                                                   as record_occurrence,
        s._source_file                                                      as source_file,
        s._excel_row                                                        as source_row,
        trim(s.c1)                                                          as source_person_id,

        cast(s.season_year as varchar)                                      as season_label,
        s.season_year,
        'ANNUAL'                                                            as season_term,

        c.country_code || '|' || trim(s.c6)                                 as organization_id,
        {{ blank_to_null('s.c6') }}                                         as organization_name,
        c.country_code                                                      as country_code,
        cast(null as varchar)                                               as region_code,

        {{ normalize_name('s.given_raw') }}                                 as first_name,
        {{ normalize_name('s.family_raw') }}                                as last_name,
        {{ name_key('s.given_raw') }}                                       as first_name_key,
        {{ name_key('s.family_raw') }}                                      as last_name_key,

        {{ parse_flexible_date('s.c3', 'DMY') }}                            as dob,
        {{ parse_flexible_date_status('s.c3', 'DMY') }}                     as dob_parse_status,
        s.family_raw                                                        as raw_last_name,
        s.c3                                                                as raw_dob,
        'DAY'                                                               as dob_precision,

        coalesce(g.sex_code, 'U')                                           as sex,
        s.c4                                                                as raw_sex,

        s.c5                                                                as division_label_raw,
        d.canonical_division,

        {{ normalize_email('s.c8') }}                                       as contact_email,
        s.c8                                                                as raw_email,
        cast(null as varchar)                                               as contact_phone,
        cast(null as varchar)                                               as postal_code,
        cast(null as varchar)                                               as raw_postal,

        {{ to_consent_boolean('s.c9') }}                                    as consent_photo,
        cast(null as boolean)                                               as consent_marketing,   -- not captured by this source
        s.c9                                                                as raw_consent_photo,
        cast(null as varchar)                                               as raw_consent_marketing,
        cast(null as boolean)                                               as waiver_signed,

        cast(null as timestamp)                                             as registered_at,
        cast(null as timestamp)                                             as record_updated_at,
        s.c7                                                                as raw_country,
        s.sheet_country_code,
        s.row_hash,
        m.mode_country,
        c.country_code is null and {{ blank_to_null('s.c7') }} is not null  as country_unmapped

    from split s
    left join {{ ref('country_map') }} c on lower(trim(s.c7)) = lower(c.source_value)
    left join {{ ref('gender_map') }} g on lower(trim(s.c4)) = lower(g.source_value)
    left join {{ ref('division_map') }} d on d.source_system = 'INTL_FED' and trim(s.c5) = d.source_label
    left join country_mode m on m._source_file = s._source_file and m._sheet_name = s._sheet_name

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
        row_number() over (partition by source_file, row_hash order by source_row) > 1
                                                                            as is_exact_duplicate,
        false                                                               as is_near_duplicate,
        age_at_cutoff < 0 or age_at_cutoff > 80                             as is_impossible_dob,
        false                                                               as is_junk_row
    from aged

)

select
    * exclude (row_hash, mode_country, country_unmapped),
    list_filter([
        case when is_exact_duplicate then 'exact_duplicate' end,
        case when is_impossible_dob then 'impossible_dob' end,
        case when dob_parse_status = 'EXCEL_SERIAL' then 'uk_dob_excel_serial' end,
        case when dob_parse_status in ('AMBIGUOUS', 'UNPARSEABLE', 'BLANK') then 'dob_unparseable' end,
        case when country_unmapped then 'unmapped_country' end,
        case when raw_country is distinct from mode_country then 'country_value_inconsistency' end,
        case when sex = 'U' then 'unmapped_gender' end,
        case when {{ blank_to_null('raw_consent_photo') }} is null then 'missing_media_consent' end,
        case when canonical_division is null then 'unmapped_division' end
    ], _f -> _f is not null)                                                as dq_flags
from flagged
