-- Phase 5 staging: the six feeds in one common shape, one row per feed record (duplicates and bad values flagged, never dropped).
-- SQL does all the typing and cleaning; raw stays strings. A value that cannot be read becomes NULL and a flag, never a guess:
--   * DOB with a two-digit year is NULL (19xx or 20xx?), not read as 20xx
--   * a Pop Warner row whose association runs two flag leagues and has no league code stays unresolved
--   * a free-text league name that is not in the alias map stays unresolved
-- Season term: Pop Warner has only a year, so the term is read from the month the record was created (before July = SPRING); school programs are ANNUAL.
-- ASSUMPTION: all feed shapes and consent wordings are assumptions made for the demonstration.
with mx as (

    select
        'matrix_export' as feed, registration_id as source_record_id, _source_file as source_file, _row_number as source_row,
        cast(left(season_label, 4) as integer) as season_year, upper(split_part(season_label, ' ', 2)) as season_term,
        league_id as league_key, cast(null as varchar) as league_text, cast(null as varchar) as league_code,
        participant_first_name as first_raw, participant_last_name as last_raw,
        date_of_birth as dob_raw, cast(null as varchar) as age_group_raw, cast(null as varchar) as grade_raw, gender as sex_raw,
        parent_email as email_raw, parent_zip as zip_raw, cast(null as varchar) as parent_name_raw,
        try_cast(registered_at as timestamp) as registered_at, true as is_flag,
        consent_scope as consent_text, try_cast(nullif(consent_ts, '') as timestamp) as consent_ts, nullif(consent_version, '') as consent_version,
        marketing_opt_in as marketing_raw,
        (nullif(consent_scope, '') is not null or nullif(consent_ts, '') is not null or nullif(consent_version, '') is not null
            or nullif(marketing_opt_in, '') is not null) as has_consent_record,
        'MDY' as dob_fmt
    from {{ source('raw_p5', 'p5_matrix_export') }}

),

va as (

    select
        'vendor_reg_a', reg_ref, _source_file, _row_number,
        cast(regexp_extract(season, '(\d{4})', 1) as integer), upper(split_part(season, ' ', 1)),
        cast(null as varchar), org_name, cast(null as varchar),
        child_fname, child_lname, birthdate, cast(null as varchar), cast(null as varchar), child_sex,
        guardian_email, postal_code, cast(null as varchar),
        try_cast(registered_at as timestamp), true,
        tos_accepted_text, try_cast(nullif(tos_accepted_at, '') as timestamp), cast(null as varchar),
        case marketing_checkbox when 'checked' then 'Y' when 'unchecked' then 'N' else '' end,
        (nullif(tos_accepted_text, '') is not null or nullif(tos_accepted_at, '') is not null or nullif(marketing_checkbox, '') is not null),
        'ANY'
    from {{ source('raw_p5', 'p5_vendor_reg_a') }}

),

vb as (

    select
        'vendor_reg_b', confirmation_no, _source_file, _row_number,
        cast(regexp_extract(term, '(\d{4})', 1) as integer), upper(split_part(term, ' ', 1)),
        org_code, cast(null as varchar), cast(null as varchar),
        child_first, child_last, cast(null as varchar), age_group, cast(null as varchar), cast(null as varchar),
        parent_email, zip, parent_name,
        try_cast(confirmation_date as timestamp), true,
        consent_given, cast(null as timestamp), cast(null as varchar),
        cast(null as varchar),
        nullif(consent_given, '') is not null,
        'MDY'
    from {{ source('raw_p5', 'p5_vendor_reg_b') }}

),

pw as (

    select
        'pop_warner_feed', record_id, _source_file, _row_number,
        cast(season_year as integer), case when month(try_cast(created_at as timestamp)) < 7 then 'SPRING' else 'FALL' end,
        association_id, cast(null as varchar), nullif(flag_league_code, ''),
        player_first, player_last, birth_date, cast(null as varchar), cast(null as varchar), gender,
        guardian_email, guardian_zip, cast(null as varchar),
        try_cast(created_at as timestamp), program_type = 'FLAG',
        waiver_signed, cast(null as timestamp), cast(null as varchar),
        cast(null as varchar),
        nullif(waiver_signed, '') is not null,
        'MDY'
    from {{ source('raw_p5', 'p5_pop_warner_feed') }}

),

pal as (

    select
        'pal_chapter_csv', 'PAL-' || regexp_extract(_source_file, '(\d{4})', 1) || '-' || lpad(cast(_row_number as varchar), 6, '0'), _source_file, _row_number,
        cast(regexp_extract("Season", '(\d{4})', 1) as integer), upper(split_part("Season", ' ', 1)),
        "Chapter", cast(null as varchar), cast(null as varchar),
        "Player First", "Player Last", "DOB", cast(null as varchar), cast(null as varchar), "Sex",
        "Parent Email", "ZIP", "Parent/Guardian",
        cast(null as timestamp), true,
        "Permission Slip", cast(null as timestamp), cast(null as varchar),
        cast(null as varchar),
        nullif("Permission Slip", '') is not null,
        'MDY'
    from {{ source('raw_p5', 'p5_pal_chapter_csv') }}

),

sc as (

    select
        'school_program', roster_id, _source_file, _row_number,
        cast(left(school_year, 4) as integer) + 1, 'ANNUAL',          -- school year 2024-25 is the 2025 season
        school_code, cast(null as varchar), cast(null as varchar),
        student_first, student_last, cast(null as varchar), cast(null as varchar), grade, sex,
        cast(null as varchar), cast(null as varchar), cast(null as varchar),
        cast(null as timestamp), true,
        cast(null as varchar), cast(null as timestamp), cast(null as varchar),
        cast(null as varchar),
        false,
        'MDY'
    from {{ source('raw_p5', 'p5_school_program') }}

),

unioned as (

    select * from mx
    union all select * from va
    union all select * from vb
    union all select * from pw
    union all select * from pal
    union all select * from sc

),

aliases as (

    -- a spelling that the map sends to two leagues (same name in two states) is ambiguous: it resolves to neither
    select alias, count(distinct league_id) as n_leagues, min(league_id) as league_id
    from {{ source('raw_p5', 'p5_league_alias_map') }}
    group by 1

),

resolved as (

    select
        u.*,
        case
            when u.feed = 'vendor_reg_a' then case when am.n_leagues = 1 then am.league_id end
            when u.feed = 'pop_warner_feed' then coalesce(case when k.n_leagues = 1 then k.league_id end, kc.league_id)
            else k.league_id
        end                                                                 as league_id,
        case
            when u.feed = 'vendor_reg_a' then
                case when am.n_leagues = 1 then 'ALIAS' when am.n_leagues > 1 then 'AMBIGUOUS_NAME' else 'UNMAPPED_NAME' end
            when k.n_leagues is null then 'UNKNOWN_KEY'
            when u.feed = 'pop_warner_feed' then
                case when k.n_leagues = 1 then 'KEY' when kc.league_id is not null then 'KEY_AND_CODE' else 'AMBIGUOUS_ASSOCIATION' end
            else 'KEY'
        end                                                                 as league_resolution
    from unioned u
    left join (select source_feed, source_key, count(*) as n_leagues, min(league_id) as league_id
               from {{ source('raw_p5', 'p5_league_catalog') }} group by 1, 2) k
        on k.source_feed = u.feed and k.source_key = u.league_key
    left join {{ source('raw_p5', 'p5_league_catalog') }} kc
        on u.feed = 'pop_warner_feed' and kc.source_feed = u.feed and kc.source_key = u.league_key and kc.flag_code = u.league_code
    left join aliases am on u.feed = 'vendor_reg_a' and am.alias = u.league_text

),

cleaned as (

    select
        r.feed, r.source_record_id, r.source_file, r.source_row,
        r.season_year, r.season_term, r.season_year::varchar || '-' || r.season_term as season_key,
        r.league_id, r.league_resolution,
        coalesce(r.league_id, 'UNRESOLVED:' || r.feed) as league_group,
        r.is_flag,
        {{ normalize_name('r.first_raw') }} as first_name, {{ normalize_name('r.last_raw') }} as last_name,
        {{ name_key('r.first_raw') }} as first_name_key, {{ name_key('r.last_raw') }} as last_name_key,
        case r.dob_fmt when 'ANY' then {{ parse_flexible_date('r.dob_raw', 'ANY') }} else {{ parse_flexible_date('r.dob_raw', 'MDY') }} end as dob_parsed,
        r.dob_raw,
        r.age_group_raw, r.grade_raw,
        coalesce(g.sex_code, 'U') as sex,
        {{ normalize_email('r.email_raw') }} as contact_email, r.email_raw,
        {{ normalize_us_zip('r.zip_raw') }} as postal_code, r.zip_raw,
        r.parent_name_raw,
        r.registered_at,
        r.consent_text, r.consent_ts, r.consent_version, r.has_consent_record,
        {{ to_consent_boolean('r.marketing_raw') }} as consent_marketing,
        md5(concat_ws('|', r.feed, r.league_key, r.league_text, r.season_year, r.season_term, r.first_raw, r.last_raw, r.dob_raw, r.email_raw, r.zip_raw,
            r.consent_text, r.is_flag)) as content_hash
    from resolved r
    left join {{ ref('gender_map') }} g on lower(trim(r.sex_raw)) = lower(g.source_value)

),

dated as (

    select
        *,
        -- a four-digit year is required; two-digit years, month names and the like are read by the macro only where they are unambiguous
        case when dob_parsed is not null then dob_parsed
             when regexp_matches(trim(dob_raw), '^[A-Za-z]+ \d{1,2}, \d{4}$') then cast(try_strptime(trim(dob_raw), '%B %d, %Y') as date)
             when regexp_matches(trim(dob_raw), '^\d{1,2} [A-Za-z]{3} \d{4}$') then cast(try_strptime(trim(dob_raw), '%d %b %Y') as date)
        end as dob
    from cleaned

)

select
    * exclude (dob_parsed),
    extract(year from dob)::integer                                         as birth_year,
    case when dob is not null then 'DAY' end                                as dob_precision,
    case when dob is not null then {{ age_at_cutoff('dob', 'season_year') }} end as age_at_cutoff,
    row_number() over (partition by content_hash order by source_file, source_row) > 1 as is_exact_duplicate_row,
    case when nullif(trim(dob_raw), '') is null then 'BLANK'
         when dob is not null then 'PARSED'
         when regexp_matches(trim(dob_raw), '^\d{1,2}/\d{1,2}/\d{2}$') then 'TWO_DIGIT_YEAR'
         else 'UNPARSEABLE' end                                             as dob_status
from dated
