-- depends_on: {{ ref('dq_rule_registry') }}
-- One row per registration (the three modelled sources and the six Phase 5 channel feeds): is this record fit for each purpose, and which rules does it fail?
-- A record is fit for a purpose when it fails NO record-level rule of severity ERROR or WARN that lists the purpose (INFO rules never judge a record). Whether a chain of
-- records is fit is the scorecards' question; this is the record's own. failing_rules_<purpose> names the registry rules, so a fix can be traced to a rule and its guidance.
with f as (

    select
        source_system, source_record_id, record_key, org_id, season_year, season_term, person_id,
        {{ dq_fitness_columns() }}
    from {{ ref('dq_record_base') }}
    where person_id is not null

),

grade as (

    -- the registration's consent provenance: KNOWN_FULL when every consent event it carries is, KNOWN_PARTIAL when some evidence is known, UNKNOWN when it carries none
    select registration_key,
           case when bool_and(provenance_grade = 'KNOWN_FULL') then 'KNOWN_FULL' when bool_or(provenance_grade in ('KNOWN_FULL', 'KNOWN_PARTIAL')) then 'KNOWN_PARTIAL' else 'UNKNOWN' end as consent_provenance_grade
    from {{ ref('int_consent_event') }} where registration_key is not null group by 1

)

select
    f.*,
    coalesce(g.consent_provenance_grade, 'UNKNOWN')         as consent_provenance_grade,
    len(failing_rules_count) = 0    as fit_for_count,
    len(failing_rules_segment) = 0  as fit_for_segment,
    len(failing_rules_geo) = 0      as fit_for_geo,
    len(failing_rules_retain) = 0   as fit_for_retain,
    len(failing_rules_activate) = 0 as fit_for_activate
from f left join grade g on g.registration_key = f.record_key
