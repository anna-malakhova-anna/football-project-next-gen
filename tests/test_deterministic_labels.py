"""The tie-break labels are deterministic: building the affected models again gives the same output, labels included.

Ties used to be broken in no fixed order (DuckDB `arg_min` and `mode()` on equal values), so two builds of unchanged code could name a different limiting dimension, a different list of
top failing rules or a different child age band, and a weighted score that sat on a rounding boundary could flip in the last digit (a float sum in a different order). The rules now (ADR-023): limiting_dimension ties go to the lowest `tie_priority` in dq_dimensions.csv; top_failing_rules are ordered by
impact desc, records affected desc, then rule_id; a child's birth year ties go to the later year (the younger band); the weighted scores are summed in exact decimals.

The test works on a COPY of the warehouse (its own dbt profile, target and log paths), so it never touches the real one. It skips when no warehouse has been built.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = ROOT / "warehouse" / "flag.duckdb"
MODELS = ["p5_child", "dq_scorecard_source", "dq_scorecard_org", "dq_scorecard_market", "dq_trend", "mart_dq_impact", "share_ops__league_scorecard", "dq_fix_list", "dq_fix_ranking", "share_ops__league_fix_list"]
BUILDS = 5


def _tables(con) -> dict[str, str]:
    """model name -> schema.table of the affected models in the copy."""
    rows = con.execute("select table_schema, table_name from information_schema.tables where table_catalog = current_database()").fetchall()
    return {t: f"{s}.{t}" for s, t in rows if t in MODELS}


@pytest.mark.skipif(not WAREHOUSE.exists(), reason="no warehouse built")
def test_rebuilding_the_affected_models_gives_identical_output_labels_included(tmp_path):
    (tmp_path / "wh").mkdir()
    db = tmp_path / "wh" / "flag.duckdb"   # the catalog name (flag) comes from the file name; some models name it
    shutil.copy(WAREHOUSE, db)
    prof = tmp_path / "profiles"
    prof.mkdir()
    (prof / "profiles.yml").write_text(f"counting_flag_football:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n      path: {db}\n      threads: 4\n", encoding="utf-8")
    snaps = []
    for i in range(BUILDS):
        r = subprocess.run(["uv", "run", "dbt", "run", "--project-dir", "dbt", "--profiles-dir", str(prof), "--target-path", str(tmp_path / "target"), "--log-path", str(tmp_path / "logs"),
                            "--select", *MODELS], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1000:]
        con = duckdb.connect(str(db))
        try:
            tables = _tables(con)
            assert set(tables) == set(MODELS), f"missing models in the copy: {set(MODELS) - set(tables)}"
            for m, t in tables.items():
                con.execute(f"create or replace table main.snap_{i}_{m} as select * from {t}")
        finally:
            con.close()
        snaps.append(i)
    con = duckdb.connect(str(db))
    try:
        for m in MODELS:
            n = con.execute(f"select count(*) from main.snap_0_{m}").fetchone()[0]
            assert n > 0, f"{m} is empty"
            for i in range(1, BUILDS):
                a = con.execute(f"select count(*) from (select * from main.snap_0_{m} except all select * from main.snap_{i}_{m})").fetchone()[0]
                b = con.execute(f"select count(*) from (select * from main.snap_{i}_{m} except all select * from main.snap_0_{m})").fetchone()[0]
                assert a == 0 and b == 0, f"{m}: build {i} differs from build 0 ({a} rows only in the first, {b} only in the later one)"
    finally:
        con.close()
