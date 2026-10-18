{{ config(tags=['phase6']) }}
-- Phase 6 (ADR-022): fresh consent at 18, no carry-over. The check model must return no rows. (Vacuous on the synthetic data; the unit test `age_out_carryover_is_caught` proves the check bites.)
select participant_id as detail, 'youth profile carried to an adult household with a fan link' as problem from {{ ref('int_age_out_carryover_check') }}
