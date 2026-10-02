-- One row per flagged record per flag, for every source, plus every junk row dropped in staging.
-- raw_value is the original (pre-cleaning) value the rule fired on.
with staged as (

    select source_system, source_record_id, record_occurrence, source_file, source_row, dq_flags,
           raw_dob, raw_last_name, raw_sex, raw_email, raw_postal, raw_consent_photo, raw_consent_marketing,
           raw_country, division_label_raw
    from {{ ref('stg_us_registrations') }}
    union all by name
    select source_system, source_record_id, record_occurrence, source_file, source_row, dq_flags,
           raw_dob, raw_last_name, raw_sex, raw_email, raw_postal, raw_consent_photo, raw_consent_marketing,
           raw_country, division_label_raw
    from {{ ref('stg_ca_registrations') }}
    union all by name
    select source_system, source_record_id, record_occurrence, source_file, source_row, dq_flags,
           raw_dob, raw_last_name, raw_sex, raw_email, raw_postal, raw_consent_photo, raw_consent_marketing,
           raw_country, division_label_raw
    from {{ ref('stg_intl_registrations') }}
    union all by name
    -- Source E: aggregate rows, no person fields (those columns are NULL in staging)
    select source_system, source_record_id, record_occurrence, source_file, source_row, dq_flags,
           raw_dob, raw_last_name, raw_sex, raw_email, raw_postal, raw_consent_photo, raw_consent_marketing,
           raw_country, division_label_raw
    from {{ ref('stg_school_headcounts') }}
    union all by name
    -- Source D: accounts and events, no registration person fields (NULL in staging)
    select source_system, source_record_id, record_occurrence, source_file, source_row, dq_flags,
           raw_dob, raw_last_name, raw_sex, raw_email, raw_postal, raw_consent_photo, raw_consent_marketing,
           raw_country, division_label_raw
    from {{ ref('stg_fan_accounts') }}
    union all by name
    select source_system, source_record_id, record_occurrence, source_file, source_row, dq_flags,
           raw_dob, raw_last_name, raw_sex, raw_email, raw_postal, raw_consent_photo, raw_consent_marketing,
           raw_country, division_label_raw
    from {{ ref('stg_fan_events') }}

),

flagged as (

    select
        source_system,
        source_record_id,
        record_occurrence,
        source_file,
        source_row,
        unnest(dq_flags)                                                    as flag,
        raw_dob, raw_last_name, raw_sex, raw_email, raw_postal, raw_consent_photo, raw_consent_marketing,
        raw_country, division_label_raw
    from staged

),

record_flags as (

    select
        source_system,
        source_record_id,
        record_occurrence,
        source_file,
        source_row,
        flag,
        case flag
            when 'exact_duplicate'                          then source_record_id
            when 'pagination_overlap_duplicate'             then source_record_id
            when 'near_duplicate'                           then source_record_id
            when 'impossible_dob'                           then raw_dob
            when 'dob_unparseable'                          then raw_dob
            when 'uk_dob_excel_serial'                      then raw_dob
            when 'missing_gender'                           then coalesce(raw_sex, '')
            when 'unmapped_gender'                          then raw_sex
            when 'missing_photo_consent'                    then coalesce(raw_consent_photo, '')
            when 'null_photo_media'                         then '<null>'
            when 'missing_media_consent'                    then coalesce(raw_consent_photo, '')
            when 'missing_marketing_opt_in'                 then coalesce(raw_consent_marketing, '')
            when 'null_casl_marketing'                      then '<null>'
            when 'missing_consents_object'                  then '<consents object absent>'
            when 'guardian_email_case_whitespace'           then '[' || raw_email || ']'
            when 'zip_leading_zero_dropped'                 then raw_postal
            when 'postal_code_format'                       then raw_postal
            when 'all_caps_names'                           then raw_last_name
            when 'unmapped_division'                        then division_label_raw
            when 'country_value_inconsistency'              then raw_country
            when 'unmapped_country'                         then raw_country
            when 'total_mismatch'                           then source_record_id
            when 'missing_grade_band'                       then '<blank>'
            when 'duplicate_report'                         then source_record_id
            when 'round_number'                             then source_record_id
            when 'unmapped_program_type'                    then source_record_id
            when 'duplicate_event'                          then source_record_id
            when 'late_arriving_event'                      then source_record_id
            when 'orphan_event'                             then source_record_id
            when 'unmapped_event_type'                      then source_record_id
            when 'email_case_whitespace'                    then '[' || raw_email || ']'
        end                                                                 as raw_value
    from flagged

),

junk as (

    -- rows staging dropped; logged here so nothing disappears silently
    select
        'INTL_FED'                                                          as source_system,
        _sheet_name || '|row' || _excel_row                                 as source_record_id,
        1                                                                   as record_occurrence,
        _source_file                                                        as source_file,
        _excel_row                                                          as source_row,
        'junk_' || lower(junk_reason)                                       as flag,
        concat_ws(' | ', c1, c2, c3, c4, c5, c6, c7, c8, c9)                as raw_value
    from {{ intl_classified_rows() }}
    where junk_reason is not null

),

combined as (

    select * from record_flags
    union all by name
    select * from junk

)

select
    c.source_system,
    c.source_record_id,
    case when c.flag not like 'junk\_%' escape '\'
         then md5(c.source_system || '|' || c.source_record_id || '|' || c.record_occurrence) end
                                                                            as registration_key,
    c.source_file,
    c.source_row,
    c.flag,
    c.raw_value,
    coalesce(d.rule_description, 'No rule description in dq_defect_config')  as rule_description
from combined c
left join {{ ref('dq_defect_config') }} d
    on d.source_system = c.source_system and d.defect_id = c.flag
