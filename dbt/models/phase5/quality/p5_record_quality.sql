-- One row per in-scope (flag) feed record with every quality fact the rules in the p5_dq_rules seed need, as plain columns.
-- Nothing here judges a record: the rules (check_sql in the seed) do. Parameters (ages, lateness, season starts) come from the p5_params seed.
with params as (

    select
        max(case when param = 'youth_min_age' then value end)::integer      as youth_min_age,
        max(case when param = 'youth_max_age' then value end)::integer      as youth_max_age,
        max(case when param = 'late_days' then value end)::integer          as late_days,
        max(case when param = 'season_start_spring' then value end)         as spring_md,
        max(case when param = 'season_start_fall' then value end)           as fall_md
    from {{ ref('p5_params') }}

),

survivor_person as (

    select i.content_hash, c.p5_person_id
    from {{ ref('p5_idr_input_records') }} i
    join {{ ref('p5_clusters') }} c using (match_record_id)

),

latest as (select max(season_year) as latest_season from {{ ref('stg_p5_registrations') }}),

league_status as (

    select league_group, max(season_year) = (select latest_season from latest) as league_current
    from {{ ref('stg_p5_registrations') }} where is_flag
    group by 1

),

base as (

    select
        s.*,
        sp.p5_person_id,
        p.youth_min_age, p.youth_max_age, p.late_days,
        case s.season_term
            when 'SPRING' then make_date(s.season_year, split_part(p.spring_md, '-', 1)::integer, split_part(p.spring_md, '-', 2)::integer)
            when 'FALL' then make_date(s.season_year, split_part(p.fall_md, '-', 1)::integer, split_part(p.fall_md, '-', 2)::integer)
        end                                                                 as season_start,
        l.league_current,
        left(s.postal_code, 3)                                              as zip3
    from {{ ref('stg_p5_registrations') }} s
    cross join params p
    left join survivor_person sp on sp.content_hash = s.content_hash
    left join league_status l on l.league_group = s.league_group
    where s.is_flag

),

placed as (

    select
        b.*,
        g.market_id                                                         as zip_market_id
    from base b
    left join {{ ref('market_geo_map') }} g on g.country_code = 'US' and g.prefix = b.zip3

),

child as (

    -- agreement across the child's records (all feeds, all seasons); NULL when there is nothing to compare
    select
        *,
        count(distinct dob) over w                                          as n_dobs,
        count(distinct sex) filter (where sex <> 'U') over w                as n_sexes,
        count(distinct zip3) filter (where zip_market_id is not null) over w as n_zip3s,
        min(dob) over w                                                     as child_dob,
        count(*) over w                                                     as n_child_records
    from placed
    window w as (partition by p5_person_id)

)

select
    feed,
    source_record_id,
    p5_person_id,
    league_group,
    league_id,
    league_resolution,
    season_year,
    season_term,
    coalesce(zip_market_id, case when postal_code is null then 'UNPLACED' else 'UNMAPPED_ZIP' end) as market_id,
    -- completeness facts
    league_id is not null                                                   as has_league,
    (dob_status = 'PARSED' or nullif(trim(age_group_raw), '') is not null or nullif(trim(grade_raw), '') is not null) as has_age_signal,
    nullif(trim(zip_raw), '') is not null                                   as zip_present,
    nullif(trim(email_raw), '') is not null                                 as email_present,
    sex <> 'U'                                                              as has_sex,
    -- validity facts
    dob_status                                                              as dob_status,
    dob is not null and age_at_cutoff between youth_min_age and youth_max_age as dob_in_youth_range,
    zip_market_id is not null                                               as zip_known,
    coalesce(regexp_matches(contact_email, '^[^@\s]+@[^@\s]+\.[a-z]{2,}$'), false) as email_wellformed,
    -- uniqueness facts
    is_exact_duplicate_row,
    row_number() over (partition by p5_person_id, season_year, season_term order by registered_at nulls last, feed, source_record_id, source_row) = 1 as is_first_of_child_season,
    -- timeliness facts
    registered_at,
    date_diff('day', season_start, cast(registered_at as date))             as days_after_season_start,
    late_days,
    league_current,
    -- consistency facts (NULL = nothing to compare)
    case when dob is null or n_child_records < 2 or n_dobs < 1 then null else n_dobs = 1 end as dob_consistent,
    case when sex = 'U' or n_child_records < 2 then null else n_sexes = 1 end as sex_consistent,
    case when zip_market_id is null or n_child_records < 2 then null else n_zip3s = 1 end as zip3_consistent,
    case when nullif(trim(age_group_raw), '') is null or child_dob is null or n_dobs <> 1 then null
         else age_group_raw = case when {{ age_at_cutoff('child_dob', 'season_year') }} <= 5 then 'U6' when {{ age_at_cutoff('child_dob', 'season_year') }} <= 7 then 'U8'
                                   when {{ age_at_cutoff('child_dob', 'season_year') }} <= 9 then 'U10' when {{ age_at_cutoff('child_dob', 'season_year') }} <= 11 then 'U12'
                                   when {{ age_at_cutoff('child_dob', 'season_year') }} <= 13 then 'U14' else 'U17' end end as age_group_consistent,
    -- consent provenance facts (Phase 5 step 4 replaces these with the consent_event model)
    has_consent_record,
    consent_ts is not null                                                  as has_consent_ts,
    consent_version is not null                                             as has_consent_version,
    case when not has_consent_record then null
         else exists (select 1 from {{ ref('p5_consent_wording_map') }} w
                      where w.source_feed = child.feed and lower(w.raw_value) = lower(trim(child.consent_text))) end as consent_wording_known
from child
