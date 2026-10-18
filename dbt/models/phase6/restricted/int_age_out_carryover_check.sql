-- RESTRICTED (schema `phase6_restricted`). Fresh consent at 18, no carry-over (ADR-022): a participant who was a minor in an earlier year and appears as an adult later must not sit in a household
-- (one with children in it) that is linked to a fan account through the youth record: an adult becomes their own fan record only with fresh consent. One row per VIOLATION; the data test requires zero.
-- The synthetic data has no participant who plays on as an adult (the generator ends a child's seasons at the youth age maximum), so on real data this is empty; the unit test below gives it a
-- participant who ages out with a fan link and requires it to be caught.
with youth as (

    select participant_id, min(participation_year) as first_minor_year from {{ ref('int_participant_age_tier') }} where age_tier in ('U13', '13_15', '16_17') group by 1

),

adult as (

    select participant_id, min(participation_year) as first_adult_year from {{ ref('int_participant_age_tier') }} where age_tier = 'ADULT' group by 1

)

select y.participant_id, h.household_id, y.first_minor_year, a.first_adult_year
from youth y
join adult a on a.participant_id = y.participant_id and a.first_adult_year > y.first_minor_year
join {{ ref('int_household') }} h on h.participant_id = y.participant_id
join {{ ref('link_household_fan_account') }} l on l.household_id = h.household_id
where h.is_adult_household is false
