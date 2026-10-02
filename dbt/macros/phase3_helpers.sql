{#-
  privacy_param(name, type)  scalar subquery reading one value from the privacy_params seed (single source of truth)
  age_band(age)              the project's age bands; NULL age -> UNKNOWN (never imputed)
  first_observed_year()      the left-censored year, from the observation_window seed (config seasons.first_observed_year)
  term_order(term)           recency order of terms inside a participation year: SPRING 1, ANNUAL 2, FALL 3.
                             "Most recent registration in a year" needs an order that works for every source, and
                             INTL has no registration time. A US spring followed by a Canadian annual season, or a
                             Canadian season followed by US fall, are both ordered correctly.
-#}
{% macro privacy_param(name, type='integer') -%}
(select cast(value as {{ type }}) from {{ ref('privacy_params') }} where param = '{{ name }}')
{%- endmacro %}

{% macro first_observed_year() -%}
(select first_observed_year from {{ ref('observation_window') }})
{%- endmacro %}

{% macro age_band(age) -%}
case
    when {{ age }} is null then 'UNKNOWN'
    when {{ age }} <= 7 then '0-7'
    when {{ age }} <= 9 then '8-9'
    when {{ age }} <= 11 then '10-11'
    when {{ age }} <= 13 then '12-13'
    when {{ age }} <= 17 then '14-17'
    when {{ age }} <= 29 then '18-29'
    when {{ age }} <= 44 then '30-44'
    else '45+'
end
{%- endmacro %}

{% macro term_order(term) -%}
case {{ term }} when 'SPRING' then 1 when 'ANNUAL' then 2 when 'FALL' then 3 end
{%- endmacro %}
