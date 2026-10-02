# Counting Flag Football

Governed participation data platform built on **synthetic** flag football data (the real equivalent would be minors' PII).

**Source of truth for what to build:** `phase-1-spec.md` (build Phase 1 only; later phases are context).

## Conventions
- SQL is the showcase: Python generates and loads data as-is; all cleaning/typing/standardizing happens in dbt SQL.
- Raw is immutable: raw tables are strings in, strings stored.
- Deterministic: global seed 42 (`config/generation.yaml`).
- Ground truth lives in `data/ground_truth/` and is never loaded into `raw` or referenced by dbt models.
- Consent NULL means "not captured"; never coerce to TRUE/FALSE.
- Keep dbt portable (Snowflake later); log every DuckDB-specific function in `docs/decisions/ADR-001-stack.md`.
- Age is computed as of Dec 31 of the season year (ADR-002).
- Stop after each numbered build step in spec section 10 and confirm it runs.

## Commands
`make setup | generate | load | build | test | all | clean`
