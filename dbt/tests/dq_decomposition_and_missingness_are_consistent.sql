{{ config(tags=['phase5']) }}
-- mart_uncertainty_decomposition: low <= point <= high within every component; exactly the three components per year; the intervals are on the participant scale and bracket the reported point
-- (identity, DQ) or lie above it (coverage); NO ROW OR COLUMN SUMS COMPONENTS (the components are not independent and coverage is an estimate, not a bound: ADR-015).
-- mart_missingness_bias: bound_low <= value_known_only <= bound_high; bounds inside [0, 1]; the known-only value is never below the Phase 3 value for girls' share (unknowns leave the denominator).
select participation_year::varchar as key, component as detail, 'low > point or point > high' as problem from {{ ref('mart_uncertainty_decomposition') }} where low > point + 1e-9 or point > high + 1e-9
union all
select participation_year::varchar, 'components', 'not exactly IDENTITY, DQ_EXCLUSIONS and COVERAGE'
from {{ ref('mart_uncertainty_decomposition') }} group by participation_year having count(*) <> 3 or count(distinct component) <> 3
union all
select participation_year::varchar, component, 'interval does not bracket the reported point' from {{ ref('mart_uncertainty_decomposition') }}
where (component in ('IDENTITY', 'DQ_EXCLUSIONS') and (interval_low > reported_point + 1e-9 or interval_high < reported_point - 1e-9)) or (component = 'COVERAGE' and interval_low < reported_point)
union all
select 'schema', column_name, 'a total or sum column exists' from information_schema.columns
where table_schema = '{{ ref("mart_uncertainty_decomposition").schema }}' and table_name = 'mart_uncertainty_decomposition' and regexp_matches(lower(column_name), 'total|overall|combined|sum')
union all
select participation_year::varchar || '|' || kpi, segment_value, 'known-only outside the bounds' from {{ ref('mart_missingness_bias') }}
where value_known_only is not null and (value_known_only < bound_low - 1e-9 or value_known_only > bound_high + 1e-9)
union all
select participation_year::varchar || '|' || kpi, segment_value, 'bound outside 0 to 1 or inverted' from {{ ref('mart_missingness_bias') }}
where bound_low is not null and (bound_low < 0 or bound_high > 1 or bound_low > bound_high)
union all
select participation_year::varchar, segment_value, 'known-only below the Phase 3 girls share' from {{ ref('mart_missingness_bias') }}
where kpi = 'girls_share_of_youth' and value_known_only < value_phase3 - 1e-9
union all
select participation_year::varchar || '|' || kpi, factor, 'p-value outside 0 to 1' from {{ ref('mart_missingness_tests') }} where p_value < 0 or p_value > 1
