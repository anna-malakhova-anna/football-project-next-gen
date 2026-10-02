{# Methodology versions are 'major.minor'. A KPI exists from `introduced_in` onwards (metric_catalog); comparing as numbers keeps '1.10' > '1.9'. #}
{% macro version_num(v) -%}
(cast(split_part({{ v }}, '.', 1) as integer) * 1000 + cast(split_part({{ v }}, '.', 2) as integer))
{%- endmacro %}

{# The market lookup key for a postal code: the ZIP3 of a US ZIP, or the FSA of a Canadian postal code, whichever the FORMAT says (a mover registered in one country may carry the
   other country's postal code). NULL for anything else, including international returns, which have no postal code and map to their country's market. #}
{% macro market_prefix(postal) -%}
case
    when regexp_matches(coalesce({{ postal }}, ''), '^\s*\d{5}') then left(regexp_replace({{ postal }}, '\D', '', 'g'), 3)
    when regexp_matches(upper(coalesce({{ postal }}, '')), '^\s*[A-Z]\d[A-Z]') then upper(left(regexp_replace({{ postal }}, '\s', '', 'g'), 3))
end
{%- endmacro %}
