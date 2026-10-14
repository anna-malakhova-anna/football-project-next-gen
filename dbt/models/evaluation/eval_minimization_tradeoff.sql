{{ config(tags=['phase5']) }}
-- GROUND TRUTH (evaluation only). The minimization frontier: for each variant (seed minimization_variants), what is lost in identity accuracy and data fitness, and what is gained in privacy?
--   accuracy   from eval.minimization_runs (written by scripts/p5_minimization_runs.py, which runs the whole Phase 2 identity chain once per variant and grades it against the answer key)
--   risk       mart_reidentification_risk (label-free)
--   fitness    mart_minimization_fitness (label-free)
-- Headline matcher: Fellegi-Sunter, before review, automatic links only (no steward in the loop, no probable pairs): the matcher alone. The rules matcher is listed beside it.
-- A sibling or twin false merge is a privacy incident (one child's consent applied to another); precision comes first, recall is a cost in duplicates, which inflate counts.
-- NOTHING is tuned to a variant: the reasoned m-probabilities are the same for every run, and only u (estimated from the data without labels) adapts to the coarsened input.
-- Tolerates a missing eval.minimization_runs (the frontier is simply empty until `make minimize` has run).
{% set runs = adapter.get_relation(database=target.database, schema='eval', identifier='minimization_runs') %}
with runs as (

    {% if runs is not none %}
    select * from {{ source('ground_truth', 'minimization_runs') }}
    {% else %}
    select cast(null as varchar) as variant_id, cast(null as varchar) as matcher, cast(null as integer) as records, cast(null as double) as precision, cast(null as double) as recall, cast(null as double) as f1,
           cast(null as integer) as sibling_or_twin_false_merges, cast(null as integer) as twin_false_merges, cast(null as integer) as true_participants,
           cast(null as integer) as predicted_participants, cast(null as integer) as participant_count_error, cast(null as double) as participant_count_error_pct,
           cast(null as double) as split_rate_pct, cast(null as double) as merge_rate_pct
    where false
    {% endif %}

)

select
    v.variant_id, v.sort_order, v.label, v.in_standard, r.matcher, r.matcher = 'fs' as is_headline_matcher,
    r.records, r.precision, r.recall, r.f1,
    r.sibling_or_twin_false_merges, r.twin_false_merges,
    r.true_participants, r.predicted_participants, r.participant_count_error, r.participant_count_error_pct, r.split_rate_pct, r.merge_rate_pct,
    k.pct_rows_below_k_min, k.pct_unique, k.smallest_class, k.average_class_size, k.contact_fields_held,
    f.fit_for_count, f.fit_for_segment, f.fit_for_geo, f.fit_for_retain, f.fit_for_activate, f.rules_no_longer_evaluable
from {{ ref('minimization_variants') }} v
left join runs r on r.variant_id = v.variant_id
left join {{ ref('mart_reidentification_risk') }} k on k.variant_id = v.variant_id
left join {{ ref('mart_minimization_fitness') }} f on f.variant_id = v.variant_id
