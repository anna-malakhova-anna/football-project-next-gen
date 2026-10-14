-- One row per feed: does it meet the data standard on the core (REQUIRED) fields, and on the consent (CONDITIONAL) fields club activation needs? Lists the failing fields.
select
    feed,
    count(*) filter (where requirement = 'REQUIRED')                        as core_fields,
    count(*) filter (where requirement = 'REQUIRED' and meets)              as core_fields_met,
    count(*) filter (where requirement = 'CONDITIONAL')                     as consent_fields,
    count(*) filter (where requirement = 'CONDITIONAL' and meets)           as consent_fields_met,
    count(*) filter (where requirement = 'REQUIRED' and not meets) = 0      as meets_core_standard,
    count(*) filter (where not meets) = 0                                   as meets_full_standard,
    list(field_name order by field_name) filter (where not meets)           as failing_fields
from {{ ref('p5_standard_conformance') }}
group by 1
