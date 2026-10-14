{#-
  Minimization treatments (Phase 5 spec 7). The dbt var `minimization_variant` (default V0_FULL) names a row of the seed minimization_variants; the treatments of that row are applied to the
  matcher's input in idr_input_records, so the whole Phase 2 chain runs on coarsened data without a code fork. min_setting(column) -> the seed's value for the active variant
  (FULL / KEEP / CLEAR defaults while parsing, or when the seed is absent). Nothing here reads ground truth.
  DuckDB-specific: date_trunc on a date (returns a date), md5 (Snowflake has MD5 too).
-#}
{% macro min_setting(column) -%}
{%- set defaults = {'dob_treatment': 'FULL', 'postal_treatment': 'FULL', 'phone_treatment': 'KEEP', 'email_treatment': 'CLEAR'} -%}
{%- if not execute -%}{{ defaults[column] }}
{%- else -%}
{%- set q = run_query("select " ~ column ~ " from " ~ ref('minimization_variants') ~ " where variant_id = '" ~ var('minimization_variant', 'V0_FULL') ~ "'") -%}
{%- if q.rows | length != 1 -%}{{ exceptions.raise_compiler_error("minimization_variant '" ~ var('minimization_variant', 'V0_FULL') ~ "' is not a row of minimization_variants") }}{%- endif -%}
{{ q.rows[0][0] }}
{%- endif -%}
{%- endmacro %}

{% macro min_dob(dob, precision) -%}
{%- set t = min_setting('dob_treatment') | trim -%}
{%- if t == 'FULL' -%}{{ dob }}
{%- elif t == 'YEAR_MONTH' -%}case when {{ precision }} = 'DAY' then cast(date_trunc('month', {{ dob }}) as date) else {{ dob }} end
{%- else -%}cast(null as date)
{%- endif -%}
{%- endmacro %}

{% macro min_dob_precision(precision, birth_year) -%}
{%- if (min_setting('dob_treatment') | trim) == 'YEAR' -%}case when {{ birth_year }} is not null then 'YEAR' end
{%- else -%}{{ precision }}
{%- endif -%}
{%- endmacro %}

{% macro min_postal(postal) -%}
{%- if (min_setting('postal_treatment') | trim) == 'ZIP3' -%}left({{ postal }}, 3){%- else -%}{{ postal }}{%- endif -%}
{%- endmacro %}

{% macro min_phone(phone) -%}
{%- if (min_setting('phone_treatment') | trim) == 'DROP' -%}cast(null as varchar){%- else -%}{{ phone }}{%- endif -%}
{%- endmacro %}

{% macro min_email(email) -%}
{%- if (min_setting('email_treatment') | trim) == 'HASH' -%}md5({{ email }}){%- else -%}{{ email }}{%- endif -%}
{%- endmacro %}
