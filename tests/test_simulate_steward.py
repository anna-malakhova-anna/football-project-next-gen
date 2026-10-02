import csv
import json

import duckdb
import pytest

from scripts import simulate_steward as sim


@pytest.fixture
def fake_db(tmp_path):
    path = tmp_path / "w.duckdb"
    con = duckdb.connect(str(path))
    con.execute("create schema identity; create schema eval;")
    con.execute("create table identity.idr_input_records as select * from (values "
                "('a','US_LEAGUE','r1'),('b','US_LEAGUE','r2'),('c','US_LEAGUE','r3'),('d','US_LEAGUE','r4'),('e','US_LEAGUE','r5')) "
                "t(match_record_id, source_system, source_record_id)")
    con.execute("create table eval.registration_truth as select * from (values "
                "('US_LEAGUE','r1','P1'),('US_LEAGUE','r2','P1'),('US_LEAGUE','r3','P2'),('US_LEAGUE','r4','P3'),('US_LEAGUE','r5','P3')) "
                "t(source_system, source_record_id, true_person_id)")
    members = json.dumps([{"record": "c", "attrs": {}}, {"record": "d", "attrs": {}}, {"record": "e", "attrs": {}}])
    con.execute("create table identity.idr_review_queue as select * from (values "
                "(1, 'PROBABLE_PAIR', 'a', 'b', null), (2, 'PROBABLE_PAIR', 'a', 'c', null), (3, 'CLUSTER_CONFLICT', null, null, ?)) "
                "t(priority, item_type, record_a, record_b, members)", [members])
    con.close()
    return path


def test_decisions_use_truth_and_cover_clusters(fake_db):
    rows = {(r["record_a"], r["record_b"]): r["decision"] for r in sim.decisions(fake_db, 10)}
    assert rows[("a", "b")] == "MATCH"          # same true person
    assert rows[("a", "c")] == "NO_MATCH"       # different people
    assert rows[("c", "d")] == "NO_MATCH" and rows[("c", "e")] == "NO_MATCH"
    assert rows[("d", "e")] == "MATCH"          # d and e are one person inside the conflicted cluster


def test_top_n_limits_the_queue_items_resolved(fake_db):
    assert len(sim.decisions(fake_db, 1)) == 1


def test_only_writes_the_review_decisions_file_and_labels_the_steward(fake_db, tmp_path):
    out_dir = tmp_path / "seeds"
    out_dir.mkdir()
    out = out_dir / "review_decisions.csv"
    before = {p.name for p in tmp_path.rglob("*")}
    sim.write(sim.decisions(fake_db, 10), out)
    assert {p.name for p in tmp_path.rglob("*")} - before == {"review_decisions.csv"}
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows and {r["decided_by"] for r in rows} == {"SIMULATED_STEWARD"}
    assert list(rows[0]) == sim.HEADER


def test_reset_writes_header_only(tmp_path):
    out = tmp_path / "review_decisions.csv"
    sim.write([], out)
    assert out.read_text() == ",".join(sim.HEADER) + "\n"


def test_default_output_is_the_review_decisions_seed():
    assert sim.OUT.name == "review_decisions.csv" and sim.OUT.parent.name == "seeds"
