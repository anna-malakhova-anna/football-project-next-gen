import duckdb
import pytest

from generator import main as gen_main
from generator.population import load_config
from loader import load_eval
from scripts.check_eval_isolation import find_leaks


def _manifest(nodes, sources=None):
    base_sources = {"source.p.ground_truth.person_registry": {"source_name": "ground_truth", "depends_on": {}},
                    "source.p.raw.us": {"source_name": "raw", "depends_on": {}}}
    return {"nodes": nodes, "sources": {**base_sources, **(sources or {})}}


def _node(path, deps):
    return {"original_file_path": path, "depends_on": {"nodes": deps}}


GT = "source.p.ground_truth.person_registry"


def test_clean_lineage_passes():
    m = _manifest({
        "model.p.stg": _node("models/staging/stg.sql", ["source.p.raw.us"]),
        "model.p.idr": _node("models/identity/idr.sql", ["model.p.stg"]),
        "model.p.eval": _node("models/evaluation/eval.sql", ["model.p.idr", GT]),
    })
    assert find_leaks(m) == []


def test_direct_reference_outside_evaluation_is_a_leak():
    m = _manifest({"model.p.idr": _node("models/identity/idr.sql", [GT])})
    assert find_leaks(m) == [("models/identity/idr.sql", GT)]


def test_transitive_leak_through_an_intermediate_model_is_caught():
    m = _manifest({
        "model.p.a": _node("models/identity/a.sql", [GT]),
        "model.p.b": _node("models/identity/b.sql", ["model.p.a"]),
        "model.p.c": _node("models/marts/c.sql", ["model.p.b"]),
    })
    assert {p for p, _ in find_leaks(m)} == {"models/identity/a.sql", "models/identity/b.sql", "models/marts/c.sql"}


def test_a_model_that_refs_an_evaluation_model_leaks_and_so_does_a_singular_test():
    m = _manifest({
        "model.p.eval": _node("models/evaluation/eval.sql", [GT]),
        "model.p.mart": _node("models/marts/mart.sql", ["model.p.eval"]),
        "test.p.t": _node("tests/t.sql", ["model.p.eval"]),
    })
    assert {p for p, _ in find_leaks(m)} == {"models/marts/mart.sql", "tests/t.sql"}


@pytest.fixture(scope="module")
def loaded(tmp_path_factory):
    base = tmp_path_factory.mktemp("evalload")
    cfg = load_config()
    gen_main.run(cfg, raw_dir=str(base / "raw"), truth_dir=str(base / "truth"))
    counts = load_eval.load(truth_dir=str(base / "truth"), db_path=str(base / "w.duckdb"), cfg=cfg)
    return base, counts


def test_load_eval_loads_the_three_truth_tables_into_schema_eval(loaded):
    base, counts = loaded
    assert counts["person_registry"] == 6000
    assert counts["registration_truth"] > 13000 and counts["defect_manifest"] > 0
    con = duckdb.connect(str(base / "w.duckdb"), read_only=True)
    tables = {r[0] for r in con.execute("select table_name from information_schema.tables where table_schema='eval'").fetchall()}
    assert tables == {"person_registry", "registration_truth", "defect_manifest"}
    assert con.execute("select count(*) from information_schema.schemata where schema_name='raw'").fetchone()[0] == 0
