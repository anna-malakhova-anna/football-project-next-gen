{{ config(tags=['phase6']) }}
-- Phase 6 (ADR-022): fresh consent at 18, no carry-over. A participant who was a minor in an earlier year and appears as an adult later must not sit in a household that is linked to a fan account through
-- their youth record: an adult becomes their own fan record only with fresh consent. NOTE: the synthetic data has no such participant (the generator ends a child's seasons at the youth age maximum,
-- ADR-017), so this test passes with zero rows to check. It is written so that it bites the day such data exists.
with youth as (select participant_id, min(participation_year) as first_minor_year from {{ ref('int_participant_age_tier') }} where age_tier in ('U13', '13_15', '16_17') group by 1),

adult as (select participant_id, min(participation_year) as first_adult_year from {{ ref('int_participant_age_tier') }} where age_tier = 'ADULT' group by 1)

select y.participant_id as detail, 'youth profile carried to an adult household with a fan link' as problem
from youth y join adult a on a.participant_id = y.participant_id and a.first_adult_year > y.first_minor_year
join {{ ref('int_household') }} h on h.participant_id = y.participant_id
join {{ ref('link_household_fan_account') }} l on l.household_id = h.household_id
where h.is_adult_household is false
