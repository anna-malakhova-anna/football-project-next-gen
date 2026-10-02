{#- source_pair(a_system, b_system) -> 'US-US', 'US-CA', 'CA-CA', 'US-INTL', 'CA-INTL', 'INTL-INTL'.
    Always in the order US, CA, INTL so the same pair of systems has one name, whichever record is "a". -#}
{% macro source_pair(a_system, b_system) -%}
case when {{ source_rank(a_system) }} <= {{ source_rank(b_system) }}
     then {{ source_short(a_system) }} || '-' || {{ source_short(b_system) }}
     else {{ source_short(b_system) }} || '-' || {{ source_short(a_system) }} end
{%- endmacro %}

{% macro source_rank(system) -%}
case {{ system }} when 'US_LEAGUE' then 1 when 'CA_CLUB' then 2 else 3 end
{%- endmacro %}

{% macro source_short(system) -%}
case {{ system }} when 'US_LEAGUE' then 'US' when 'CA_CLUB' then 'CA' else 'INTL' end
{%- endmacro %}
