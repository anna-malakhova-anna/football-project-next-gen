{#- Use the custom schema as-is (staging, intermediate, ...) instead of dbt's default <target>_<custom>.
    Snowflake-portable: on Snowflake this just names schemas in the target database. -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
