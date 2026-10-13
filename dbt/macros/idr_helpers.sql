{#-
  idr_plausible_max_cluster_size()
  The largest cluster that is plausible for ONE person, computed from the observation window (not a constant):
      observed years x 2 US terms x 2 concurrent leagues + 2 near-duplicate registrations
  A 3-year window gave 14; five years give 22. A bigger cluster fails the build (tests/idr_clusters_within_plausible_size.sql)
  and is flagged OVERSIZE by idr_cluster_integrity. Found hardcoded at 14 when the window was extended (ADR-008).
-#}
{% macro idr_plausible_max_cluster_size() -%}
((select last_observed_year - first_observed_year + 1 from {{ ref('observation_window') }}) * 2 * 2 + 2)
{%- endmacro %}

{#-
  idr_rules_rule_id()
  The ordered rules baseline (R1 to R6) as a CASE over the pair feature levels, shared by idr_pair_scores_rules and the Phase 5 resolution
  (p5_pair_scores), so both apply identical rules. Needs the columns of idr_pair_features in scope.
-#}
{% macro idr_rules_rule_id() -%}
case
    when first_name_level in ('EXACT', 'NICKNAME') and last_name_level = 'EXACT' and dob_level = 'EXACT'
        then 'R1'
    when first_name_level in ('EXACT', 'NICKNAME') and last_name_level = 'EXACT' and dob_level = 'SAME_YEAR_ONLY'
         and (email_level = 'EXACT' or phone_level = 'EXACT')
        then 'R2'
    when first_name_level = 'FUZZY_HIGH' and last_name_level = 'EXACT' and dob_level in ('EXACT', 'DAY_MONTH_SWAPPED')
        then 'R3'
    when email_level = 'EXACT' and dob_level = 'EXACT' and first_name_level = 'DIFFERENT'
        then 'R4'
    when last_name_level = 'EXACT' and dob_level = 'YEAR_OFF_BY_ONE' and first_name_level = 'EXACT'
         and (email_level = 'EXACT' or phone_level = 'EXACT')
        then 'R5'
    else 'R6'
end
{%- endmacro %}
