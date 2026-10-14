-- What each feed WOULD look like if it already submitted in the shape of the data standard (p5_data_standard): one column per standard field, one row per feed record.
-- A value the feed cannot supply is NULL, never filled in: vendor_reg_b has no birth year, school_program has no parent email or ZIP, only matrix_export has a consent version.
-- Tackle rows are kept (program_type TACKLE) so the standard check can show that a mixed feed sends records it should not.
-- consent_purposes is inferred from the wording through p5_consent_wording_map (an ASSUMPTION per row there) plus NFL_CLUB_MARKETING only where the parent ticked a marketing box.
select
    s.feed,
    s.source_record_id,
    s.league_id,
    s.season_year::varchar                                                  as season_year,
    s.season_term,
    case when s.is_flag then 'FLAG' else 'TACKLE' end                       as program_type,
    s.first_name                                                            as child_given_name,
    s.last_name                                                             as child_family_name,
    s.birth_year::varchar                                                   as birth_year,
    case s.sex when 'M' then 'M' when 'F' then 'F' when 'U' then 'U' end    as sex,
    left(s.postal_code, 3)                                                  as home_zip3,
    s.contact_email                                                         as parent_email,
    strftime(s.registered_at, '%Y-%m-%d %H:%M:%S')                          as registered_at,
    strftime(s.consent_ts, '%Y-%m-%d %H:%M:%S')                             as consent_recorded_at,
    s.consent_version                                                       as consent_text_version,
    nullif(concat_ws('|', w.purposes_covered, case when s.consent_marketing then 'NFL_CLUB_MARKETING' end), '') as consent_purposes,
    cast(null as varchar)                                                   as consent_method
from {{ ref('stg_p5_registrations') }} s
left join {{ ref('p5_consent_wording_map') }} w
    on w.source_feed = s.feed and lower(w.raw_value) = lower(trim(s.consent_text)) and w.meaning = 'GRANTED'
where not s.is_exact_duplicate_row
