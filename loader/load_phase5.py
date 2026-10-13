"""Land the Phase 5 feeds in DuckDB schema `raw` as strings (no transformation) and their quarantined truth in schema `eval`.

  raw.p5_<feed>               one table per feed (matrix_export, vendor_reg_a, vendor_reg_b, pop_warner_feed, pal_chapter_csv, school_program); every column
                              keeps its header as found and its values as strings; `_source_file`, `_row_number`, `_loaded_at` are added
  raw.p5_league_catalog       canonical leagues (reference data: league id, name, the key each feed uses, state)
  raw.p5_league_alias_map     steward-maintained free-text spelling -> league id (covers only part of vendor_reg_a's spellings)
  eval.p5_registration_truth  every feed record -> true person, household, canonical league (evaluation models only)
  eval.p5_defect_manifest     every injected defect by feed record

Separate from `make load` on purpose: the Phase 1-4 raw tables and their row-count checks are untouched. Idempotent.
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import duckdb
import pyarrow as pa

from generator.phase5.feeds import FEEDS
from generator.population import load_config


def _read(files: list[Path], base: Path) -> tuple[list[str], list[list]]:
    columns, rows = None, []
    for f in sorted(files):
        with open(f, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            if columns and header != columns:
                raise ValueError(f"{f.name}: header differs from the other files of the feed")
            columns = header
            rows.extend(rec + [f.relative_to(base).as_posix(), n] for n, rec in enumerate(reader, start=1))
    return columns, rows


def load(raw_dir: str | None = None, truth_dir: str | None = None, db_path: str | None = None, cfg: dict | None = None) -> dict[str, int]:
    cfg = cfg or load_config()
    raw = Path(raw_dir or cfg["paths"]["raw_dir"])
    truth = Path(truth_dir or cfg["paths"]["ground_truth_dir"])
    db = Path(db_path or cfg["paths"]["warehouse"])
    db.parent.mkdir(parents=True, exist_ok=True)
    loaded_at = dt.datetime.now().replace(microsecond=0)
    sources = {f"p5_{f}": list((raw / "p5" / f).glob("*.csv")) for f in FEEDS}
    sources["p5_league_catalog"] = [raw / "p5" / "reference" / "league_catalog.csv"]
    sources["p5_league_alias_map"] = [raw / "p5" / "reference" / "league_alias_map.csv"]
    con = duckdb.connect(str(db))
    counts: dict[str, int] = {}
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        con.execute("CREATE SCHEMA IF NOT EXISTS eval")
        for name, files in sources.items():
            if not files:
                raise FileNotFoundError(f"no files for {name}; run `make p5-feeds` first")
            cols, rows = _read(files, raw)
            names = cols + ["_source_file", "_row_number"]
            tbl = pa.Table.from_arrays([pa.array([r[i] for r in rows], type=pa.int32() if names[i] == "_row_number" else pa.string())
                                        for i in range(len(names))], names=names)
            con.register("_landing", tbl)
            con.execute(f'CREATE OR REPLACE TABLE raw.{name} AS SELECT * FROM _landing')
            con.unregister("_landing")
            con.execute(f"ALTER TABLE raw.{name} ADD COLUMN _loaded_at TIMESTAMP DEFAULT TIMESTAMP '{loaded_at}'")
            con.execute(f"UPDATE raw.{name} SET _loaded_at = TIMESTAMP '{loaded_at}'")
            counts[f"raw.{name}"] = con.execute(f"SELECT count(*) FROM raw.{name}").fetchone()[0]
            if counts[f"raw.{name}"] != len(rows):
                raise RuntimeError(f"row count mismatch for {name}")
        for table in ("p5_registration_truth", "p5_defect_manifest"):
            path = truth / f"{table}.parquet"
            con.execute(f"CREATE OR REPLACE TABLE eval.{table} AS SELECT * FROM read_parquet('{path.as_posix()}')")
            counts[f"eval.{table}"] = con.execute(f"SELECT count(*) FROM eval.{table}").fetchone()[0]
    finally:
        con.close()
    return counts


if __name__ == "__main__":
    for table, n in load().items():
        print(f"{table}: {n} rows")
