-- depends_on: {{ ref('dq_rule_registry') }}
-- depends_on: {{ ref('dq_record_base') }}
-- depends_on: {{ ref('dq_org_season_base') }}
-- The long-form fact everything in the data quality layer reads: one row per rule x grain key x purpose.
--   RECORD rules (origin PHASE1, PHASE5)  are evaluated over dq_record_base and aggregated to (source, organization, season); an organization-less stream (fan, school) is keyed by source and season
--   ORG_SEASON rules                      are evaluated over dq_org_season_base (dark organizations included)
--   CONTRACT rules                        are the contract's own measurement (quality.dq_contract_results, written by scripts/validate_contracts.py), read here, not re-measured:
--                                         the contract's maximum violation rate becomes a minimum pass rate; the grain is the source over all seasons
-- observed_value is a pass rate in [0, 1]. threshold is the registry's minimum pass rate for that purpose; `pass` is NULL for a rule with no threshold for any purpose (INFO) and
-- when nothing was evaluable. A rule listing several purposes yields one row per purpose, so a purpose is judged against its own bar.
with registry as (select * from {{ ref('dq_rule_registry') }}),

measured as (

    {{ dq_record_rule_results() }}
    union all
    {{ dq_record_rule_results('ORG_SEASON', 'dq_org_season_base') }}

),

contract as (

    select
        r.rule_id, c.source_system, cast(null as varchar) as org_id, cast(null as integer) as season_year,
        1 as n_evaluated, case when c.observed <= c.threshold then 1 else 0 end as n_pass, 1 - c.observed as pass_rate_override
    from {{ source('contracts', 'dq_contract_results') }} c
    join registry r
      on r.origin = 'CONTRACT'
     and split_part(split_part(r.contract_ref, '@', 1), '|', 1) = c.source_system
     and split_part(split_part(r.contract_ref, '@', 1), '|', 2) = coalesce(c.component, '')
     and split_part(split_part(r.contract_ref, '#', 2), ':', 1) = c.rule
     and replace(substr(r.contract_ref, instr(r.contract_ref, ':') + 1), ' ', '') = replace(c.column_name, ' ', '')

),

unioned as (

    select rule_id, source_system, org_id, season_year, n_evaluated, n_pass, n_pass::double / nullif(n_evaluated, 0) as pass_rate from measured
    union all
    select rule_id, source_system, org_id, season_year, n_evaluated, n_pass, pass_rate_override from contract

),

expanded as (

    select
        u.*, r.dimension, r.origin, r.severity, r.grain as rule_grain, r.owner_role,
        unnest(case when coalesce(r.purposes, '') = '' then [cast(null as varchar)] else string_split(r.purposes, '|') end) as purpose,
        r.threshold_count, r.threshold_segment, r.threshold_geo, r.threshold_retain, r.threshold_activate
    from unioned u join registry r using (rule_id)

)

select
    rule_id,
    dimension,
    origin,
    case when org_id is not null then 'ORG_SEASON' else 'SOURCE_SEASON' end                                  as grain,
    source_system,
    org_id,
    season_year,
    purpose,
    n_evaluated,
    n_pass,
    round(pass_rate, 6)                                                                                       as observed_value,
    {{ dq_threshold_for('purpose') }}                                                                         as threshold,
    case when n_evaluated = 0 or pass_rate is null or ({{ dq_threshold_for('purpose') }}) is null then null
         else pass_rate >= ({{ dq_threshold_for('purpose') }}) end                                            as pass,
    severity,
    owner_role,
    current_timestamp                                                                                         as run_at
from expanded
