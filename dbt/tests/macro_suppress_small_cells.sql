{{ config(tags=['phase3']) }}
-- suppress_small_cells edge cases on a hierarchy year -> country -> age_band, k = 10. Returns failing cases.
--  2023  group under the year total: counts 5 (small), 40, 30  -> 5 PRIMARY, 30 SECONDARY (next smallest), 40 published
--  2024  two small cells (4, 7) and 50      -> both PRIMARY, no secondary (two unknowns cannot be separated)
--  2025  10 (exactly k), 9 and a zero       -> 9 PRIMARY; the zero is never the cell hidden, so the smallest non-zero (10) is SECONDARY; 0 published
--  2026  the small cell's parent is itself small (suppressed) -> no secondary
--  2027  a single child of a parent         -> small cell PRIMARY, nothing more to hide
-- plus rates: nulled when a component is small or the row is suppressed.
with src(year, country, band, n, youth, girls, rate) as (
    values
        (2023, cast(null as varchar), cast(null as varchar), 75, 60, 30, 0.5),
        (2023, 'A', null, 5, 5, 2, 0.4),
        (2023, 'B', null, 40, 30, 15, 0.5),
        (2023, 'C', null, 30, 25, 10, 0.4),
        (2024, null, null, 61, 50, 20, 0.4),
        (2024, 'A', null, 4, 4, 1, 0.25),
        (2024, 'B', null, 7, 6, 3, 0.5),
        (2024, 'C', null, 50, 40, 16, 0.4),
        (2025, null, null, 19, 15, 6, 0.4),
        (2025, 'A', null, 10, 8, 3, 0.375),
        (2025, 'B', null, 9, 7, 3, 0.43),
        (2025, 'Z', null, 0, 0, 0, null),
        (2026, null, null, 8, 8, 4, 0.5),
        (2026, 'A', null, 3, 3, 1, 0.33),
        (2026, 'B', null, 5, 5, 3, 0.6),
        (2027, null, null, 40, 30, 12, 0.4),
        (2027, 'A', null, 6, 6, 2, 0.33),
        (2028, null, null, 100, 70, 35, 0.5),
        (2028, 'A', null, 100, 70, 35, 0.5),
        (2028, 'A', '0-7', 7, 7, 3, 0.43),
        (2028, 'A', '8-9', 60, 40, 20, 0.5),
        (2028, 'A', '10-11', 33, 23, 12, 0.52)
),
got as (
    select * from {{ suppress_small_cells('src', ['year', 'country', 'band'], ['n'], rates={'rate': ['girls', 'youth']}, passthrough=[], k=10) }}
),
expected(year, country, band, n, rate, suppressed) as (
    values
        (2023, cast(null as varchar), cast(null as varchar), 75, 0.5, 'NONE'),
        (2023, 'A', null, cast(null as integer), cast(null as double), 'PRIMARY'),
        (2023, 'B', null, 40, 0.5, 'NONE'),
        (2023, 'C', null, null, null, 'SECONDARY'),
        (2024, null, null, 61, 0.4, 'NONE'),
        (2024, 'A', null, null, null, 'PRIMARY'),
        (2024, 'B', null, null, null, 'PRIMARY'),
        (2024, 'C', null, 50, 0.4, 'NONE'),
        (2025, null, null, 19, null, 'NONE'),
        (2025, 'A', null, null, null, 'SECONDARY'),
        (2025, 'B', null, null, null, 'PRIMARY'),
        (2025, 'Z', null, 0, null, 'NONE'),
        (2026, null, null, null, null, 'PRIMARY'),
        (2026, 'A', null, null, null, 'PRIMARY'),
        (2026, 'B', null, null, null, 'PRIMARY'),
        (2027, null, null, 40, 0.4, 'NONE'),
        (2027, 'A', null, null, null, 'PRIMARY'),
        (2028, null, null, 100, 0.5, 'NONE'),
        (2028, 'A', null, 100, 0.5, 'NONE'),
        (2028, 'A', '0-7', null, null, 'PRIMARY'),
        (2028, 'A', '8-9', 60, 0.5, 'NONE'),
        (2028, 'A', '10-11', null, null, 'SECONDARY')
)
select e.year, e.country, e.band, e.n as expected_n, g.n as got_n, e.rate as expected_rate, g.rate as got_rate, e.suppressed as expected, g.suppressed as got
from expected e left join got g on e.year = g.year and e.country is not distinct from g.country and e.band is not distinct from g.band
where g.suppressed is distinct from e.suppressed or g.n is distinct from e.n or g.rate is distinct from e.rate
