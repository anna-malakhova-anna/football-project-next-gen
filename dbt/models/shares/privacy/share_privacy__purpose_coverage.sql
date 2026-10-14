{{ config(tags=['phase5']) }}
-- PRIVACY share: which purposes does each consent text version cover? One row per consent text version and purpose. Configuration only (seeds consent_text_versions, consent_purposes); no data about people.
-- A purpose that needs its own explicit consent (separate_consent_required) is never covered by a form that merely accepts terms: purpose limitation.
select
    v.consent_text_version, p.purpose_id as purpose, p.label as purpose_label,
    list_contains(string_split(v.purposes, '|'), p.purpose_id) as form_names_purpose,
    p.separate_consent_required, p.counts_for_club_activation
from {{ ref('consent_text_versions') }} v cross join {{ ref('consent_purposes') }} p
order by v.consent_text_version, p.purpose_id
