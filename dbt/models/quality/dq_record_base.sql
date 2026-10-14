-- The one record-level stream the rule registry is evaluated against. One row per record of every source, with the SAME small set of facts for every source:
-- registrations of the three modelled sources, the six Phase 5 channel feeds (Contracted, not counted), school headcount rows, and the fan streams. A fact a source
-- cannot supply is NULL, which a rule reads as "not applicable" (never as pass or fail). No rule logic lives here: the rules are rows of dq_rule_registry.
-- person_id is the Phase 2 participant (registrations) or the Phase 5 channel resolution (channel feeds); it is the key of the consistency and uniqueness facts.
with covers as (select consent_text_version, covers_club_marketing from {{ ref('consent_text_versions') }}),

reg as (

    select
        u.source_system, u.source_record_id, u.registration_key as record_key, u.organization_id as org_id,
        u.season_year::integer as season_year, u.season_term, b.participant_id as person_id, u.dq_flags, u.registered_at,
        cast(null as boolean)                                               as org_resolved,
        u.birth_year is not null                                            as has_age_signal,
        u.contact_email is not null                                         as email_present,
        case when u.contact_email is null then null else regexp_matches(u.contact_email, '^[^@\s]+@[^@\s]+\.[a-z]{2,}$') end as email_wellformed,
        cast(null as boolean)                                               as postal_known,
        cast(null as boolean)                                               as registered_late,
        u.source_system = 'CA_CLUB' and not list_contains(u.dq_flags, 'missing_consents_object') or u.consent_photo is not null or u.consent_marketing is not null as consent_recorded,
        (u.source_system = 'CA_CLUB' and not list_contains(u.dq_flags, 'missing_consents_object'))                                                                  as consent_ts_known,
        u.consent_text_version is not null                                  as consent_version_known,
        case when u.consent_marketing is true then coalesce(c.covers_club_marketing, false) end as marketing_form_covers_purpose,
        u.dob, u.sex, case when u.source_system <> 'INTL_FED' then left(u.postal_code, 3) end as postal3, u.birth_year,
        u.dob_precision, cast(null as varchar) as age_group_raw, u.age_at_cutoff, u.season_year as season_for_age
    from {{ ref('int_registrations_unioned') }} u
    join {{ ref('bridge_registration_participant') }} b on b.registration_key = u.registration_key
    left join covers c on c.consent_text_version = u.consent_text_version

),

reg_facts as (

    select
        r.* exclude (dob, sex, postal3, birth_year, dob_precision, age_group_raw, age_at_cutoff, season_for_age),
        row_number() over (partition by person_id, season_year, season_term order by registered_at nulls last, record_key) = 1 as is_first_of_person_season,
        -- consistency across the person's records: evaluable only where at least two records carry the value; consistent when they all agree
        case when count(*) filter (where dob is not null and dob_precision = 'DAY') over w < 2 or dob is null or dob_precision <> 'DAY' then null
             else count(distinct dob) filter (where dob_precision = 'DAY') over w = 1 end as dob_consistent,
        case when count(*) filter (where sex <> 'U') over w < 2 or sex = 'U' then null
             else count(distinct sex) filter (where sex <> 'U') over w = 1 end as sex_consistent,
        case when count(*) filter (where postal3 is not null) over w < 2 or postal3 is null then null
             else count(distinct postal3) over w = 1 end as zip3_consistent,
        cast(null as boolean) as age_group_consistent,
        r.sex <> 'U' as sex_known, r.postal3 is not null as postal_present
    from reg r
    window w as (partition by person_id)

),

p5 as (

    select
        q.feed as source_system, q.source_record_id, q.feed || '|' || q.source_record_id as record_key, q.league_group as org_id,
        q.season_year, q.season_term, q.p5_person_id as person_id, s.dq_flags, q.registered_at,
        q.has_league as org_resolved, q.has_age_signal, q.email_present, q.email_wellformed,
        q.zip_known as postal_known,
        case when q.days_after_season_start is null then null else q.days_after_season_start > q.late_days end as registered_late,
        q.has_consent_record as consent_recorded, q.has_consent_ts as consent_ts_known, q.has_consent_version as consent_version_known,
        cast(null as boolean) as marketing_form_covers_purpose,
        q.is_first_of_child_season as is_first_of_person_season,
        q.dob_consistent, q.sex_consistent, q.zip3_consistent, q.age_group_consistent,
        q.has_sex as sex_known, q.zip_present as postal_present
    from {{ ref('p5_record_quality') }} q
    join {{ ref('stg_p5_registrations') }} s on s.feed = q.feed and s.source_record_id = q.source_record_id

),

other as (

    select source_system, source_record_id, source_system || '|' || source_record_id as record_key, cast(null as varchar) as org_id,
           season_year::integer as season_year, cast(null as varchar) as season_term, cast(null as varchar) as person_id, dq_flags, cast(null as timestamp) as registered_at
    from {{ ref('stg_school_headcounts') }}
    union all
    select source_system, source_record_id, source_system || '|' || source_record_id, null, year(created_at), null, null, dq_flags, created_at from {{ ref('stg_fan_accounts') }}
    union all
    select source_system, source_record_id, source_system || '|' || source_record_id, null, year(event_ts), null, null, dq_flags, event_ts from {{ ref('stg_fan_consent_events') }}
    union all
    select source_system, source_record_id, source_system || '|' || source_record_id, null, year(event_ts), null, null, dq_flags, event_ts from {{ ref('stg_fan_events') }}
    union all
    select source_system, source_record_id, source_system || '|' || source_record_id, null, year(txn_ts), null, null, dq_flags, txn_ts from {{ ref('stg_fan_transactions') }}

)

select * from reg_facts
union all by name select * from p5
union all by name select * from other
