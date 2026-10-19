-- depends_on: {{ ref('dq_rule_registry') }}
-- depends_on: {{ ref('dq_record_resolved') }}
-- DP2 AGGREGATE PORT. The record-level rules that need the resolved person (post-resolution uniqueness, agreement across a person's records), evaluated over dq_record_resolved and aggregated to
-- (source, organization, season) exactly as DP1's dq_rule_measures does for every other rule: rule_id, source_system, org_id, season_year, n_evaluated, n_pass. Counts only.
-- DP4's dq_rule_results unions the two.
{{ dq_record_rule_results('RECORD', 'dq_record_resolved', 'source_system, org_id, season_year', 'identity') }}
