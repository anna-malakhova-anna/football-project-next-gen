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

)

select
    *,
    len(failing_rules_count) = 0    as fit_for_count,
    len(failing_rules_segment) = 0  as fit_for_segment,
    len(failing_rules_geo) = 0      as fit_for_geo,
    len(failing_rules_retain) = 0   as fit_for_retain,
    len(failing_rules_activate) = 0 as fit_for_activate
from f
