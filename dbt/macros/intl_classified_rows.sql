{#-
  intl_classified_rows()
  The raw INTL layer holds every worksheet row positionally (c1..c9), junk included. This returns each
  raw row with `header_row` (per file + sheet) and `junk_reason`:
      TITLE_ROW | BLANK_ROW | HEADER_ROW | SUMMARY_ROW | NULL for a real player row
  Shared by stg_intl_registrations (which drops junk) and dq_defect_log (which logs what was dropped),
  so both always agree on what counts as junk.
-#}
{% macro intl_classified_rows() -%}
(
    with hdr as (
        select _source_file, _sheet_name, min(_excel_row) as header_row
        from {{ source('raw', 'intl_federation_returns') }}
        where trim(c1) = 'Player ID'
        group by 1, 2
    )
    select
        r.*,
        h.header_row,
        case
            when concat_ws('', r.c1, r.c2, r.c3, r.c4, r.c5, r.c6, r.c7, r.c8, r.c9) = '' then 'BLANK_ROW'
            when r._excel_row < h.header_row then 'TITLE_ROW'
            when r._excel_row = h.header_row then 'HEADER_ROW'
            when trim(r.c1) like 'Total:%' then 'SUMMARY_ROW'
            else null
        end as junk_reason
    from {{ source('raw', 'intl_federation_returns') }} r
    left join hdr h using (_source_file, _sheet_name)
)
{%- endmacro %}
