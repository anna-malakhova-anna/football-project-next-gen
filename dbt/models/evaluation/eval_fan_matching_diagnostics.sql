{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). Why the estimates are where they are:
--   comparison_contamination  the weighted share of the comparison group that is in fact a participant household (an account the linkage could not
--                             link). It pulls the matched estimate toward zero, and cannot be seen without the truth.
--   fandom_*                  mean latent fandom of the naive groups (participants vs everyone else): the selection that inflates the naive estimate
--   fandom_matched_*          the same after matching: how much of the selection the matching variables removed
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
union all select 'pretrend_mean_effect_pct', avg(effect_pct) from {{ ref('mart_fan_did') }} where months_since_event < 0
union all select 'pretrend_max_abs_effect_pct', max(abs(effect_pct)) from {{ ref('mart_fan_did') }} where months_since_event < 0
