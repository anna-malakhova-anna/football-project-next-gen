{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). The measured rate ratio of fan lapse after a child stops playing against the multiplier the generator applied to the lapse hazard
-- (sources.fan.lapse.after_child_churn_multiplier). The measured ratio is of confirmed lapses (a lapse is confirmed six quiet months after the last engagement, placed by its onset month), and it
-- is an association by construction, so a ratio near the multiplier says the measurement recovers what was built in, not that stopping causes lapsing in real data.
select
    m.rate_ratio_after_vs_while                                             as measured_rate_ratio,
    (select any_value(true_lapse_multiplier_after_child_churn) from {{ source('ground_truth', 'fan_truth') }} where is_participant_household) as true_hazard_multiplier,
    round(m.rate_ratio_after_vs_while / (select any_value(true_lapse_multiplier_after_child_churn) from {{ source('ground_truth', 'fan_truth') }} where is_participant_household), 3) as measured_over_truth
from (select distinct rate_ratio_after_vs_while from {{ ref('mart_fan_lapse_after_child_churn') }}) m
