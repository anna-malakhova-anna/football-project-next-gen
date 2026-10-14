{#- p5_param(name) -> the value of a p5_params row as a SQL literal (numbers stay numbers). Read with run_query at compile time; callers add `-- depends_on: {{ ref('p5_params') }}`. -#}
{% macro p5_param(name) -%}
{%- if execute -%}
{%- set r = run_query("select value from " ~ ref('p5_params') ~ " where param = '" ~ name ~ "'") -%}
{{- r.rows[0][0] -}}
{%- else -%}0{%- endif -%}
{%- endmacro %}
