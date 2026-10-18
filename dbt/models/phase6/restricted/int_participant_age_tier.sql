-- RESTRICTED (schema `phase6_restricted`). One row per participant and participation year: the age tier (U13, 13_15, 16_17, ADULT, or UNKNOWN when no age can be computed) and the age-rule jurisdiction.
-- Age is the Phase 1 convention (completed years on Dec 31 of the season year, ADR-002; fct_participant_year.age_at_cutoff). Tier boundaries are vars (age_tier_*). The jurisdiction comes from the
-- participant's attributed country and home region through the seed age_consent_jurisdiction_map; a country not listed gets DEFAULT, the strictest rules (ADR-022).
-- UNKNOWN age is NOT treated as an adult: the permission model applies the strictest minor row to it.
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
from {{ ref('fct_participant_year') }} f
join {{ ref('dim_participant') }} p on p.participant_id = f.participant_id
left join {{ ref('age_consent_jurisdiction_map') }} m1 on m1.country_code = f.attributed_country_code and m1.region_code = p.home_region_code
left join {{ ref('age_consent_jurisdiction_map') }} m2 on m2.country_code = f.attributed_country_code and coalesce(m2.region_code, '') = ''
