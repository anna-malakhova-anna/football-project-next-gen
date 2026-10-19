-- depends_on: {{ ref('dq_rule_registry') }}
-- depends_on: {{ ref('dq_record_base') }}
-- depends_on: {{ ref('dq_org_season_base') }}
-- depends_on: {{ ref('dq_standard_conformance') }}
-- DP1 AGGREGATE PORT. What DP1 can measure without a resolved person, one row per rule x grain key (before the registry's purposes expand it): rule_id, source_system, org_id, season_year,
-- n_evaluated, n_pass, pass_rate. Counts only.
--   RECORD rules that need no resolved person   evaluated over dq_record_base and aggregated to (source, organization, season); an organization-less stream (fan, school) is keyed by source and season
--   ORG_SEASON rules                            evaluated over dq_org_season_base (dark organizations included)
--   STANDARD rules                              the data standard's field conformance (dq_standard_conformance, from validate_against_standard), INFO, never scored
--   CONTRACT rules                              the contract's own measurement (quality.dq_contract_results, written by scripts/validate_contracts.py), read here, not re-measured
-- The rules that DO need the resolved person are DP2's (dq_identity_rule_results). DP4's dq_rule_results unions the two and applies the registry's purposes and thresholds.
with registry as (select * from {{ ref('dq_rule_registry') }}),

measured as (

    {{ dq_record_rule_results('RECORD', 'dq_record_base', 'source_system, org_id, season_year', 'plain') }}
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

standard as (

    -- conformance to the data standard: measured by validate_against_standard, one registry rule per field (origin STANDARD, INFO)
    select 'DQ-STD-' || upper(replace(field_name, '_', '-')) as rule_id, source_system, org_id, season_year,
           n_rows as n_evaluated, n_rows - n_missing - n_invalid as n_pass, conformance as pass_rate_override
    from {{ ref('dq_standard_conformance') }}

),

unioned as (

    select rule_id, source_system, org_id, season_year, n_evaluated, n_pass, n_pass::double / nullif(n_evaluated, 0) as pass_rate from measured
    union all
    select rule_id, source_system, org_id, season_year, n_evaluated, n_pass, pass_rate_override from contract
    union all
    select rule_id, source_system, org_id, season_year, n_evaluated, n_pass, pass_rate_override from standard

)

select * from unioned
