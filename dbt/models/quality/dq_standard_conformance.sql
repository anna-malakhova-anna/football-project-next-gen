-- depends_on: {{ ref('data_standard_fields') }}
-- Every source against the data standard, field by field, per organization and season: rows, rows missing the field, rows present but invalid, and the share present and valid.
-- The validation SQL is the validate_against_standard macro, so it applies to any new feed. Measured and reported here; the standard is the ASK, so these rows are INFO in the registry
-- (never scored into the purpose scores, which would count a missing ZIP twice).
select
    grp_source_system as source_system, grp_org_id as org_id, grp_season_year::integer as season_year,
    field_name, requirement, n_rows, n_missing, n_invalid,
    round(1 - (n_missing + n_invalid)::double / n_rows, 4) as conformance
from (
    {{ validate_against_standard(ref('dq_standardized_records')) }}
)
