# Counting Flag Football

Governed participation data platform built on **synthetic** flag football data (the real equivalent would be minors' PII).

**Source of truth for what to build:** `phase-1-spec.md` and `phase-2-spec.md` (Phase 2 builds on Phase 1; later phases are context).

## Conventions
- SQL is the showcase: Python generates and loads data as-is; all cleaning/typing/standardizing happens in dbt SQL.
- Raw is immutable: raw tables are strings in, strings stored.
- Deterministic: global seed 42 (`config/generation.yaml`).
- Ground truth lives in `data/ground_truth/` and is never loaded into `raw` or referenced by dbt models.
- Consent NULL means "not captured"; never coerce to TRUE/FALSE.
- Keep dbt portable (Snowflake later); log every DuckDB-specific function in `docs/decisions/ADR-001-stack.md`.
- Age is computed as of Dec 31 of the season year (ADR-002).
- Stop after each numbered build step in spec section 10 and confirm it runs.

## Phase 2 conventions (identity resolution)
- The matcher never sees ground truth: it lives in schema `eval`, source `ground_truth`, read only by `dbt/models/evaluation/`
  (`scripts/check_eval_isolation.py` enforces it). m-probabilities are reasoned, never tuned against truth.
- Every link carries its reason; `matcher` / `stage` / `scope` columns let one run compare matchers and review stages.
- Precision first: a sibling or twin false merge is a privacy incident. The steward in `simulate_steward.py` is simulated;
  never present POST_REVIEW numbers as matcher performance.
- Phase 2 models and their tests carry the dbt tag `phase2`; `make all` excludes them, `make phase2` runs everything.

## Commands
`make setup | generate | load | build | test | all | clean`; Phase 2: `make load-eval | idr | eval | phase2`
