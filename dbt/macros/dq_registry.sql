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

{#-
  validate_against_standard(relation, keys)
  Validates ANY relation that carries the data standard's columns (seed data_standard_fields) against the standard. For every standard field, per grouping key, it counts the rows
  (n_rows), the rows where the field is missing (NULL or blank) and the rows where it is present but invalid (fails the field's regex pattern or allowed values). `keys` lists the
  grouping columns of the relation (they are returned as they are). A field the relation lacks entirely is reported as 100% missing. Use it on a new feed before onboarding it:
  map its columns to the standard names in a model, then select {{ validate_against_standard(ref('my_feed_in_standard_shape'), ['grp_source_system']) }}.
  Reads the standard with run_query at compile time (the seed must be loaded first; callers add a depends_on line for it).
-#}
{% macro validate_against_standard(relation, keys=['grp_source_system', 'grp_org_id', 'grp_season_year']) -%}
{%- if execute -%}
{%- set fields = run_query("select field_name, requirement, pattern, allowed_values from " ~ ref('data_standard_fields') ~ " order by ordinal") -%}
{%- set cols = adapter.get_columns_in_relation(relation) | map(attribute='name') | map('lower') | list -%}
{%- for f in fields.rows %}
{% set name = f[0] %}{% set present = name in cols %}
select {{ keys | join(', ') }}, '{{ name }}' as field_name, '{{ f[1] }}' as requirement, count(*) as n_rows,
       {% if present -%}
       count(*) filter (where nullif(trim(cast({{ name }} as varchar)), '') is null) as n_missing,
       count(*) filter (where nullif(trim(cast({{ name }} as varchar)), '') is not null and not (
           {%- if f[3] %} cast({{ name }} as varchar) in ({% for v in f[3].split('|') %}'{{ v }}'{% if not loop.last %}, {% endif %}{% endfor %})
           {%- elif f[2] %} regexp_matches(cast({{ name }} as varchar), '{{ f[2] | replace("'", "''") }}')
           {%- else %} true {%- endif %})) as n_invalid
       {%- else -%}
       count(*) as n_missing, 0 as n_invalid
       {%- endif %}
from {{ relation }}
group by {{ keys | join(', ') }}
{% if not loop.last %}union all
{% endif %}
{%- endfor %}
{%- else -%}
select {% for k in keys %}cast(null as varchar) as {{ k }}, {% endfor %}cast(null as varchar) as field_name, cast(null as varchar) as requirement, 0 as n_rows, 0 as n_missing, 0 as n_invalid where false
{%- endif -%}
{%- endmacro %}

{#-
  dq_impact_person_rows()
  For every record-level rule that can judge a record (severity ERROR or WARN), one SELECT over dq_record_base: per person and season, how many of the person's records fail the rule and
  whether ALL of the records the rule could evaluate fail it (all_fail). A person whose every evaluable record fails a rule is the one a rule can cost a count, a segment or a place.
  Only persons with at least one failing record are returned.

  dq_impact_merge_rows()
  For every such rule, the PROBABLE identity links that join two different participants (the gap between the point and the low participant count) where either record fails the rule: the
  uncertain merges the rule is entangled in. An upper-bound attribution (a merge can be touched by several rules).
-#}
{% macro dq_impact_person_rows() -%}
{%- if execute -%}
{%- set rules = run_query("select rule_id, check_sql from " ~ ref('dq_rule_registry') ~ " where grain = 'RECORD' and nullif(trim(check_sql), '') is not null and severity in ('ERROR', 'WARN') order by rule_id") -%}
{%- for r in rules.rows %}
select '{{ r[0] }}' as rule_id, person_id, season_year, any_value(source_system) as source_system,
       count(*) filter (where not coalesce(({{ r[1] }}), true)) as records_failing,
       bool_and(not ({{ r[1] }})) filter (where ({{ r[1] }}) is not null) as all_fail
from {{ ref('dq_record_base') }}
where person_id is not null and season_year between {{ first_observed_year() }} and (select last_observed_year from {{ ref('observation_window') }})
group by person_id, season_year
having count(*) filter (where not coalesce(({{ r[1] }}), true)) > 0
{% if not loop.last %}union all{% endif %}
{%- endfor %}
{%- else -%}
select cast(null as varchar) as rule_id, cast(null as varchar) as person_id, cast(null as integer) as season_year, cast(null as varchar) as source_system, 0 as records_failing, cast(null as boolean) as all_fail where false
{%- endif -%}
{%- endmacro %}

{% macro dq_impact_merge_rows() -%}
{%- if execute -%}
{%- set rules = run_query("select rule_id, check_sql from " ~ ref('dq_rule_registry') ~ " where grain = 'RECORD' and nullif(trim(check_sql), '') is not null and severity in ('ERROR', 'WARN') order by rule_id") -%}
{%- for r in rules.rows %}
select '{{ r[0] }}' as rule_id, ba.season_year, count(*) as merges_touched
from merges m
join {{ ref('dq_record_base') }} ba on ba.record_key = m.record_a
where m.record_a in (select record_key from {{ ref('dq_record_base') }} where not coalesce(({{ r[1] }}), true))
   or m.record_b in (select record_key from {{ ref('dq_record_base') }} where not coalesce(({{ r[1] }}), true))
group by ba.season_year
{% if not loop.last %}union all{% endif %}
{%- endfor %}
{%- else -%}
select cast(null as varchar) as rule_id, cast(null as integer) as season_year, 0 as merges_touched where false
{%- endif -%}
{%- endmacro %}
