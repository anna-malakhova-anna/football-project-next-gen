{{ config(tags=['phase4']) }}
-- Profile of the RAW aggregate source (Source E): the aggregate-shaped equivalent of dq_source_profile (playbook, Profiling stage).
-- One row per column: rows, blanks, distinct values and the most common values (programs are institutions, not people, so showing them is
-- fine; small programs are still suppressed wherever they are shared). Then the issue counters the profile exists to find.
{% set columns = ['district', 'school_or_program', 'country', 'region', 'program_type', 'grade_band', 'girls_count', 'boys_count', 'total_count', 'reported_by', 'report_date'] %}
with raw as (select * from {{ source('raw', 'school_headcounts') }}),

long as (

    select column_name, nullif(trim(val), '') as val
    from raw
    unpivot include nulls (val for column_name in ({{ columns | join(', ') }}))

),

stats as (

    select column_name, count(*) as row_count, count(*) filter (where val is null) as blank_count, count(distinct val) as distinct_count
    from long group by 1

),

freq as (

    select column_name, val, count(*) as n, row_number() over (partition by column_name order by count(*) desc, val) as rnk
    from long where val is not null group by 1, 2

),

top as (select column_name, list(val || ' (' || n || ')' order by rnk) as top_values from freq where rnk <= 5 group by 1),

ordinals as (select * from (values {% for c in columns %}('{{ c }}', {{ loop.index }}){{ ',' if not loop.last }}{% endfor %}) as t(column_name, column_position))

select
    'column_profile' as section,
    o.column_position,
    s.column_name                                                           as item,
    s.row_count                                                             as n,
    round(s.blank_count * 1.0 / s.row_count, 4)                             as rate,
    s.distinct_count,
    t.top_values,
    cast(null as varchar)                                                   as note
from stats s join ordinals o using (column_name) left join top t using (column_name)

union all

select 'issue', 100 + row_number() over (order by item), item, n, round(n * 1.0 / (select count(*) from raw), 4), null, null, note
from (
    select 'total_not_girls_plus_boys' as item,
           count(*) filter (where try_cast(girls_count as integer) + try_cast(boys_count as integer) <> try_cast(total_count as integer)) as n,
           'total_count differs from girls_count + boys_count' as note from raw
    union all
    select 'round_total', count(*) filter (where try_cast(total_count as integer) in (100, 150, 200, 250, 300)), 'suspiciously round totals' from raw
    union all
    select 'missing_grade_band', count(*) filter (where nullif(trim(grade_band), '') is null), 'blank grade band' from raw
    union all
    select 'double_reported_program_year', count(*) - count(distinct (district, school_or_program, program_type, _source_file)),
           'same program reported more than once in a year (extra rows)' from raw
    union all
    select 'rows_with_non_numeric_count', count(*) filter (where try_cast(total_count as integer) is null), 'total_count is not an integer' from raw
)

order by section desc, column_position
