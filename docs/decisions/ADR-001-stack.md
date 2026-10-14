# ADR-001: Stack: DuckDB + dbt locally, portable to Snowflake

- **Status:** Accepted (Phase 1)
- **Context:** The project needs a warehouse and transformation layer that anyone can run from an empty clone in
  minutes, with no cloud account, while showing production-style SQL: layered models, tests, seeds, macros and
  documentation. All data is synthetic, so nothing here needs a managed or access-controlled service yet.

## Decision

- **Warehouse:** DuckDB, a single local file (`warehouse/flag.duckdb`).
- **Transformations:** `dbt-core` with `dbt-duckdb`: raw -> staging (views) -> intermediate (tables) -> quality (tables),
  with seeds for reference data and macros for shared cleaning logic.
- **Python is only for generating and loading data.** It writes files and lands them as-is in `raw`. All cleaning,
  typing, standardizing and profiling is SQL, so the SQL is the thing under review.
- **Python tooling:** `uv`, `faker`, `openpyxl`, `pyarrow` (ground-truth parquet), `pytest`.

## Alternatives considered

| Option | Why not (for Phase 1) |
|---|---|
| Snowflake / BigQuery from day one | Needs an account and credentials; slows the clone-and-run loop; nothing in Phase 1 needs scale |
| Postgres in Docker | Heavier setup; weaker for analytic SQL (no `UNPIVOT`, no list types, no `QUALIFY`) |
| SQLite | Supports window functions, but lacks `QUALIFY`, `UNPIVOT`, list types and strptime-style date parsing, and its typing is weak, so the staging SQL would need workarounds that don't carry to a warehouse |
| pandas for cleaning | Hides the work in Python, which contradicts "SQL is the showcase" and gives nothing to test with dbt |

## Portability to Snowflake

The dbt project is written to move with a profile change plus the dialect swaps below. What stays unchanged: model
layout, seeds, generic tests, singular tests (they are plain SELECTs), `ref` / `source`, contracts, the data
dictionary script, and most functions (`md5`, `concat_ws`, `split_part`, `nullif`, `coalesce`, `upper`, `lower`,
`trim`, `extract`, `row_number`, `QUALIFY`, `IS DISTINCT FROM`, `UNION ALL`).

To port: (1) add a Snowflake output in `profiles.yml`; (2) swap the DuckDB-specific constructs below; (3) re-run
`dbt build`; (4) point the loader at Snowflake `COPY INTO` or a stage instead of the DuckDB Python API. The
`generate_schema_name` macro already maps custom schemas to plain schema names.

## DuckDB-specific functions and syntax used

| Construct | Where | Snowflake equivalent |
|---|---|---|
| `strip_accents(x)` | `normalize_name` macro (`name_key`) | `TRANSLATE` / collation `'en-ai'` (accent-insensitive) |
| `try_strptime(x, fmt)` | `parse_flexible_date` | `TRY_TO_DATE(x, fmt)` (Snowflake format tokens differ: `MM/DD/YYYY`) |
| `regexp_matches(x, re)` | date, postal, phone macros; staging flags; `dq_summary` | `REGEXP_LIKE(x, re)` (note: full-match semantics) |
| `regexp_extract(x, re, n)` | `stg_us_registrations`, `stg_intl_registrations` | `REGEXP_SUBSTR(x, re, 1, 1, 'e', n)` |
| `regexp_replace(x, re, rep, 'g')` | `normalize_name`, `normalize_phone`, `normalize_ca_postal`, `stg_intl_registrations` | `REGEXP_REPLACE(x, re, rep)` (global by default; drop the `'g'` flag) |
| Lambda list functions `list_transform`, `string_split`, `array_to_string`, `_x -> expr` | `normalize_name` (title case) | `INITCAP` (handles space, hyphen and apostrophe delimiters) |
| `list_filter([...], _f -> _f IS NOT NULL)` and array literals `[a, b]` | all three staging models (`dq_flags`) | `ARRAY_CONSTRUCT_COMPACT(...)` |
| `list_contains(list, x)` | `dq_summary` | `ARRAY_CONTAINS(x::VARIANT, list)` |
| `unnest(list)` in `SELECT` | `dq_defect_log` | `LATERAL FLATTEN(input => list)` |
| `list(x ORDER BY ...)` aggregate | `dq_source_profile` | `ARRAY_AGG(x) WITHIN GROUP (ORDER BY ...)` |
| `UNION ALL BY NAME` | `int_registrations_unioned`, `dq_defect_log`, `dq_source_profile` | `UNION ALL BY NAME` (supported) |
| `SELECT * EXCLUDE (cols)` | staging final selects | `SELECT * EXCLUDE (cols)` (supported) |
| `UNPIVOT INCLUDE NULLS (v FOR c IN (...))` | `dq_source_profile` | Same syntax (supported) |
| `json_extract_string(j, '$.a.b')`, `json_extract(j, '$.a')` | `stg_ca_registrations` | `GET_PATH(j, 'a.b')::VARCHAR`, `GET_PATH(j, 'a')` on a `VARIANT` column |
| `date + integer`, e.g. `DATE '1899-12-30' + n` | `parse_flexible_date` (Excel serials) | `DATEADD(day, n, '1899-12-30'::DATE)` |
| `COUNT(*) FILTER (WHERE ...)` | `dq_source_profile` | `COUNT_IF(...)` |
| `x::integer` casts and `cast(x as varchar(2))` | staging, intermediate | `::` and `CAST` work; DuckDB ignores `varchar(n)` length, Snowflake enforces it |
| `TRY_CAST(x AS TIMESTAMP)` | staging | `TRY_TO_TIMESTAMP(x)` |
| `information_schema.columns` / `.tables` | `raw_contains_no_ground_truth` test | Same, with upper-case identifiers |
| Raw loading via the DuckDB Python API and `CREATE OR REPLACE TABLE ... AS SELECT` | `loader/load_raw.py` | `COPY INTO` from a stage; `CREATE OR REPLACE TABLE` works unchanged |
| `make_date(y, m, d)` | `p5_record_quality` (season start from `p5_params`) | `DATE_FROM_PARTS(y, m, d)` |
| `date_diff('day', a, b)` | `p5_record_quality` | `DATEDIFF(day, a, b)` |
| `regexp_matches(s, pattern)` with `\d`, `\s` | `p5_record_quality`, `stg_p5_registrations` | `REGEXP_LIKE(s, pattern)` (anchors the whole string; add `.*` where a partial match is meant) |
| `try_strptime(s, '%B %d, %Y')`, `%b` | `stg_p5_registrations` (month-name DOBs) | `TRY_TO_DATE(s, 'MMMM DD, YYYY')` |
| `run_query` over a seed at compile time, to turn the `check_sql` text of `p5_dq_rules` into one query | `p5_rule_results` macro | Same dbt macro; needs the seed loaded first (dbt build orders it). The rule SQL itself must stay in the common dialect |
| `count(distinct x) filter (where ...) over (partition by ...)` | `p5_record_quality` | `COUNT(DISTINCT x)` has no window form in Snowflake: precompute the distinct count in a CTE and join it |
| `date_trunc('month', d)` on a date; `md5(s)`; `list_filter(list, x -> ...)` and `list_contains` on the registry's failing-rule lists; `count(distinct (a, b, ...))` over a row value | `idr_input_records` (via `macros/minimization.sql`), `mart_minimization_fitness`, `mart_reidentification_risk` | `DATE_TRUNC('MONTH', d)`, `MD5(s)`, `FILTER(array, x -> ...)` and `ARRAY_CONTAINS`, and `COUNT(DISTINCT OBJECT_CONSTRUCT(...))` or a concatenated key |

## Consequences

- **Good:** `make all` runs in about 20 seconds on a laptop; every step is inspectable SQL; the contract on the unioned
  model and the singular tests give real regression protection.
- **Costs:** a handful of macros need rewriting on a port (name title-casing and date parsing are the largest). A
  single-file warehouse has no roles or row-level security, so the Phase 3 role-based access pattern will be
  demonstrated with views and documented grants, and **not** enforced by the engine.
- **Risk:** DuckDB's looser typing can hide width problems (`varchar(n)`) that Snowflake would reject.
