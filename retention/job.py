"""Phase 5 age-out and revocation retention job. SYNTHETIC data; every retention value is an ASSUMPTION (the actual period is an open question for the privacy lead).

  uv run python -m retention.job [--as-of 2027-12-31] [--no-rebuild]

What it does, in SQL (retention/sql/*.sql), orchestrated here:
  1. rebuild the retention-managed store (schema pii_store) from the Phase 5 dbt models (skipped with --no-rebuild)
  2. revocation, IMMEDIATE: households that revoked consent leave every activation-eligible set
  3. plan what is due: AGE_OUT (Dec 31 of birth year + age_out_age, plus grace), REVOKED (after revocation_delay_days), MAX_AGE (a registration older than max_record_months)
  4. keep aggregates only (counts by reason, market, age band), delete the child-level rows, then the parent side of any household left with no child
  5. log COUNTS ONLY to pii_store.retention_log
  6. verify with independent invariant checks; the job fails (exit 1) if anything over the threshold survives
It never touches raw, eval, the dbt models or the published snapshots.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import duckdb

from generator.population import load_config

SQL = Path(__file__).resolve().parent / "sql"
DB = Path(__file__).resolve().parent.parent / "warehouse" / "flag.duckdb"


def params_from_config(cfg: dict | None = None) -> dict:
    r = (cfg or load_config())["phase5"]["retention"]
    return {"as_of": str(r["as_of"]), "age_out_age": int(r["age_out_age"]), "grace_months": int(r["grace_months"]),
            "max_record_months": int(r["max_record_months"]), "revocation_delay_days": int(r["revocation_delay_days"])}


def _statements(name: str, params: dict) -> list[str]:
    text = (SQL / name).read_text(encoding="utf-8")
    text = "\n".join(line for line in text.split("\n") if not line.lstrip().startswith("--"))
    return [s.strip() for s in text.format_map(params).split(";") if s.strip()]


def _run(con, name: str, params: dict) -> None:
    for stmt in _statements(name, params):
        con.execute(stmt)


def init_schema(con) -> None:
    _run(con, "00_schema.sql", {})


def build_store(con) -> None:
    init_schema(con)
    _run(con, "10_build_store.sql", {})


def verify(con, params: dict) -> dict[str, int]:
    out = {}
    for stmt in _statements("90_verify.sql", params):
        name, n = con.execute(stmt).fetchone()
        out[name] = n
    return out


def run(con, params: dict | None = None) -> dict:
    """Run the job on a connection whose pii_store holds the data. Returns counts only."""
    params = params or params_from_config()
    dt.date.fromisoformat(params["as_of"])                                  # validates the only string that is formatted into SQL
    init_schema(con)
    n = con.execute("select count(distinct run_id) from pii_store.retention_log").fetchone()[0]
    run_id = f"RET-{params['as_of']}-{n + 1:02d}"
    p = {**params, "run_id": run_id}
    before = {t: con.execute(f"select count(*) from pii_store.{t}").fetchone()[0]
              for t in ("child_record", "household_contact", "consent_event", "household_activation")}
    children_before = con.execute("select count(distinct p5_person_id) from pii_store.child_record").fetchone()[0]
    households_before = con.execute("select count(*) from pii_store.household_contact").fetchone()[0]

    _run(con, "20_revocation_activation.sql", p)
    changed = con.execute("select count(*) from _revoked_changed").fetchone()[0]                     # newly removed from an eligible set by this run
    revoked_now = con.execute("select count(*) from _revoked_now").fetchone()[0]
    _run(con, "30_plan.sql", p)
    due = {r[0]: (r[1], r[2]) for r in con.execute("select reason, count(distinct p5_person_id), count(*) from _due_records group by 1").fetchall()}
    _run(con, "40_aggregate_and_delete.sql", p)
    after = {t: con.execute(f"select count(*) from pii_store.{t}").fetchone()[0] for t in before}
    purged = households_before - con.execute("select count(*) from pii_store.household_contact").fetchone()[0]

    def log(rule: str, table: str, rows: int, children: int, households: int) -> None:
        con.execute("insert into pii_store.retention_log values (?, current_timestamp, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [run_id, params["as_of"], rule, table, rows, children, households, params["age_out_age"], params["grace_months"],
                     params["max_record_months"], params["revocation_delay_days"]])
    log("REVOCATION_ACTIVATION_REMOVAL", "household_activation", changed, 0, revoked_now)
    for reason, (children, records) in sorted(due.items()):
        log(reason, "child_record", records, children, 0)
    for t in ("household_contact", "consent_event", "household_activation"):
        log("ORPHAN_HOUSEHOLD_PURGE", t, before[t] - after[t], 0, purged)
    violations = verify(con, params)
    return {"run_id": run_id, "children_before": children_before, "children_after": con.execute("select count(distinct p5_person_id) from pii_store.child_record").fetchone()[0],
            "records_deleted": before["child_record"] - after["child_record"], "households_purged": purged, "due_by_reason": due,
            "revoked_households_as_of": revoked_now, "newly_removed_from_activation": changed, "violations": violations}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of")
    ap.add_argument("--no-rebuild", action="store_true")
    args = ap.parse_args()
    params = params_from_config()
    if args.as_of:
        params["as_of"] = args.as_of
    con = duckdb.connect(str(DB))
    try:
        if not args.no_rebuild:
            build_store(con)
        res = run(con, params)
    finally:
        con.close()
    for k, v in res.items():
        print(f"{k}: {v}")
    return 1 if any(res["violations"].values()) else 0


if __name__ == "__main__":
    sys.exit(main())
