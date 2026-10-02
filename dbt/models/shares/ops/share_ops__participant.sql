-- OPS share: one row per resolved participant with full identifiers and the survivorship results.
select
    participant_id, first_name, last_name, dob, birth_year, dob_precision, sex, home_country_code, home_region_code,
    contact_email, contact_phone, is_minor_current,
    consent_photo, consent_photo_captured_at, consent_photo_season_year,
    consent_marketing, consent_marketing_captured_at, consent_marketing_season_year,
    first_season, last_season, seasons_active, registration_count, source_systems,
    resolution_confidence, has_open_integrity_issue
from {{ ref('dim_participant') }}
