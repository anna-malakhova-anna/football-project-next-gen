{#-
  age_at_cutoff(dob, season_year, cutoff_month_day=none)
  Completed years of age on the project cutoff date of the season year (ADR-002). Default cutoff is
  December 31 (var age_cutoff_month_day = '12-31'), which is a project convention, not any league's rule.
  Birthday-aware by comparing (month, day) rather than using date_diff('year'), which only counts
  calendar-year boundaries.

  age_at_cutoff_from_birth_year(birth_year, season_year)
  For sources that only give birth year (CA). Exact under the default Dec 31 cutoff; for any earlier
  cutoff it is the upper bound, because the birthday is unknown. See ADR-002.
-#}
{% macro age_at_cutoff(dob, season_year, cutoff_month_day=none) -%}
{%- set md = var('age_cutoff_month_day', '12-31') if cutoff_month_day is none else cutoff_month_day -%}
{%- set cutoff = md.split('-')[0] | int * 100 + md.split('-')[1] | int -%}
cast({{ season_year }} - extract(year from {{ dob }})
    - case when extract(month from {{ dob }}) * 100 + extract(day from {{ dob }}) > {{ cutoff }} then 1 else 0 end
    as integer)
{%- endmacro %}

{% macro age_at_cutoff_from_birth_year(birth_year, season_year) -%}
cast({{ season_year }} - {{ birth_year }} as integer)
{%- endmacro %}
