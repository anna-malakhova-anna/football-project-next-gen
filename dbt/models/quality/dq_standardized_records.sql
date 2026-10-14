-- depends_on: {{ ref('data_standard_fields') }}
-- What every registration source looks like in the shape of the data standard (seed data_standard_fields): one column per standard field, one row per submitted record (exact duplicates
-- excluded), plus grp_* grouping columns for the validation. A value a source cannot supply is NULL, never filled in: INTL returns carry no postal code, vendor_reg_b has no birth year,
-- school rosters have no parent email or ZIP, only one platform emits a consent timestamp. consent_purposes is the purposes named by the wording version the form used
-- (consent_text_versions), or, for the channel feeds, the purposes read through p5_consent_wording_map (an ASSUMPTION per row there) plus CLUB_MARKETING only where the parent ticked a box.
-- Tackle rows of the mixed Pop Warner feed are kept (program_type TACKLE) so the check can show a mixed feed sends records it should not.
with versions as (select consent_text_version, purposes from {{ ref('consent_text_versions') }}),

modelled as (

    select
        u.source_system as grp_source_system, u.organization_id as grp_org_id, u.season_year::varchar as grp_season_year,
        u.source_record_id,
        u.organization_id                                                   as org_id,
        u.season_year::varchar                                              as season_year,
        u.season_term,
        'FLAG'                                                              as program_type,
        u.first_name                                                        as child_given_name,
        u.last_name                                                         as child_family_name,
        u.birth_year::varchar                                               as birth_year,
        u.sex,
        left(u.postal_code, 3)                                              as home_zip3,
        u.contact_email                                                     as parent_email,
        strftime(u.registered_at, '%Y-%m-%d %H:%M:%S')                      as registered_at,
        cast(null as varchar)                                               as consent_recorded_at,
        u.consent_text_version,
        v.purposes                                                          as consent_purposes,
        cast(null as varchar)                                               as consent_method
    from {{ ref('int_registrations_unioned') }} u
    left join versions v on v.consent_text_version = u.consent_text_version
    where not coalesce(u.is_exact_duplicate, false)

),

channel as (

    select
        s.feed as grp_source_system, s.league_group as grp_org_id, s.season_year::varchar as grp_season_year,
        s.source_record_id,
        s.league_id                                                         as org_id,
        s.season_year::varchar                                              as season_year,
        s.season_term,
        case when s.is_flag then 'FLAG' else 'TACKLE' end                   as program_type,
        s.first_name                                                        as child_given_name,
        s.last_name                                                         as child_family_name,
        s.birth_year::varchar                                               as birth_year,
        case s.sex when 'M' then 'M' when 'F' then 'F' when 'U' then 'U' end as sex,
        left(s.postal_code, 3)                                              as home_zip3,
        s.contact_email                                                     as parent_email,
        strftime(s.registered_at, '%Y-%m-%d %H:%M:%S')                      as registered_at,
        strftime(s.consent_ts, '%Y-%m-%d %H:%M:%S')                         as consent_recorded_at,
        s.consent_version                                                   as consent_text_version,
        nullif(concat_ws('|', w.purposes_covered, case when s.consent_marketing then 'NFL_CLUB_MARKETING' end), '') as consent_purposes,
        cast(null as varchar)                                               as consent_method
    from {{ ref('stg_p5_registrations') }} s
    left join {{ ref('p5_consent_wording_map') }} w
        on w.source_feed = s.feed and lower(w.raw_value) = lower(trim(s.consent_text)) and w.meaning = 'GRANTED'
    where not s.is_exact_duplicate_row

)

select * from modelled
union all
select * from channel
