-- depends_on: {{ ref('dq_rule_registry') }}
-- depends_on: {{ ref('dq_rule_measures') }}
-- depends_on: {{ ref('dq_identity_rule_results') }}
-- DP4 (assembled from DP1's dq_rule_measures and DP2's dq_identity_rule_results, the two halves of the registry). The long-form fact everything in the data quality layer reads: one row per rule x grain key x purpose.
--   RECORD rules (origin PHASE1, PHASE5)  are evaluated over dq_record_base and aggregated to (source, organization, season); an organization-less stream (fan, school) is keyed by source and season
--   ORG_SEASON rules                      are evaluated over dq_org_season_base (dark organizations included)
--   STANDARD rules                        are the data standard's field conformance (dq_standard_conformance, from validate_against_standard), INFO, never scored
--   CONTRACT rules                        are the contract's own measurement (quality.dq_contract_results, written by scripts/validate_contracts.py), read here, not re-measured:
--                                         the contract's maximum violation rate becomes a minimum pass rate; the grain is the source over all seasons
-- observed_value is a pass rate in [0, 1]. threshold is the registry's minimum pass rate for that purpose; `pass` is NULL for a rule with no threshold for any purpose (INFO) and
-- when nothing was evaluable. A rule listing several purposes yields one row per purpose, so a purpose is judged against its own bar.
with registry as (select * from {{ ref('dq_rule_registry') }}),

unioned as (

    select rule_id, source_system, org_id, season_year, n_evaluated, n_pass, pass_rate from {{ ref('dq_rule_measures') }}
    union all
    select rule_id, source_system, org_id, season_year, n_evaluated, n_pass, n_pass::double / nullif(n_evaluated, 0) from {{ ref('dq_identity_rule_results') }}

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
