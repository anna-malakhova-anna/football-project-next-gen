{#-
  Small, source-agnostic cleaners used by staging. All return NULL instead of guessing.

  blank_to_null(col)           trim; '' -> NULL (raw empty CSV fields are '' by design)
  normalize_phone(col, cc)     digits-only E.164-ish: '+' || country code || 10 digits. Accepts 10 digits
                               or country code + 10 digits (NANP style). Anything else -> NULL.
  to_consent_boolean(col)      Y/yes/true/1 -> TRUE, N/no/false/0 -> FALSE, anything else (incl. blank)
                               -> NULL. NULL means "not captured" and is NEVER coerced to FALSE.
  normalize_us_zip(col)        5 digits; restores a dropped leading zero (4 digits); ZIP+4 -> ZIP5; else NULL
  normalize_ca_postal(col)     'A1A 1A1' (uppercase, one space); else NULL
-#}
{% macro blank_to_null(col) -%}
nullif(trim({{ col }}), '')
{%- endmacro %}

{% macro normalize_phone(col, cc='1') -%}
{%- set d -%}regexp_replace(coalesce({{ col }}, ''), '\D', '', 'g'){%- endset -%}
case
    when {{ d }} = '' then null
    when length({{ d }}) = 10 then '+{{ cc }}' || {{ d }}
    when length({{ d }}) = {{ 10 + cc | length }} and left({{ d }}, {{ cc | length }}) = '{{ cc }}' then '+' || {{ d }}
    else null
end
{%- endmacro %}

{% macro to_consent_boolean(col) -%}
case lower(trim({{ col }}))
    when 'y' then true when 'yes' then true when 'true' then true when '1' then true
    when 'n' then false when 'no' then false when 'false' then false when '0' then false
    else null
end
{%- endmacro %}

{% macro normalize_us_zip(col) -%}
{%- set z -%}{{ blank_to_null(col) }}{%- endset -%}
case
    when regexp_matches({{ z }}, '^\d{5}$') then {{ z }}
    when regexp_matches({{ z }}, '^\d{4}$') then '0' || {{ z }}
    when regexp_matches({{ z }}, '^\d{5}-\d{4}$') then left({{ z }}, 5)
    else null
end
{%- endmacro %}

{% macro normalize_ca_postal(col) -%}
{%- set z -%}upper(regexp_replace(coalesce({{ col }}, ''), '\s', '', 'g')){%- endset -%}
case
    when regexp_matches({{ z }}, '^[A-Z]\d[A-Z]\d[A-Z]\d$') then substr({{ z }}, 1, 3) || ' ' || substr({{ z }}, 4, 3)
    else null
end
{%- endmacro %}
