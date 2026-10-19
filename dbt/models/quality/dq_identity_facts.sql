-- DP2. The quality facts that need the RESOLVED PERSON, one row per record of the modelled sources and the Phase 5 channel feeds, keyed by record_key (the same key as dq_record_base):
--   person_id                    the Phase 2 participant (registrations) or the Phase 5 channel resolution (channel feeds)
--   is_first_of_person_season    uniqueness: the person's first record of the season (post-resolution)
--   dob / sex / zip3 / age_group _consistent   agreement across the person's records: evaluable only where at least two records carry the value; NULL = nothing to compare
-- Nothing here judges a record: the identity rules of dq_rule_registry do (dq_identity_rule_results). DP1's dq_record_base holds every other fact; dq_record_resolved joins the two.
with reg as (

    select
        u.registration_key as record_key, b.participant_id as person_id, u.season_year::integer as season_year, u.season_term, u.registered_at,
        u.dob, u.dob_precision, u.sex, case when u.source_system <> 'INTL_FED' then left(u.postal_code, 3) end as postal3
    from {{ ref('int_registrations_unioned') }} u
    join {{ ref('bridge_registration_participant') }} b on b.registration_key = u.registration_key

),

reg_facts as (

    select
        record_key, person_id,
        row_number() over (partition by person_id, season_year, season_term order by registered_at nulls last, record_key) = 1 as is_first_of_person_season,
        -- consistency across the person's records: evaluable only where at least two records carry the value; consistent when they all agree
        case when count(*) filter (where dob is not null and dob_precision = 'DAY') over w < 2 or dob is null or dob_precision <> 'DAY' then null
             else count(distinct dob) filter (where dob_precision = 'DAY') over w = 1 end as dob_consistent,
        case when count(*) filter (where sex <> 'U') over w < 2 or sex = 'U' then null
             else count(distinct sex) filter (where sex <> 'U') over w = 1 end as sex_consistent,
        case when count(*) filter (where postal3 is not null) over w < 2 or postal3 is null then null
             else count(distinct postal3) over w = 1 end as zip3_consistent,
        cast(null as boolean) as age_group_consistent
    from reg
    window w as (partition by person_id)

),

p5 as (

    select
        feed || '|' || source_record_id as record_key, p5_person_id as person_id, is_first_of_child_season as is_first_of_person_season,
        dob_consistent, sex_consistent, zip3_consistent, age_group_consistent
    from {{ ref('p5_record_identity') }}

)

select * from reg_facts
union all by name select * from p5
