-- RESTRICTED (schema `phase6_restricted`). One row per participant and participation year: the age tier (U13, 13_15, 16_17, ADULT, or UNKNOWN when no age can be computed) and the age-rule jurisdiction.
-- Age is the Phase 1 convention (completed years on Dec 31 of the season year, ADR-002; fct_participant_year.age_at_cutoff). Tier boundaries are vars (age_tier_*). The jurisdiction comes from the
-- participant's attributed country and home region through the seed age_consent_jurisdiction_map; a country not listed gets DEFAULT, the strictest rules (ADR-022).
-- UNKNOWN age is NOT treated as an adult: the permission model applies the strictest minor row to it.
-- When the participant's own registrations disagree on the birth year (a year typed off by one, say), the tier uses the YOUNGEST age they support, not the survivorship birth year
-- of dim_participant: that birth year breaks a tie by recency, so one mistyped record could make a 17-year-old an adult. For a consent rule an age in doubt is the stricter one (ADR-022).
-- On Dec 31 the completed age is the season year minus the birth year, so each registration's birth year is participation_year - age_at_cutoff. Only a plausible age can raise the doubt:
-- an age below p5_params.youth_min_age (the DQ rule's floor for a youth league) is a broken date of birth, not a younger child.
with youngest as (

    select participant_id, max(participation_year - age_at_cutoff) as youngest_birth_year
    from {{ ref('fct_registration') }}
    where is_valid_registration and age_at_cutoff >= (select cast(value as integer) from {{ ref('p5_params') }} where param = 'youth_min_age')
    group by 1

),

aged as (

    select f.participant_id, f.participation_year, f.attributed_country_code,
           -- an UNKNOWN age stays unknown (least() would skip the NULL and take the registration's age)
           case when f.age_at_cutoff is not null then least(f.age_at_cutoff, f.participation_year - y.youngest_birth_year) end as age_at_cutoff
    from {{ ref('fct_participant_year') }} f
    left join youngest y on y.participant_id = f.participant_id

)

select
    f.participant_id,
    f.participation_year,
    f.age_at_cutoff,
    case when f.age_at_cutoff is null then 'UNKNOWN'
         when f.age_at_cutoff < {{ var('age_tier_13_15_from') }} then 'U13'
         when f.age_at_cutoff < {{ var('age_tier_16_17_from') }} then '13_15'
         when f.age_at_cutoff < {{ var('age_tier_adult_from') }} then '16_17'
         else 'ADULT' end                                                   as age_tier,
    coalesce(m1.jurisdiction, m2.jurisdiction, 'DEFAULT')                   as jurisdiction
from aged f
join {{ ref('dim_participant') }} p on p.participant_id = f.participant_id
left join {{ ref('age_consent_jurisdiction_map') }} m1 on m1.country_code = f.attributed_country_code and m1.region_code = p.home_region_code
left join {{ ref('age_consent_jurisdiction_map') }} m2 on m2.country_code = f.attributed_country_code and coalesce(m2.region_code, '') = ''
