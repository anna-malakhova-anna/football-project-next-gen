{{ config(tags=['phase3']) }}
-- Every metric column in a share_exec model is defined in metric_catalog. Dimension and label columns are listed here;
-- anything else must be a catalogued metric. Returns uncatalogued columns.
select c.table_name, c.column_name
from information_schema.columns c
left join {{ ref('metric_catalog') }} m on m.metric_id = c.column_name
where c.table_schema = 'share_exec'
  and c.column_name not in ('participation_year', 'country_code', 'age_band', 'sex', 'status', 'suppressed', 'estimator', 'caveat', 'segment_type', 'segment_value', 'years_since_entry', 'entry_year', 'cohort_year', 'segment', 'fan_status', 'methodology_version', 'fan_group', 'month', 'household_group', 'market_id', 'market_name', 'quadrant', 'is_team_market', 'launch_year', 'household_population', 'markets_in_row', 'horizon_months', 'currency_label', 'year', 'months_since_origin', 'uplift_status_group', 'uplift_outcome', 'uplift_outcome_kind', 'consent_cut', 'consent_dimension_value', 'consent_channel',
    'gate_id', 'product_id', 'kind', 'definition', 'plain_name', 'comparison', 'target', 'unit', 'baseline_2025', 'gate_for', 'source_model', 'source_field', 'current_value', 'bar_fill_pct', 'target_marker_pct', 'status_text', 'value_text', 'n_gates', 'n_met', 'blocking_gate_plain',
    'country_name', 'region', 'legal_regime_id', 'output_port', 'status_on_page', 'season_year', 'status_reason', 'counting_grade', 'participation_direction', 'proxy_direction',
    'proxy_agreement', 'comparable_basis', 'comparable_markets', 'single_comparable', 'scenario_direction', 'scenario_label', 'limiting_dimension', 'regime_name', 'regime_verification', 'lane', 'action', 'gate_kind', 'target_value', 'gate_status', 'score_status', 'plan_status', 'rationale', 'stage_order', 'stage', 'state', 'artifact', 'what_happened', 'market_status_now', 'counting_grade_now', 'chart_id', 'lens', 'field', 'value_display', 'value_raw')
  and m.metric_id is null
