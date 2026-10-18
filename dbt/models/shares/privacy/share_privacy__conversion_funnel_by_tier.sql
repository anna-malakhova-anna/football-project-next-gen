{{ config(tags=['phase6']) }}
-- PRIVACY share, DP5 output port (Phase 6): the household conversion funnel split by the age tier of the youngest child (ADR-022). Counts of households only; a step is hidden when it or the step it follows
-- is below k_min. Steps 1 to 4 are analytics only (the household linkage policy, ADR-009); step 5 is activation (the guardian's CLUB_MARKETING permission). No household, child or contact key.
select age_tier, step_no, step, kind, households as tier_funnel_households, share_of_registered, suppressed
from {{ ref('mart_conversion_funnel_by_tier') }}
order by case age_tier when 'U13' then 1 when '13_15' then 2 when '16_17' then 3 when 'ADULT' then 4 else 5 end, step_no
