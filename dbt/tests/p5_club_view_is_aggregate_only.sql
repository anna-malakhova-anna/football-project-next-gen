{{ config(tags=['phase5']) }}
-- The club-facing schema holds aggregates only.
--  (1) every table and column in it is listed in p5_club_view_policy, and every listed one exists (what is absent is tested)
--  (2) no column name suggests a child or a person (id, name, birth, record)
--  (3) no count column holds a value between 1 and club_min_cell - 1 (the minimum cell size), and no cell is a one-row-per-child grain: rows per club and market are unique
-- depends_on: {{ ref('p5_params') }}
-- depends_on: {{ ref('p5_club_market_view') }}
-- depends_on: {{ ref('p5_club_market_age_view') }}
with actual as (

    select lower(table_name) as table_name, lower(column_name) as column_name
    from information_schema.columns where table_schema = 'phase5_club'

),

k as (select {{ p5_param('club_min_cell') }} as k)

select 'column not in the policy' as problem, table_name || '.' || column_name as detail from actual
where (table_name, column_name) not in (select (table_name, column_name) from {{ ref('p5_club_view_policy') }})
union all
select 'policy column missing', table_name || '.' || column_name from {{ ref('p5_club_view_policy') }}
where (table_name, column_name) not in (select (table_name, column_name) from actual)
union all
select 'child-like column', table_name || '.' || column_name from actual
where regexp_matches(column_name, 'person|child_id|first_name|last_name|given|family|birth|dob|record|email')
union all
select 'cell below the minimum size (market view)', club_id || '|' || market_id from {{ ref('p5_club_market_view') }}, k
where participation_estimate between 1 and k.k - 1 or estimate_low between 1 and k.k - 1 or estimate_high between 1 and k.k - 1
union all
select 'cell below the minimum size (age view)', club_id || '|' || market_id || '|' || coalesce(age_band, 'TOTAL') from {{ ref('p5_club_market_age_view') }}, k
where children between 1 and k.k - 1
union all
select 'duplicate club x market', club_id || '|' || market_id from {{ ref('p5_club_market_view') }} group by club_id, market_id having count(*) > 1
union all
select 'duplicate club x market x band', club_id || '|' || market_id || '|' || coalesce(age_band, 'TOTAL') from {{ ref('p5_club_market_age_view') }} group by club_id, market_id, age_band having count(*) > 1
