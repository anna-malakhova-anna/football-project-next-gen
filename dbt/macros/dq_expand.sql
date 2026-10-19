{#-
  dq_expanded_cte() / dq_results_select()
  The registry's purposes and thresholds applied to a relation of measured rules. The caller defines two CTEs, `registry` (select * from dq_rule_registry) and `unioned`
  (rule_id, source_system, org_id, season_year, n_evaluated, n_pass, pass_rate), then writes `, {{ dq_expanded_cte() }} {{ dq_results_select() }}`. One row per rule x grain key x purpose:
  observed_value (pass rate), threshold (the registry's minimum pass rate for the purpose) and `pass` (NULL when nothing was evaluable or the rule has no threshold). Shared by DP4's dq_rule_results
  (all rules) and DP1's dq_fix_list (the rules DP1 measures).
-#}
{% macro dq_expanded_cte() -%}
expanded as (

    select
        u.*, r.dimension, r.origin, r.severity, r.grain as rule_grain, r.owner_role,
        unnest(case when coalesce(r.purposes, '') = '' then [cast(null as varchar)] else string_split(r.purposes, '|') end) as purpose,
        r.threshold_count, r.threshold_segment, r.threshold_geo, r.threshold_retain, r.threshold_activate
    from unioned u join registry r using (rule_id)

)
{%- endmacro %}

{% macro dq_results_select() -%}
select
    rule_id,
    dimension,
    origin,
    case when org_id is not null then 'ORG_SEASON' else 'SOURCE_SEASON' end                                  as grain,
    source_system,
    org_id,
    season_year,
    purpose,
    n_evaluated,
    n_pass,
    round(pass_rate, 6)                                                                                       as observed_value,
    {{ dq_threshold_for('purpose') }}                                                                         as threshold,
    case when n_evaluated = 0 or pass_rate is null or ({{ dq_threshold_for('purpose') }}) is null then null
         else pass_rate >= ({{ dq_threshold_for('purpose') }}) end                                            as pass,
    severity,
    owner_role,
    current_timestamp                                                                                         as run_at
from expanded
{%- endmacro %}
