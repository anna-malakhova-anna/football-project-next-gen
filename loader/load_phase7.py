"""Land the Phase 7 GMP_PROXY returns in DuckDB schema `raw` as strings (no transformation) and the dark-market answer key in schema `eval`.

  raw.gmp_proxy           club-filed returns per program market and season (market, season, club_events, games_in_market, federation_exists,
                          reported_by, report_date), values as found; `_source_file`, `_row_number`, `_loaded_at` are added
  eval.gmp_market_truth   true participants and direction of the 15 markets with no participation source (evaluation models only, ADR-025)

Separate from `make load` on purpose: no Phase 1-6 raw table is touched. Idempotent.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import pyarrow as pa

from generator.population import load_config
from loader.load_phase5 import _read


def load(raw_dir: str | None = None, truth_dir: str | None = None, db_path: str | None = None, cfg: dict | None = None) -> dict[str, int]:
    cfg = cfg or load_config()
    raw = Path(raw_dir or cfg["paths"]["raw_dir"])
    truth = Path(truth_dir or cfg["paths"]["ground_truth_dir"])
    db = Path(db_path or cfg["paths"]["warehouse"])
    files = list((raw / "gmp_proxy").glob("*.csv"))
    if not files:
        raise FileNotFoundError("no GMP_PROXY files; run `make p7-data` first")
    loaded_at = dt.datetime.now().replace(microsecond=0)
    cols, rows = _read(files, raw)
    names = cols + ["_source_file", "_row_number"]
    tbl = pa.Table.from_arrays([pa.array([r[i] for r in rows], type=pa.int32() if names[i] == "_row_number" else pa.string()) for i in range(len(names))],
                               names=names)
    con = duckdb.connect(str(db))
    counts: dict[str, int] = {}
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        con.execute("CREATE SCHEMA IF NOT EXISTS eval")
        con.register("_landing", tbl)
        con.execute("CREATE OR REPLACE TABLE raw.gmp_proxy AS SELECT * FROM _landing")
        con.unregister("_landing")
        con.execute(f"ALTER TABLE raw.gmp_proxy ADD COLUMN _loaded_at TIMESTAMP DEFAULT TIMESTAMP '{loaded_at}'")
        con.execute(f"UPDATE raw.gmp_proxy SET _loaded_at = TIMESTAMP '{loaded_at}'")
        counts["raw.gmp_proxy"] = con.execute("SELECT count(*) FROM raw.gmp_proxy").fetchone()[0]
        if counts["raw.gmp_proxy"] != len(rows):
            raise RuntimeError("row count mismatch for gmp_proxy")
        path = truth / "gmp_market_truth.parquet"
        con.execute(f"CREATE OR REPLACE TABLE eval.gmp_market_truth AS SELECT * FROM read_parquet('{path.as_posix()}')")
        counts["eval.gmp_market_truth"] = con.execute("SELECT count(*) FROM eval.gmp_market_truth").fetchone()[0]
    finally:
        con.close()
    return counts


if __name__ == "__main__":
    for table, n in load().items():
        print(f"{table}: {n} rows")
