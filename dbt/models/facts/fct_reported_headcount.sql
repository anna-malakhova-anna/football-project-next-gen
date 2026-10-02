{{ config(tags=['phase4']) }}
-- Fact for Source E: reported headcount at program x year grain. AGGREGATE-ONLY, and deliberately a separate fact from the participant facts:
-- a count of children in a program cannot be linked to a person, so it is never added to unique_participants (methodology v1.1, section 8).
-- Superseded duplicate reports are excluded; the headcount is the staging-repaired one (girls + boys when the stated total disagrees).
-- This model must not depend on any participant model, and no participant model may depend on it (scripts/check_lineage.py).
select
    md5(source_record_id || '|' || record_occurrence)                       as headcount_key,
    season_year                                                             as participation_year,
    country_code,
    region,
    district,
    school_or_program,
    program_type,
    program_type in ('INTRAMURAL', 'AFTER_SCHOOL')                          as is_voluntary,
    grade_band,
    girls_count,
    boys_count,
    headcount,
    is_probable_estimate,
    total_was_corrected
from {{ ref('stg_school_headcounts') }}
where not is_superseded
