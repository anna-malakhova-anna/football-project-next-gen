{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). Why the estimates are where they are:
--   comparison_contamination  the weighted share of the comparison group that is in fact a participant household (an account the linkage could not
--                             link). It pulls the matched estimate toward zero, and cannot be seen without the truth.
--   fandom_*                  mean latent fandom of the naive groups (participants vs everyone else): the selection that inflates the naive estimate
--   fandom_matched_*          the same after matching: how much of the selection the matching variables removed
--   unmatched_pre_period_gap_pct   how much busier the eligible participants were than ALL comparison accounts in the 12 months before registration, with no matching: the selection the matching has to remove
--   unmatched_post_period_gap_pct  the same gap after registration (selection + effect)
--   matched_pre_period_gap_pct     the same pre-period gap after matching (should be near zero)
--   pretrend_*                the pre-period (months -12 to -1) gap between matched participants and comparisons in the event study, in % of the comparison level
with m as (select m.*, t.is_participant_household, t.latent_fandom
           from {{ ref('int_fan_cem_matched') }} m join {{ source('ground_truth', 'fan_truth') }} t on t.account_id = m.account_id),

naive as (

    select avg(latent_fandom) filter (where is_participant_household) as fandom_participants,
           avg(latent_fandom) filter (where not is_participant_household) as fandom_non_participants
    from {{ source('ground_truth', 'fan_truth') }} where account_id <> ''

)

select 'comparison_contamination' as measure,
       sum(weight) filter (where not is_treated and is_participant_household) / sum(weight) filter (where not is_treated) as value
from m
union all select 'fandom_participants', fandom_participants from naive
union all select 'fandom_non_participants', fandom_non_participants from naive
union all select 'fandom_matched_treated', sum(weight * latent_fandom) filter (where is_treated) / sum(weight) filter (where is_treated) from m
union all select 'fandom_matched_comparison', sum(weight * latent_fandom) filter (where not is_treated) / sum(weight) filter (where not is_treated) from m
union all select 'unmatched_pre_period_gap_pct', avg(pre_rate) filter (where is_treated) / avg(pre_rate) filter (where not is_treated) - 1 from {{ ref('int_fan_cem_candidates') }}
union all select 'unmatched_post_period_gap_pct', avg(post_rate) filter (where is_treated) / avg(post_rate) filter (where not is_treated) - 1 from {{ ref('int_fan_cem_candidates') }}
union all select 'matched_pre_period_gap_pct', (sum(weight * pre_rate) filter (where is_treated) / sum(weight) filter (where is_treated)) / (sum(weight * pre_rate) filter (where not is_treated) / sum(weight) filter (where not is_treated)) - 1 from {{ ref('int_fan_cem_matched') }}
union all select 'pretrend_mean_effect_pct', avg(effect_pct) from {{ ref('mart_fan_did') }} where months_since_event < 0
union all select 'pretrend_max_abs_effect_pct', max(abs(effect_pct)) from {{ ref('mart_fan_did') }} where months_since_event < 0
