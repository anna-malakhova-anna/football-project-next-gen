{#- participant_id(min_source_record_id): 'P-' plus the first 12 hex characters of md5 of the smallest source_record_id in
    the cluster (ADR-004). Deterministic for the same data; changes when clusters merge or split. Ground-truth ids are
    'P-' plus 6 digits, so the two are visually distinct. -#}
{% macro participant_id(min_source_record_id) -%}
'P-' || upper(left(md5({{ min_source_record_id }}), 12))
{%- endmacro %}
