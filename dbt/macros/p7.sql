{#- p7_param(name, quote=false) -> the value of a p7_params row (ADR-025): a SQL literal (numbers stay numbers; quote=true wraps text in quotes). Read with run_query at compile time; callers add `-- depends_on: {{ ref('p7_params') }}`. -#}
{% macro p7_param(name, quote=false) -%}
{%- if execute -%}
{%- set r = run_query("select value from " ~ ref('p7_params') ~ " where param = '" ~ name ~ "'") -%}
{%- if quote -%}'{{ r.rows[0][0] | replace("'", "''") }}'{%- else -%}{{ r.rows[0][0] }}{%- endif -%}
{%- else -%}{%- if quote -%}''{%- else -%}0{%- endif -%}{%- endif -%}
{%- endmacro %}
