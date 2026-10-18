{#-
  store_run_results(results): the on-run-end hook (Phase 6). Appends one row per executed node of every dbt command to phase6_ops.ops_dbt_run_results (invocation, time, command, node, status, execution time),
  so product health can read the pipeline's pass rate and run time from the warehouse instead of from a file that the next command overwrites. Keeps the last 30 invocations.
  Portable: on another warehouse only the DDL and the timestamp function change.
-#}
{% macro store_run_results(results) -%}
{%- if execute and results | length > 0 and flags.WHICH in ['run', 'test', 'build', 'seed', 'snapshot'] -%}
    {%- do run_query("create schema if not exists phase6_ops") -%}
    {%- do run_query("create table if not exists phase6_ops.ops_dbt_run_results (invocation_id varchar, run_at timestamp, command varchar, unique_id varchar, resource_type varchar, name varchar, status varchar, execution_time double)") -%}
    {%- set vals = [] -%}
    {%- for r in results -%}
        {%- do vals.append("('" ~ invocation_id ~ "', current_timestamp::timestamp, '" ~ flags.WHICH ~ "', '" ~ (r.node.unique_id | replace("'", "''")) ~ "', '" ~ r.node.resource_type ~ "', '" ~ (r.node.name | replace("'", "''")) ~ "', '" ~ (r.status | string) ~ "', " ~ (r.execution_time | float) ~ ")") -%}
    {%- endfor -%}
    {%- do run_query("insert into phase6_ops.ops_dbt_run_results values " ~ vals | join(', ')) -%}
    {%- do run_query("delete from phase6_ops.ops_dbt_run_results where invocation_id not in (select invocation_id from (select invocation_id, max(run_at) as t from phase6_ops.ops_dbt_run_results group by 1 order by 2 desc limit 30))") -%}
{%- endif -%}
{%- endmacro %}
