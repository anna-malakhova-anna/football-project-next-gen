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

{{ dq_expanded_cte() }}

{{ dq_results_select() }}
