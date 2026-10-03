{{ config(tags=['phase3']) }}
-- Every metric column in a share_exec model is defined in metric_catalog. Dimension and label columns are listed here;
-- anything else must be a catalogued metric. Returns uncatalogued columns.
select c.table_name, c.column_name
from information_schema.columns c
left join {{ ref('metric_catalog') }} m on m.metric_id = c.column_name
where c.table_schema = 'share_exec'
  and c.column_name not in ('participation_year', 'country_code', 'age_band', 'sex', 'status', 'suppressed', 'estimator', 'caveat', 'segment_type', 'segment_value', 'years_since_entry', 'entry_year', 'cohort_year', 'segment', 'fan_status', 'methodology_version', 'fan_group', 'month', 'household_group', 'market_id', 'market_name', 'quadrant', 'is_team_market', 'launch_year', 'household_population', 'markets_in_row', 'horizon_months', 'currency_label')
  and m.metric_id is null
