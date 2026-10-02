import json
from pathlib import Path

import duckdb
import pytest

from scripts import build_site as bs

WAREHOUSE = Path(__file__).resolve().parent.parent / "warehouse" / "flag.duckdb"


def _ds(sql, relations):
    return {"name": "t", "sql": sql, "relations": set(relations), "kind": "x", "title": "t"}


def test_a_dataset_may_only_read_share_exec_approved_aggregates_evaluation_summaries_or_governance_metadata():
    assert bs.check_dataset(_ds("select * from share_exec.share_exec__participation_bounds", ["share_exec.share_exec__participation_bounds"])) == []
    assert bs.check_dataset(_ds("select * from evaluation.eval_retention", ["evaluation.eval_retention"])) == []
    assert bs.check_dataset(_ds("select * from marts.dim_participant", ["marts.dim_participant"]))               # participant level
    assert bs.check_dataset(_ds("select * from share_ops.share_ops__participant", ["share_ops.share_ops__participant"]))
    assert bs.check_dataset(_ds("select * from linkage.link_household_fan_account", ["linkage.link_household_fan_account"]))
    assert bs.check_dataset(_ds("select * from evaluation.eval_record_truth", ["evaluation.eval_record_truth"]))  # not a whitelisted summary


def test_sql_that_reads_an_undeclared_relation_is_refused():
    problems = bs.check_dataset(_ds("select * from share_exec.a join marts.dim_participant using (x)", ["share_exec.a"]))
    assert any("marts.dim_participant" in p for p in problems)


def test_a_chart_spec_may_not_compute_numbers_in_the_browser():
    known = {"data/a.json"}
    ok = {"data": {"url": "data/a.json"}, "mark": "line", "encoding": {"x": {"field": "x", "type": "quantitative"}}}
    assert bs.check_spec(ok, known, "c") == []
    for bad in ({"transform": [{"calculate": "datum.a * 2", "as": "b"}]}, {"transform": [{"aggregate": [{"op": "mean", "field": "a"}]}]},
                {"transform": [{"window": [{"op": "sum", "field": "a"}]}]}, {"transform": [{"fold": ["a", "b"]}]}, {"transform": [{"bin": True}]}):
        assert any("browser" in p for p in bs.check_spec({**ok, **bad}, known, "c")), bad
    assert any("browser" in p for p in bs.check_spec({**ok, "encoding": {"y": {"field": "a", "aggregate": "mean"}}}, known, "c"))
    layered = {"data": {"url": "data/a.json"}, "layer": [{"mark": "line"}, {"mark": "point", "transform": [{"calculate": "1", "as": "z"}]}]}
    assert bs.check_spec(layered, known, "c")


def test_every_chart_reads_a_registered_dataset_and_never_inline_numbers():
    known = {"data/a.json"}
    assert any("not a registered" in p for p in bs.check_spec({"data": {"url": "data/zzz.json"}, "mark": "bar"}, known, "c"))
    assert any("inline" in p for p in bs.check_spec({"data": {"values": [{"a": 1}]}, "mark": "bar"}, known, "c"))


def test_every_defined_chart_passes_the_checks_and_has_a_shows_and_a_does_not_show_sentence():
    names = {d["name"] for d in bs.DATASETS}
    known = {f"data/{n}.json" for n in names}
    for cid, ch in bs.charts().items():
        assert bs.check_spec(ch["spec"], known, cid) == [], cid
        assert set(ch["datasets"]) <= names, cid
        assert ch["shows"].strip().endswith(".") and ch["doesnt"].strip().endswith("."), cid
        assert ch["page"] in {p for p, _ in bs.PAGES + bs.APPENDIX}, cid
    assert all(bs.check_dataset(d) == [] for d in bs.DATASETS)


def test_every_dataset_name_is_unique_and_every_chart_dataset_is_exported_to_a_file():
    names = [d["name"] for d in bs.DATASETS]
    assert len(names) == len(set(names))


@pytest.mark.skipif(not WAREHOUSE.exists(), reason="needs a built warehouse (make all-phases)")
def test_the_site_builds_from_the_warehouse_with_every_page_and_data_file(tmp_path):
    try:
        res = bs.build(WAREHOUSE, tmp_path / "site")
    except duckdb.Error as e:
        pytest.skip(f"warehouse not fully built: {e}")
    site = tmp_path / "site"
    for slug, _ in bs.PAGES + bs.APPENDIX:
        assert (site / f"{slug}.html").exists()
    nav = (site / "index.html").read_text().split("</nav>")[0]
    assert "appendix.html" not in nav                       # the stretch source is off the main navigation, linked from the footer only
    assert "appendix.html" in (site / "index.html").read_text()
    assert "combined reach" not in (site / "participation.html").read_text().lower()
    manifest = json.loads((site / "data" / "manifest.json").read_text())
    assert len(manifest["datasets"]) == res["datasets"]
    assert {d["kind"] for d in manifest["datasets"]} <= {"share_exec", "approved_aggregate", "evaluation", "governance"}
    for d in manifest["datasets"]:
        assert (site / "data" / f"{d['name']}.json").exists(), d["name"]
        assert d["rows"] > 0 or d["name"] == "restatement_log", d["name"]       # an empty restatement log is the good case: nothing published has changed
    index = (site / "index.html").read_text()
    assert "Synthetic data" in index and "5-minute" in index.lower() or "five-minute" in index.lower()
    for slug in ("participation", "identity", "retention", "fandom"):
        text = (site / f"{slug}.html").read_text()
        assert text.count("What this shows") == text.count("What it does not show") >= 1 or slug == "identity"
    # no JavaScript in the pages computes anything: the only script is the embed loop
    for slug, _ in bs.PAGES:
        text = (site / f"{slug}.html").read_text()
        assert "Math." not in text and ".reduce(" not in text and ".map(" not in text
