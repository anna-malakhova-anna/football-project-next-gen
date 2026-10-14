{{ config(tags=['phase5']) }}
-- depends_on: {{ ref('p5_params') }}
-- What analytics survive the deletion policy, and which do not (Phase 5 spec 10). Label-free: counts and retention figures only, no ground truth.
-- Read from retention_audit.deletion_runs, written by `make retention-vs-deletion` (retention/zones.py), which deletes in a COPY of the warehouse and rebuilds there:
--   BASELINE          the figure before any deletion
--   FACTS_ONLY        child-level identifiers anonymized in the identity and linkage zones, the Phase 4 retention marts rebuilt from the remaining pseudonymous, coarsened facts
--   IDENTITY_REBUILT  the same, and identity resolution then re-run on the anonymized inputs (what happens if the pipeline is simply rebuilt after deletion)
-- A figure SURVIVES a scenario when it moves by no more than phase5.retention.survival_tolerance (p5_params). Tolerates a missing table (empty until the experiment has run).
{% set rel = adapter.get_relation(database=target.database, schema='retention_audit', identifier='deletion_runs') %}
with runs as (

    {% if rel is not none %}
    select * from {{ source('retention_audit', 'deletion_runs') }}
    {% else %}
    select cast(null as varchar) as scenario, cast(null as varchar) as metric, cast(null as double) as value where false
    {% endif %}

),

wide as (

    select metric,
           max(value) filter (where scenario = 'BASELINE')         as baseline,
           max(value) filter (where scenario = 'FACTS_ONLY')       as facts_only,
           max(value) filter (where scenario = 'IDENTITY_REBUILT') as identity_rebuilt
    from runs group by 1

)

select
    metric,
    case metric
        when 'participants' then 'Unique participants (all years)'
        when 'participant_years' then 'Participant-years'
        when 'participants_with_two_or_more_seasons' then 'Participants seen in two or more seasons'
        when 'youth_then_adult_participants' then 'Participants with youth history who also appear as adults'
        when 'retention_entrants' then 'Retention entrants'
        when 'retention_at_step_1' then 'Retained one season after entry (Kaplan-Meier)'
        when 'retention_at_step_2' then 'Retained two seasons after entry'
        when 'retention_at_step_3' then 'Retained three seasons after entry'
    end as label,
    baseline, facts_only, identity_rebuilt,
    round((facts_only - baseline) / nullif(baseline, 0), 4)       as facts_only_change,
    round((identity_rebuilt - baseline) / nullif(baseline, 0), 4) as identity_rebuilt_change,
    case when baseline = 0 then facts_only = 0 else abs(facts_only - baseline) / baseline <= {{ p5_param('retention_survival_tolerance') }} end               as survives_facts_only,
    case when baseline = 0 then identity_rebuilt = 0 else abs(identity_rebuilt - baseline) / baseline <= {{ p5_param('retention_survival_tolerance') }} end   as survives_identity_rebuilt,
    {{ p5_param('retention_survival_tolerance') }}                                                                                                   as tolerance,
    case metric
        when 'youth_then_adult_participants' then 'Zero in the baseline too: this synthetic data has no child who plays on as an adult inside the window, so the loss the policy is most likely to cause here (re-linking a returning adult to their youth history) cannot be shown by it.'
        when 'participants_with_two_or_more_seasons' then 'Links between a child''s own seasons are lost when identity is re-run without names, date of birth and contacts.'
        else null
    end as note
from wide
