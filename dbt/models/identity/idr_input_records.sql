-- depends_on: {{ ref('minimization_variants') }}
-- One row per registration that identity resolution works on.
--   * exact duplicates (same source_record_id repeated) are collapsed to one surviving record; the keys of
--     every collapsed copy are carried in `member_registration_keys`, so the bridge table still maps them all
--   * records with an impossible DOB are kept, with DOB and birth year nulled for matching: they can still
--     match on name, email and phone
--   * near-duplicates (a different record id) are NOT collapsed: they are matching candidates
--   * var minimization_variant (default V0_FULL, seed minimization_variants): dob, postal code, phone and email are coarsened here, once, before any matching (macros/minimization.sql)
with ranked as (

    select
        *,
        row_number() over (
            partition by source_system, source_record_id
            order by registered_at nulls last, record_occurrence, registration_key
        ) as survivor_rank,
        list(registration_key) over (partition by source_system, source_record_id) as member_registration_keys,
        count(*) over (partition by source_system, source_record_id) as collapsed_count
    from {{ ref('int_registrations_unioned') }}

)

select
    registration_key                                                        as match_record_id,
    source_system,
    source_record_id,
    source_person_id,
    season_label,
    season_year,
    season_term,
    season_year::varchar || '-' || season_term                              as season_key,
    organization_id,
    country_code,
    region_code,
    first_name,
    last_name,
    first_name_key,
    last_name_key,
    case when is_impossible_dob then null else {{ min_dob('dob', 'dob_precision') }} end as dob,
    case when is_impossible_dob then null else birth_year end               as birth_year,
    case when is_impossible_dob then null else {{ min_dob_precision('dob_precision', 'birth_year') }} end as dob_precision,
    is_impossible_dob                                                       as dob_nulled,
    sex,
    {{ min_email('contact_email') }}                                       as contact_email,
    {{ min_phone('contact_phone') }}                                       as contact_phone,
    {{ min_postal('postal_code') }}                                        as postal_code,
    canonical_division,
    is_minor,
    consent_photo,
    consent_marketing,
    registered_at,
    member_registration_keys,
    collapsed_count
from ranked
where survivor_rank = 1
