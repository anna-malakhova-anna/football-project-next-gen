"""Load the committed scorecard snapshots (published/*.parquet) into DuckDB schema `published`, so a dbt model
(mart_restatement_log) can compare the current scorecard with what was published. The parquet files are the system of
record; this table is a rebuildable copy. With no snapshots yet it creates an EMPTY table with the right columns.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from generator.population import load_config

ROOT = Path(__file__).resolve().parent.parent
PUBLISHED = ROOT / "published"
EMPTY = """create or replace table published.scorecard_snapshots (
    snapshot_id varchar, published_at timestamp, participation_year integer, kpi_id varchar, value double, low double,
    high double, methodology_version varchar, git_sha varchar, git_dirty boolean,
    raw_rows_us bigint, raw_rows_ca bigint, raw_rows_intl bigint, identity_fingerprint varchar)"""


def load(db_path: str | None = None, published_dir: Path = PUBLISHED, cfg: dict | None = None) -> int:
    cfg = cfg or load_config()
    db = Path(db_path or cfg["paths"]["warehouse"])
    db.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(published_dir.glob("scorecard_*.parquet")) if published_dir.exists() else []
    con = duckdb.connect(str(db))
    try:
        con.execute("create schema if not exists published")
        con.execute(EMPTY)
        for f in files:
            con.execute(f"insert into published.scorecard_snapshots select snapshot_id, published_at, participation_year, kpi_id, "
                        f"value, low, high, methodology_version, git_sha, git_dirty, raw_rows_us, raw_rows_ca, raw_rows_intl, "
                        f"identity_fingerprint from read_parquet('{f.as_posix()}')")
        return con.execute("select count(*) from published.scorecard_snapshots").fetchone()[0]
    finally:
        con.close()


if __name__ == "__main__":
    print(f"published.scorecard_snapshots: {load()} rows")
