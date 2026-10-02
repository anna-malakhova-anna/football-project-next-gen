{#-
  normalize_name(col)  -> display form
    trim, collapse internal whitespace, blank -> NULL. Title-cased only when the value is entirely
    upper or entirely lower case (ALL-CAPS records, e.g. TREMBLAY -> Tremblay), so deliberate mixed
    case such as McDaniel or DeLeon is preserved. Capitalizes after spaces, hyphens and apostrophes.
  name_key(col)        -> match form: normalize_name, accent-stripped, lowercase.

  DuckDB-specific: lambda list functions (list_transform, string_split, array_to_string) and
  strip_accents. Snowflake equivalents: INITCAP and TRANSLATE/COLLATE 'en-ai'. See ADR-001.
-#}
{% macro _clean_ws(col) -%}
nullif(regexp_replace(trim({{ col }}), '\s+', ' ', 'g'), '')
{%- endmacro %}

{% macro _title_case(expr) -%}
array_to_string(list_transform(string_split({{ expr }}, ' '),
    _w -> array_to_string(list_transform(string_split(_w, '-'),
        _h -> array_to_string(list_transform(string_split(_h, ''''),
            _a -> upper(_a[1]) || _a[2:]), '''')), '-')), ' ')
{%- endmacro %}

{% macro normalize_name(col) -%}
case
    when {{ _clean_ws(col) }} is null then null
    when {{ _clean_ws(col) }} = upper({{ _clean_ws(col) }}) or {{ _clean_ws(col) }} = lower({{ _clean_ws(col) }})
        then {{ _title_case('lower(' ~ _clean_ws(col) ~ ')') }}
    else {{ _clean_ws(col) }}
end
{%- endmacro %}

{% macro name_key(col) -%}
lower(strip_accents({{ normalize_name(col) }}))
{%- endmacro %}
