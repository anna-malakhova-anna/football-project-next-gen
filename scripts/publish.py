"""Publish a year's KPI scorecard as a versioned, immutable snapshot (ADR-007).

  uv run python -m scripts.publish 2025        (make publish YEAR=2025)

1. Runs EVERY test: dbt test (all phases), pytest, the eval-isolation check and the share-policy check. If any fails, it
   refuses to publish and writes nothing.
2. Writes published/scorecard_<year>_<UTC timestamp>.parquet: the year's KPI rows plus the context needed to explain a
   later change: methodology version, git commit SHA (and whether the tree was dirty), the row counts of the three raw
   source tables, and a fingerprint of the registration-to-participant assignment.
Snapshots are committed and never edited. A changed number is reissued only through the restatement process.
"""
from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "warehouse" / "flag.duckdb"
OUT = ROOT / "published"

CONTEXT_SQL = """
select
    (select count(*) from raw.us_league_registrations)   as raw_rows_us,
    (select count(*) from raw.ca_club_records)           as raw_rows_ca,
    (select count(*) from raw.intl_federation_returns)   as raw_rows_intl,
    (select md5(string_agg(registration_key || participant_id, '|' order by registration_key))
       from marts.bridge_registration_participant)       as identity_fingerprint
"""


def run_all_tests() -> tuple[bool, str]:
    """-> (all passed, which step failed). dbt test fails on any error-severity failure; warn-level tests do not fail."""
    steps = [
        ("dbt test", ["uv", "run", "dbt", "test", "--profiles-dir", "."], ROOT / "dbt"),
        ("pytest", ["uv", "run", "pytest", "-q"], ROOT),
        ("eval isolation", ["uv", "run", "python", "-m", "scripts.check_eval_isolation"], ROOT),
        ("share policy", ["uv", "run", "python", "-m", "scripts.check_share_policy"], ROOT),
    ]
    for name, cmd, cwd in steps:
        if subprocess.run(cmd, cwd=cwd, capture_output=True).returncode != 0:
            return False, name
    return True, ""


def git_state() -> tuple[str, bool]:
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip())
        return sha, dirty
    except Exception:
        return "unknown", True


def build_snapshot(con: duckdb.DuckDBPyConnection, year: int, now: dt.datetime, sha: str, dirty: bool) -> tuple[str, str]:
    """Write the snapshot parquet via the connection; returns (snapshot_id, SELECT that produces it). Pure of side effects
    on the warehouse, so it is testable against a small database."""
    snapshot_id = f"scorecard_{year}_{now.strftime('%Y%m%dT%H%M%SZ')}"
    sql = f"""
        select '{snapshot_id}' as snapshot_id, timestamp '{now.strftime('%Y-%m-%d %H:%M:%S')}' as published_at,
               s.participation_year, s.kpi_id, s.value, s.low, s.high, s.methodology_version,
               '{sha}' as git_sha, {str(dirty).lower()} as git_dirty,
               c.raw_rows_us, c.raw_rows_ca, c.raw_rows_intl, c.identity_fingerprint
        from measurement.mart_kpi_scorecard s cross join ({CONTEXT_SQL}) c
        where s.participation_year = {year}
        order by s.kpi_id"""
    return snapshot_id, sql


def publish(year: int, out_dir: Path = OUT, db_path: Path = DB, run_tests=run_all_tests, now: dt.datetime | None = None) -> Path | None:
    ok, failed = run_tests()
    if not ok:
        print(f"REFUSING TO PUBLISH {year}: '{failed}' failed. Nothing was written.", file=sys.stderr)
        return None
    now = now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0, tzinfo=None)
    sha, dirty = git_state()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        snapshot_id, sql = build_snapshot(con, year, now, sha, dirty)
        n = con.execute(f"select count(*) from ({sql})").fetchone()[0]
        if n == 0:
            print(f"REFUSING TO PUBLISH {year}: the scorecard has no rows for that year.", file=sys.stderr)
            return None
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{snapshot_id}.parquet"
        if path.exists():
            print(f"REFUSING TO OVERWRITE {path.name}: published snapshots are immutable.", file=sys.stderr)
            return None
        con.execute(f"copy ({sql}) to '{path.as_posix()}' (format parquet)")
    finally:
        con.close()
    print(f"published {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path} ({n} KPI rows, git {sha[:8]}{' dirty' if dirty else ''})")
    return path


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0].isdigit():
        print("usage: python -m scripts.publish <YEAR>", file=sys.stderr)
        return 2
    return 0 if publish(int(argv[0])) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
