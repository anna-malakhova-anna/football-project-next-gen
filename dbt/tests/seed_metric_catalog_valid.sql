{{ config(tags=['phase3']) }}
-- Metric catalog hygiene: ids are snake_case, every north-star / growth / reach / depth / data-trust KPI group is
-- populated, and exactly one metric is the north star. Returns problems; passes when empty.
select 'bad_metric_id' as problem, metric_id as detail from {{ ref('metric_catalog') }}
where not regexp_matches(metric_id, '^[a-z][a-z0-9_]*$')
union all
select 'kpi_group_empty', g.kpi_group
from (select unnest(['north_star', 'growth', 'reach', 'depth', 'data_trust']) as kpi_group) g
left join {{ ref('metric_catalog') }} m on m.kpi_group = g.kpi_group
group by g.kpi_group having count(m.metric_id) = 0
union all
select 'north_star_count_not_1', cast(count(*) as varchar) from {{ ref('metric_catalog') }} where kpi_group = 'north_star'
having count(*) <> 1
union all
select 'ratio_metric_with_count_unit', metric_id from {{ ref('metric_catalog') }} where additivity = 'RATIO' and unit = 'count'
