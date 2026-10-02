{#-
  parse_flexible_date(col, fmt)         -> DATE or NULL
  parse_flexible_date_status(col, fmt)  -> why:
      BLANK | PARSED_ISO | PARSED_MDY | PARSED_DMY | EXCEL_SERIAL | AMBIGUOUS | UNPARSEABLE

  fmt says how to read slash dates and makes the macro source-aware:
      'MDY'  MM/DD/YYYY   (US league)
      'DMY'  DD/MM/YYYY   (international federations)
      'ANY'  decide from the value itself; if both readings are valid and differ (03/04/2015)
             the value is AMBIGUOUS and the date is NULL. The macro never guesses.
  Always accepted: ISO YYYY-MM-DD, and Excel date serials (5-6 digits, so a bare 4-digit year such
  as 2015 is NOT mistaken for a serial; this limits serials to 1927-05-18 and later).
  A value that matches a pattern but is not a real date (02/30/2015, 13/05/2015 under MDY) is
  UNPARSEABLE, not coerced.

  DuckDB-specific: try_strptime, regexp_matches, date + integer. Snowflake: TRY_TO_DATE with a format,
  REGEXP_LIKE, DATEADD(day, n, '1899-12-30'). See ADR-001.
-#}
{% macro parse_flexible_date_status(col, fmt) -%}
{%- if fmt not in ['MDY', 'DMY', 'ANY'] -%}{{ exceptions.raise_compiler_error("parse_flexible_date: fmt must be MDY, DMY or ANY, got " ~ fmt) }}{%- endif -%}
{%- set s -%}trim({{ col }}){%- endset -%}
{%- set mdy -%}try_strptime({{ s }}, '%m/%d/%Y'){%- endset -%}
{%- set dmy -%}try_strptime({{ s }}, '%d/%m/%Y'){%- endset -%}
case
    when nullif({{ s }}, '') is null then 'BLANK'
    when regexp_matches({{ s }}, '^\d{5,6}$') then 'EXCEL_SERIAL'
    when regexp_matches({{ s }}, '^\d{4}-\d{1,2}-\d{1,2}$') then
        case when try_strptime({{ s }}, '%Y-%m-%d') is not null then 'PARSED_ISO' else 'UNPARSEABLE' end
    when regexp_matches({{ s }}, '^\d{1,2}/\d{1,2}/\d{4}$') then
        {%- if fmt == 'MDY' %}
        case when {{ mdy }} is not null then 'PARSED_MDY' else 'UNPARSEABLE' end
        {%- elif fmt == 'DMY' %}
        case when {{ dmy }} is not null then 'PARSED_DMY' else 'UNPARSEABLE' end
        {%- else %}
        case
            when {{ mdy }} is null and {{ dmy }} is null then 'UNPARSEABLE'
            when {{ dmy }} is null then 'PARSED_MDY'
            when {{ mdy }} is null then 'PARSED_DMY'
            when {{ mdy }} = {{ dmy }} then 'PARSED_MDY'   -- e.g. 05/05/2015: both readings agree
            else 'AMBIGUOUS'
        end
        {%- endif %}
    else 'UNPARSEABLE'
end
{%- endmacro %}

{% macro parse_flexible_date(col, fmt) -%}
{%- set s -%}trim({{ col }}){%- endset -%}
case {{ parse_flexible_date_status(col, fmt) }}
    when 'PARSED_ISO' then cast(try_strptime({{ s }}, '%Y-%m-%d') as date)
    when 'PARSED_MDY' then cast(try_strptime({{ s }}, '%m/%d/%Y') as date)
    when 'PARSED_DMY' then cast(try_strptime({{ s }}, '%d/%m/%Y') as date)
    when 'EXCEL_SERIAL' then date '1899-12-30' + cast({{ s }} as integer)
end
{%- endmacro %}
