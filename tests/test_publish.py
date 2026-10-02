import datetime as dt

import duckdb
import pytest

from loader import load_published
from scripts import publish

NOW = dt.datetime(2026, 1, 15, 9, 30, 0)


@pytest.fixture
def small_db(tmp_path):
    path = tmp_path / "w.duckdb"
    con = duckdb.connect(str(path))
    for schema in ("measurement", "raw", "marts"):
        con.execute(f"create schema {schema}")
    con.execute("""create table measurement.mart_kpi_scorecard as select * from (values
        (2024, 'unique_participants', 3351.0, 3345.0, 3356.0, '1.0'),
        (2025, 'unique_participants', 3962.0, 3953.0, 3965.0, '1.0'),
        (2025, 'retention_rate', 0.6753, cast(null as double), cast(null as double), '1.0')
    ) t(participation_year, kpi_id, value, low, high, methodology_version)""")
    con.execute("create table raw.us_league_registrations as select * from range(10)")
    con.execute("create table raw.ca_club_records as select * from range(4)")
    con.execute("create table raw.intl_federation_returns as select * from range(3)")
    con.execute("create table marts.bridge_registration_participant as select * from (values ('r1', 'P-1'), ('r2', 'P-2')) t(registration_key, participant_id)")
    con.close()
    return path


def _ok():
    return True, ""


def test_refuses_to_publish_when_any_test_fails_and_writes_nothing(small_db, tmp_path):
    out = tmp_path / "published"
    assert publish.publish(2025, out, small_db, run_tests=lambda: (False, "dbt test"), now=NOW) is None
    assert not out.exists() or not list(out.iterdir())


def test_publishes_the_year_with_the_context_needed_to_explain_a_later_change(small_db, tmp_path):
    out = tmp_path / "published"
    path = publish.publish(2025, out, small_db, run_tests=_ok, now=NOW)
    assert path.name == "scorecard_2025_20260115T093000Z.parquet"
    rows = duckdb.connect().execute(f"select * from read_parquet('{path.as_posix()}') order by kpi_id").fetchall()
    cols = [d[0] for d in duckdb.connect().execute(f"select * from read_parquet('{path.as_posix()}')").description]
    assert len(rows) == 2 and {r[cols.index("participation_year")] for r in rows} == {2025}      # only the requested year
    r = dict(zip(cols, rows[1]))
    assert r["kpi_id"] == "unique_participants" and r["value"] == 3962.0 and (r["low"], r["high"]) == (3953.0, 3965.0)
    assert r["methodology_version"] == "1.0" and r["git_sha"] and isinstance(r["git_dirty"], bool)
    assert (r["raw_rows_us"], r["raw_rows_ca"], r["raw_rows_intl"]) == (10, 4, 3)
    assert len(r["identity_fingerprint"]) == 32


def test_published_snapshots_are_immutable(small_db, tmp_path):
    out = tmp_path / "published"
    assert publish.publish(2025, out, small_db, run_tests=_ok, now=NOW) is not None
    assert publish.publish(2025, out, small_db, run_tests=_ok, now=NOW) is None             # same second: refuses to overwrite
    assert len(list(out.glob("*.parquet"))) == 1


def test_refuses_a_year_with_no_scorecard_rows(small_db, tmp_path):
    assert publish.publish(1999, tmp_path / "published", small_db, run_tests=_ok, now=NOW) is None


def test_loader_loads_snapshots_and_creates_an_empty_table_when_there_are_none(small_db, tmp_path):
    out = tmp_path / "published"
    assert load_published.load(str(small_db), out, cfg={"paths": {"warehouse": str(small_db)}}) == 0
    publish.publish(2025, out, small_db, run_tests=_ok, now=NOW)
    assert load_published.load(str(small_db), out, cfg={"paths": {"warehouse": str(small_db)}}) == 2
