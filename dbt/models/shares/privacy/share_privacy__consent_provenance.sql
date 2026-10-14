{{ config(tags=['phase5']) }}
-- PRIVACY share: do we know what families agreed to? Consent events by source, consent text version and provenance grade (KNOWN_FULL / KNOWN_PARTIAL / UNKNOWN), per season. Counts of consent events only: no
-- household, child or registration key, no time stamp, no contact. A cell with fewer than k_min events is suppressed (primary, then secondary within its source-season).
-- Aggregate of the restricted `linkage` consent model (ADR-009, ADR-019); an approved aggregate in the share-policy check.
with e as (

    select season_year as participation_year, source_system, coalesce(consent_text_version, 'NOT_RECORDED') as consent_text_version, provenance_grade, count(*) as consent_events
    from {{ ref('int_consent_event') }}
    group by all

)

select participation_year, source_system, consent_text_version, provenance_grade, consent_events, suppressed
from {{ suppress_small_cells('e', ['participation_year', 'source_system', 'consent_text_version', 'provenance_grade'], ['consent_events']) }}
order by participation_year, source_system, consent_text_version, provenance_grade
