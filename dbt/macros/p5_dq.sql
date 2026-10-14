{#-
  p5_rule_results(group_expr)
  Evaluates EVERY rule of the p5_dq_rules seed against p5_record_quality and returns one row per rule x group: how many records the rule could be evaluated on
  (check_sql is not NULL) and how many passed (check_sql is TRUE). The SQL is the seed's own text, so the rules table is the only place a check is defined.
  Rules are read with run_query at compile time, which needs the seed loaded first (dbt seed, or dbt build, runs it before the models).

  p5_score_columns(results)
  The score body shared by the league and the market scorecards: dimension scores (mean pass rate of the rules in the dimension), the overall score (mean of the
  dimension scores), and fitness for each purpose (every rule that has a threshold for the purpose meets it).
-#}
{% macro p5_rule_results(group_expr) -%}
{%- if execute -%}
{%- set rules = run_query("select rule_id, check_sql from " ~ ref('p5_dq_rules') ~ " order by rule_id") -%}
{%- for r in rules.rows %}
select '{{ r[0] }}' as rule_id, {{ group_expr }} as group_id,
       count(*) filter (where ({{ r[1] }}) is not null) as n_evaluated,
       count(*) filter (where ({{ r[1] }})) as n_pass
from {{ ref('p5_record_quality') }}
group by 1, 2
{% if not loop.last %}union all{% endif %}
{%- endfor %}
{%- else -%}
select cast(null as varchar) as rule_id, cast(null as varchar) as group_id, 0 as n_evaluated, 0 as n_pass where false
{%- endif -%}
{%- endmacro %}

{% macro p5_score_columns(results) -%}
with rated as (

    select
        r.group_id, r.rule_id, u.dimension, r.n_evaluated, r.n_pass,
        r.n_pass::double / nullif(r.n_evaluated, 0)                         as pass_rate,
        u.threshold_participation_reporting                                 as thr_reporting,
        u.threshold_club_activation                                         as thr_activation
    from {{ results }} r
    join {{ ref('p5_dq_rules') }} u using (rule_id)

),

dimension_scores as (

    select group_id, dimension, avg(pass_rate) as dimension_score
    from rated where pass_rate is not null
    group by 1, 2

),

scores as (

    select
        group_id,
        avg(dimension_score)                                                as overall_score,
        max(dimension_score) filter (where dimension = 'COMPLETENESS')      as completeness,
        max(dimension_score) filter (where dimension = 'VALIDITY')          as validity,
        max(dimension_score) filter (where dimension = 'UNIQUENESS')        as uniqueness,
        max(dimension_score) filter (where dimension = 'TIMELINESS')        as timeliness,
        max(dimension_score) filter (where dimension = 'CONSISTENCY')       as consistency,
        max(dimension_score) filter (where dimension = 'CONSENT_PROVENANCE') as consent_provenance
    from dimension_scores
    group by 1

),

fitness as (

    select
        group_id,
        count(*) filter (where thr_reporting is not null and pass_rate < thr_reporting)  as rules_failing_reporting,
        count(*) filter (where thr_activation is not null and pass_rate < thr_activation) as rules_failing_activation
    from rated
    group by 1

)

select
    s.group_id, s.overall_score, s.completeness, s.validity, s.uniqueness, s.timeliness, s.consistency, s.consent_provenance,
    f.rules_failing_reporting, f.rules_failing_activation,
    f.rules_failing_reporting = 0                                           as fit_for_participation_reporting,
    f.rules_failing_activation = 0                                          as fit_for_club_activation
from scores s join fitness f using (group_id)
{%- endmacro %}

{#-
  p5_standard_check(relation, feed_expr)
  Validates ANY relation that carries the standard's columns against the p5_data_standard seed. For every standard field, per feed (feed_expr, e.g. a column or a literal):
    n_rows, n_missing (NULL or blank), n_invalid (present but failing the field's regex pattern or allowed values), and the conformance share (present and valid).
  Use it on a new feed before onboarding: map the feed's columns to the standard names in a model, then select {{ p5_standard_check(ref('my_feed'), "'my_feed'") }}.
  A field that the relation lacks entirely is reported as 100% missing. Reads the standard with run_query at compile time (the seed must be loaded first).
-#}
{% macro p5_standard_check(relation, feed_expr) -%}
{%- if execute -%}
{%- set fields = run_query("select field_name, requirement, pattern, allowed_values from " ~ ref('p5_data_standard') ~ " order by ordinal") -%}
{%- set cols = adapter.get_columns_in_relation(relation) | map(attribute='name') | map('lower') | list -%}
{%- for f in fields.rows %}
{% set name = f[0] %}
{% set present = name in cols %}
select {{ feed_expr }} as feed, '{{ name }}' as field_name, '{{ f[1] }}' as requirement,
       count(*) as n_rows,
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
group by 1
{% if not loop.last %}union all
{% endif %}
{%- endfor %}
{%- else -%}
select cast(null as varchar) as feed, cast(null as varchar) as field_name, cast(null as varchar) as requirement, 0 as n_rows, 0 as n_missing, 0 as n_invalid where false
{%- endif -%}
{%- endmacro %}
