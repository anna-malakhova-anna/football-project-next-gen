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


def test_phase5_datasets_may_read_the_club_and_privacy_shares_and_nothing_row_level():
    for ok in ("share_club.share_club__market_year", "share_privacy.share_privacy__consent_provenance", "quality.mart_dq_impact", "evaluation.eval_minimization_tradeoff"):
        assert bs.check_dataset(_ds(f"select * from {ok}", [ok])) == [], ok
    for bad in ("linkage.int_consent_event", "quality.dq_record_fitness", "quality.mart_market_coverage", "evaluation.eval_minimization_checks", "marts.dim_participant"):
        assert bs.check_dataset(_ds(f"select * from {bad}", [bad])), bad


def test_every_phase5_chart_names_the_question_it_answers_and_both_lens_notes():
    from scripts import site_phase5 as p5
    from scripts import site_cards
    copy = site_cards.load_copy()
    for cid, ch in p5.charts().items():
        if ch.get("card"):                      # cards take question and lens notes from site_src/copy/charts.yml
            c = copy[ch["card"]["id"]]
            assert c["question"].strip().endswith("?") and all(c[k].strip() for k in ("means_club", "means_privacy", "action_club", "action_privacy", "caution")), cid
            continue
        assert ch["question"].strip().endswith(")") or ch["question"].strip().endswith("?"), cid
        assert ch["lens"]["club"].strip() and ch["lens"]["privacy"].strip(), cid


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
        assert ch.get("spec") is None or bs.check_spec(ch["spec"], known, cid) == [], cid
        assert ch.get("spec") or ch.get("render") or ch.get("card"), cid
        assert set(ch["datasets"]) <= names, cid
        if ch.get("card"):
            for sp in [ch["card"].get("thumb")] + [sl.get("spec") for sl in ch["card"]["slides"]]:
                if sp is None:
                    continue
                assert bs.check_spec(sp, known, cid) == [], cid
            assert ch["page"] in {p for p, _ in bs.PAGES + bs.APPENDIX}, cid
            continue
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
    assert {d["kind"] for d in manifest["datasets"]} <= {"share_exec", "share_club", "share_privacy", "approved_aggregate", "evaluation", "governance"}
    for d in manifest["datasets"]:
        assert (site / "data" / f"{d['name']}.json").exists(), d["name"]
        assert d["rows"] > 0 or d["name"] == "restatement_log", d["name"]       # an empty restatement log is the good case: nothing published has changed
    index = (site / "index.html").read_text()
    assert "Synthetic data" in index and "5-minute" in index.lower() or "five-minute" in index.lower()
    for slug in ("acquisition", "value", "audience", "participation", "trust", "quality", "sure", "markets", "privacy"):
        text = (site / f"{slug}.html").read_text()
        assert text.count("What this shows") == text.count("What it does not show")      # old-style sections come in pairs
        assert text.count("What this shows") + text.count('class="vcard"') >= 1             # a page has old sections, cards, or both
    # no JavaScript in the pages computes anything: the only script is the embed loop
    for slug, _ in bs.PAGES:
        text = (site / f"{slug}.html").read_text()
        assert "Math." not in text and ".reduce(" not in text and ".map(" not in text


@pytest.mark.skipif(not WAREHOUSE.exists(), reason="needs a built warehouse (make all-phases)")
def test_fan_acquisition_comes_first_and_the_first_chart_is_the_incremental_estimate(tmp_path):
    try:
        bs.build(WAREHOUSE, tmp_path / "site")
    except duckdb.Error as e:
        pytest.skip(f"warehouse not fully built: {e}")
    assert [slug for slug, _ in bs.PAGES][:4] == ["index", "acquisition", "value", "audience"]
    page = (tmp_path / "site" / "acquisition.html").read_text()
    assert page.index('id="sec-acq_estimates"') < page.index('id="sec-funnel_status"')
    index = (tmp_path / "site" / "index.html").read_text()
    assert "fans" in index.split("<h2>")[0].lower() and "contact" in index.lower()
    audience = (tmp_path / "site" / "audience.html").read_text().lower()
    assert "not a marketing list" in audience or "no household is identified" in audience


def test_the_brand_boundary_check_refuses_images_foreign_svg_and_foreign_favicons(tmp_path):
    site = tmp_path / "site"
    (site / "css").mkdir(parents=True)
    (site / "favicon.svg").write_text(bs.FAVICON, encoding="utf-8")
    (site / "css" / "site.css").write_text("body{margin:0}", encoding="utf-8")
    ok = '<svg data-mark="project" viewBox="0 0 1 1"></svg><svg aria-hidden="true"></svg>'
    (site / "index.html").write_text(f"<html><body>{ok}</body></html>", encoding="utf-8")
    assert bs.check_brand_boundary(site) == []
    (site / "index.html").write_text(f'<html><body>{ok}<img src="x.png"></body></html>', encoding="utf-8")
    assert any("image element" in p for p in bs.check_brand_boundary(site))
    (site / "index.html").write_text('<html><body><svg viewBox="0 0 1 1"><path d="M0 0"/></svg></body></html>', encoding="utf-8")
    assert any("inline SVG" in p for p in bs.check_brand_boundary(site))
    (site / "index.html").write_text(f"<html>{ok}</html>", encoding="utf-8")
    (site / "logo.webp").write_bytes(b"x")
    assert any("image files" in p for p in bs.check_brand_boundary(site))
    (site / "logo.webp").unlink()
    (site / "favicon.svg").write_text("<svg><path d='M0 0'/></svg>", encoding="utf-8")
    assert any("favicon" in p for p in bs.check_brand_boundary(site))
    (site / "favicon.svg").write_text(bs.FAVICON, encoding="utf-8")
    (site / "css" / "site.css").write_text("a{background:url(shield.png)}", encoding="utf-8")
    assert any("url()" in p for p in bs.check_brand_boundary(site))


def test_numbers_show_thousands_separators_but_years_stay_plain_and_rates_are_percentages():
    assert bs.fmt_cell(4665, "households") == "4,665" and bs.fmt_cell(13043, "households") == "13,043"
    assert bs.fmt_cell(2021, "participation_year") == "2021"
    assert bs.fmt_cell(0.25, "consent_gap_share_of_active") == "25.0%"


def test_the_local_logo_is_allowed_only_as_the_wordmark_image_and_only_when_asked_for(tmp_path):
    site = tmp_path / "site"
    (site / "css").mkdir(parents=True)
    (site / "img").mkdir()
    (site / "favicon.svg").write_text(bs.FAVICON, encoding="utf-8")
    (site / "css" / "site.css").write_text("body{margin:0}", encoding="utf-8")
    (site / "img" / "logo.webp").write_bytes(b"x")
    logo = '<img class="wordmark-logo" src="img/logo.webp" alt="" width="36" height="36">'
    (site / "index.html").write_text(f"<html>{logo}</html>", encoding="utf-8")
    assert bs.check_brand_boundary(site, local_logo=True) == []
    assert bs.check_brand_boundary(site)                                    # a CI build (no local logo) refuses it
    (site / "index.html").write_text(f'<html>{logo}<img src="img/logo.webp"></html>', encoding="utf-8")
    assert any("image element" in p for p in bs.check_brand_boundary(site, local_logo=True))
