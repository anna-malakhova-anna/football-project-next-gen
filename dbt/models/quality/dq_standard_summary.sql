-- depends_on: {{ ref('p5_params') }}
-- One row per source and season: does it meet the data standard on the core (REQUIRED) fields, and on the consent (CONDITIONAL) fields club activation needs? A field is met when
-- at least standard_min_conformance (p5_params, 95% by default) of the source's rows are present and valid. Lists the failing fields so the ask to the operators is concrete.
with pooled as (

    select source_system, season_year, field_name, requirement, sum(n_rows) as n_rows, sum(n_missing + n_invalid) as n_bad,
           1 - sum(n_missing + n_invalid)::double / sum(n_rows) as conformance
    from {{ ref('dq_standard_conformance') }} group by all

),

judged as (select *, conformance >= (select value::double from {{ ref('p5_params') }} where param = 'standard_min_conformance') as meets from pooled)

select
    source_system, season_year,
    count(*) filter (where requirement = 'REQUIRED')                        as core_fields,
    count(*) filter (where requirement = 'REQUIRED' and meets)              as core_fields_met,
    count(*) filter (where requirement = 'CONDITIONAL')                     as consent_fields,
    count(*) filter (where requirement = 'CONDITIONAL' and meets)           as consent_fields_met,
    count(*) filter (where requirement = 'REQUIRED' and not meets) = 0      as meets_core_standard,
    count(*) filter (where not meets) = 0                                   as meets_full_standard,
    list(field_name order by field_name) filter (where not meets)           as failing_fields
from judged group by 1, 2
