{{ config(tags=['phase6']) }}
-- Phase 6 (ADR-022). A permission is Y only when the rules allow the purpose for the household's most restrictive child AND the purpose is covered: league operations by the registration, every other
-- purpose by a guardian consent with full provenance. A blank (NOT_CAPTURED), a decline, a revocation or incomplete provenance never gives Y (the Phase 1 to 3 NULL rule). Minors are always guardian-level.
select household_id || '|' || purpose as detail, 'permitted Y without a covering basis' as problem
from {{ ref('int_consent_permissions') }}
where permitted = 'Y' and not (basis = 'REGISTRATION' and purpose = 'LEAGUE_OPS') and not (basis = 'GUARDIAN_CONSENT' and consent_status = 'GRANTED_FULL')
union all
select household_id || '|' || purpose, 'permitted Y although the rules do not allow the purpose for this tier'
from {{ ref('int_consent_permissions') }} where permitted = 'Y' and not rule_allows
union all
select household_id || '|' || purpose, 'a minor household whose consent is not the guardian''s'
from {{ ref('int_consent_permissions') }} where governing_tier <> 'ADULT' and permitted = 'Y' and who_consents <> 'GUARDIAN'
union all
select household_id || '|' || purpose, 'a permission derived from a blank consent'
from {{ ref('int_consent_permissions') }} where consent_status = 'NOT_CAPTURED' and permitted = 'Y' and purpose <> 'LEAGUE_OPS'
