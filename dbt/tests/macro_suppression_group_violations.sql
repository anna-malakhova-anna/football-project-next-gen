{{ config(tags=['phase3']) }}
-- The independent suppression checker must DETECT violations, or the exec tests prove nothing. Feed it a table with known
-- violations and a clean one; this test fails if it misses a violation or flags a clean group.
--   2023: lone suppressed cell (NULL) beside a published total and two published siblings  -> LONE_SUPPRESSED_CELL
--   2024: a published count of 4 (below k_min 10)                                          -> UNSUPPRESSED_SMALL_CELL
--   2025: clean: two suppressed cells, and a zero published                                -> nothing
--   2026: lone suppressed cell but the total itself suppressed                              -> nothing (no published subtotal)
with src(year, country, n) as (
    values (2023, cast(null as varchar), 100), (2023, 'A', cast(null as integer)), (2023, 'B', 60), (2023, 'C', 40),
           (2024, null, 80), (2024, 'A', 4), (2024, 'B', 76),
           (2025, null, 90), (2025, 'A', null), (2025, 'B', null), (2025, 'C', 0), (2025, 'D', 90),
           (2026, null, cast(null as integer)), (2026, 'A', null), (2026, 'B', 50)
),
v as (select * from {{ suppression_group_violations('src', ['year', 'country'], 'n') }})
select 'missed_lone_cell' as problem from (select 1) where not exists (select 1 from v where problem = 'LONE_SUPPRESSED_CELL' and detail like '2023%')
union all
select 'missed_small_cell' from (select 1) where not exists (select 1 from v where problem = 'UNSUPPRESSED_SMALL_CELL' and detail like '2024|A')
union all
select 'false_alarm_' || detail from v where detail like '2025%' or detail like '2026%'
union all
select 'unexpected_count_' || cast(count(*) as varchar) from v having count(*) <> 2
