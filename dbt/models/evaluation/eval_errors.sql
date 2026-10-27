-- GROUND TRUTH (evaluation only). The first 200 false positives and false negatives of each kind per matcher and review
-- stage (highest match probability first), from eval_errors_all, for the error analysis in ADR-003 and docs/identity_resolution.md.
-- This list is CAPPED: count errors from eval_error_categories, never from this model.
with ranked as (

    select
        *,
        row_number() over (partition by matcher, stage, error_type order by match_probability desc nulls last, record_a, record_b) as error_rank
    from {{ ref('eval_errors_all') }}

)

select
    matcher, stage, error_type, likely_cause,
    record_a, record_b, true_person_a, true_person_b, source_pair,
    tier, round(match_probability, 5) as match_probability, override_applied,
    first_name_level, last_name_level, dob_level, email_level, phone_level, context_level,
    error_rank
from ranked
where error_rank <= 200
order by matcher, stage, error_type, error_rank
