{#-
  The rule registry (seed dq_rule_registry) is the one place a data quality rule is defined. These macros turn its rows into queries.
  Every call reads the registry with run_query at compile time (the seed must be loaded first: dbt seed / dbt build) and callers add `-- depends_on:` lines for the seeds they use.

  dq_record_rule_results()   one SELECT per RECORD-grain rule over dq_record_base: rule_id, source_system, org_id, season_year, n_evaluated, n_pass
                             (check_sql TRUE passes, FALSE fails, NULL is not applicable)
  dq_org_rule_results()      the same for ORG_SEASON-grain rules over dq_org_season_base
  dq_fitness_columns()       per purpose: the list of failing rules a record has (rules of severity ERROR or WARN that list the purpose), as failing_rules_<PURPOSE>
  dq_threshold_for(p)        the registry threshold column for a purpose name
-#}
{% macro dq_threshold_for(purpose_col) -%}
case {{ purpose_col }} when 'COUNT' then threshold_count when 'SEGMENT' then threshold_segment when 'GEO' then threshold_geo
                       when 'RETAIN' then threshold_retain when 'ACTIVATE' then threshold_activate end
{%- endmacro %}

{% macro dq_record_rule_results(grain='RECORD', base='dq_record_base', keys='source_system, org_id, season_year') -%}
{%- if execute -%}
{%- set rules = run_query("select rule_id, check_sql from " ~ ref('dq_rule_registry') ~ " where grain = '" ~ grain ~ "' and nullif(trim(check_sql), '') is not null order by rule_id") -%}
{%- for r in rules.rows %}
select '{{ r[0] }}' as rule_id, {{ keys }},
       count(*) filter (where ({{ r[1] }}) is not null) as n_evaluated,
       count(*) filter (where ({{ r[1] }})) as n_pass
from {{ ref(base) }}
group by {{ keys }}
{% if not loop.last %}union all{% endif %}
{%- endfor %}
{%- else -%}
select cast(null as varchar) as rule_id, cast(null as varchar) as source_system, cast(null as varchar) as org_id, cast(null as integer) as season_year, 0 as n_evaluated, 0 as n_pass where false
{%- endif -%}
{%- endmacro %}

{% macro dq_fitness_columns() -%}
{%- if execute -%}
{%- for purpose in ['COUNT', 'SEGMENT', 'GEO', 'RETAIN', 'ACTIVATE'] -%}
{%- set rules = run_query("select rule_id, check_sql from " ~ ref('dq_rule_registry') ~ " where grain = 'RECORD' and nullif(trim(check_sql), '') is not null and severity in ('ERROR', 'WARN') and list_contains(string_split(purposes, '|'), '" ~ purpose ~ "') order by rule_id") %}
    list_filter([
        {%- for r in rules.rows %}
        case when not coalesce(({{ r[1] }}), true) then '{{ r[0] }}' end{{ ',' if not loop.last }}
        {%- endfor %}
    ], _f -> _f is not null) as failing_rules_{{ purpose | lower }}{{ ',' if not loop.last }}
{%- endfor %}
{%- else -%}
    cast([] as varchar[]) as failing_rules_count
{%- endif -%}
{%- endmacro %}

{#- dq_grade(score_expr) -> the grade for a 0-100 score: the band with the highest min_score at or below it (seed dq_grade_bands). -#}
{% macro dq_grade(score_expr) -%}
(select b.grade from {{ ref('dq_grade_bands') }} b where b.min_score <= ({{ score_expr }}) order by b.min_score desc limit 1)
{%- endmacro %}

{#- dq_wilson(p, n, z, side) -> the lower or upper bound of the Wilson score interval for a proportion p (0-1) observed on n trials. NULL when n is 0. -#}
{% macro dq_wilson(p, n, side='low', z=1.96) -%}
case when ({{ n }}) > 0 then
    (({{ p }}) + {{ z }} * {{ z }} / (2.0 * ({{ n }}))
        {{ '-' if side == 'low' else '+' }} {{ z }} * sqrt((({{ p }}) * (1 - ({{ p }})) + {{ z }} * {{ z }} / (4.0 * ({{ n }}))) / ({{ n }})))
    / (1 + {{ z }} * {{ z }} / ({{ n }}))
end
{%- endmacro %}
