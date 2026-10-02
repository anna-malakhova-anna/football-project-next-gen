{{ config(tags=['phase4']) }}
-- Staging for Source E (school and recreation program aggregate headcounts). 1:1 with raw grain: one row per CSV row.
-- AGGREGATE-ONLY: there is no person here. Bad rows are flagged, never dropped; the choices made at Profiling (onboarding log) are applied here:
--   * a program-year reported twice keeps the latest report (`is_superseded` marks the others, which never feed the facts);
--   * the headcount used is girls + boys when total_count disagrees with it, otherwise total_count;
--   * round totals are kept and flagged as probable estimates;
--   * a blank grade band becomes UNKNOWN.
with raw as (

    select
        _source_file,
        _row_number,
        trim(district)                                                      as district,
        trim(school_or_program)                                             as school_or_program,
        trim(country)                                                       as country_raw,
        nullif(trim(region), '')                                            as region,
        trim(program_type)                                                  as program_type_raw,
        nullif(trim(grade_band), '')                                        as grade_band_raw,
        try_cast(girls_count as integer)                                    as girls_count,
        try_cast(boys_count as integer)                                     as boys_count,
        try_cast(total_count as integer)                                    as total_count,
        trim(reported_by)                                                   as reported_by,
        try_cast(report_date as date)                                       as report_date,
        cast(regexp_extract(_source_file, '(\d{4})\.csv$', 1) as integer)   as season_year
    from {{ source('raw', 'school_headcounts') }}

),

typed as (

    select
        r.*,
        c.country_code,
        case when program_type_raw in ('PE_UNIT', 'INTRAMURAL', 'AFTER_SCHOOL') then program_type_raw end as program_type,
        coalesce(grade_band_raw, 'UNKNOWN')                                 as grade_band,
        -- the same program-year, whoever reported it: district + school/program + type + year
        row_number() over (
            partition by district, school_or_program, program_type_raw, season_year
            order by report_date desc, _row_number desc
        )                                                                   as report_rank
    from raw r
    left join {{ ref('country_map') }} c on lower(r.country_raw) = lower(c.source_value)

),

flagged as (

    select
        *,
        girls_count + boys_count                                            as girls_plus_boys,
        list_filter([
            case when girls_count + boys_count <> total_count            then 'total_mismatch' end,
            case when grade_band_raw is null                             then 'missing_grade_band' end,
            case when report_rank > 1                                    then 'duplicate_report' end,
            case when total_count in (100, 150, 200, 250, 300)           then 'round_number' end,
            case when program_type is null                               then 'unmapped_program_type' end,
            case when country_code is null                               then 'unmapped_country' end
        ], _f -> _f is not null)                                            as dq_flags
    from typed

)

select
    'SCHOOL_AGGREGATES'                                                     as source_system,
    season_year || '|' || district || '|' || school_or_program || '|' || program_type_raw || '|' || reported_by
                                                                            as source_record_id,
    row_number() over (partition by season_year, district, school_or_program, program_type_raw, reported_by order by _row_number)
                                                                            as record_occurrence,
    _source_file                                                            as source_file,
    _row_number                                                             as source_row,
    season_year,
    district,
    school_or_program,
    country_code,
    region,
    program_type,
    grade_band,
    girls_count,
    boys_count,
    total_count,
    -- the headcount to use: the arithmetic wins when the stated total disagrees with it
    coalesce(girls_plus_boys, total_count)                                  as headcount,
    list_contains(dq_flags, 'total_mismatch')                               as total_was_corrected,
    list_contains(dq_flags, 'round_number')                                 as is_probable_estimate,
    report_rank > 1                                                         as is_superseded,
    reported_by,
    report_date,
    dq_flags,
    country_raw                                                             as raw_country,
    cast(null as varchar)                                                   as raw_dob,
    cast(null as varchar)                                                   as raw_last_name,
    cast(null as varchar)                                                   as raw_sex,
    cast(null as varchar)                                                   as raw_email,
    cast(null as varchar)                                                   as raw_postal,
    cast(null as varchar)                                                   as raw_consent_photo,
    cast(null as varchar)                                                   as raw_consent_marketing,
    cast(null as varchar)                                                   as division_label_raw
from flagged
