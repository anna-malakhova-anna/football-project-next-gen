{# Methodology versions are 'major.minor'. A KPI exists from `introduced_in` onwards (metric_catalog); comparing as numbers keeps '1.10' > '1.9'. #}
{% macro version_num(v) -%}
(cast(split_part({{ v }}, '.', 1) as integer) * 1000 + cast(split_part({{ v }}, '.', 2) as integer))
{%- endmacro %}
