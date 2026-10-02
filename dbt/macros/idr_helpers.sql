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
