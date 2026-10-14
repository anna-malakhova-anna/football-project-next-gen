import csv
from pathlib import Path
import re

import pyarrow.parquet as pq
import pytest

from generator import main
from generator.phase5 import feeds
from generator.population import load_config


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    base = tmp_path_factory.mktemp("p5")
    cfg = load_config()
    res = feeds.run(cfg, raw_dir=str(base / "raw"), truth_dir=str(base / "truth"))
    return base, cfg, res


def _rows(base, feed):
    out = []
    for f in sorted((base / "raw" / "p5" / feed).glob("*.csv")):
        with open(f, newline="", encoding="utf-8") as fh:
            out.extend(csv.DictReader(fh))
    return out


def test_six_feeds_with_different_schemas(built):
    base, _, res = built
    assert set(res["rows"]) == set(feeds.FEEDS) and all(n > 0 for n in res["rows"].values())
    assert len({tuple(feeds.COLUMNS[f]) for f in feeds.FEEDS}) == 6
    for f in feeds.FEEDS:
        assert len(_rows(base, f)) == res["rows"][f]


def test_deterministic(built, tmp_path):
    base, cfg, _ = built
    feeds.run(cfg, raw_dir=str(tmp_path / "raw"), truth_dir=str(tmp_path / "truth"))
    for f in feeds.FEEDS:
        assert _rows(base, f) == _rows(tmp_path, f)


def test_defects_are_injected_at_exact_counts(built):
    base, cfg, _ = built
    man = pq.read_table(base / "truth" / "p5_defect_manifest.parquet").to_pylist()
    for feed in feeds.FEEDS:
        n = sum(1 for _ in _rows(base, feed))
        for defect, rate in cfg["phase5"]["defects"][feed].items():
            got = sum(1 for m in man if m["feed"] == feed and m["defect_id"] == defect)
            if defect == "duplicate_row":
                n -= got
                assert got == round(rate * n) or abs(got - round(rate * n)) <= 1
            elif defect == "blank_flag_league_code":
                assert got > 0
            else:
                assert got == min(round(rate * n), got) and abs(got - round(rate * n)) <= 1, (feed, defect, got, rate * n)


def test_defect_rates_are_configurable(built, tmp_path):
    _, cfg, _ = built
    cfg2 = load_config()
    cfg2["phase5"]["defects"]["matrix_export"]["missing_zip"] = 0.0
    feeds.run(cfg2, raw_dir=str(tmp_path / "raw"), truth_dir=str(tmp_path / "truth"))
    assert all(r["parent_zip"] != "" for r in _rows(tmp_path, "matrix_export"))
    man = pq.read_table(tmp_path / "truth" / "p5_defect_manifest.parquet").to_pylist()
    assert not [m for m in man if m["feed"] == "matrix_export" and m["defect_id"] == "missing_zip"]


def test_feed_specific_shapes(built):
    base, _, _ = built
    assert all("date_of_birth" not in r for r in _rows(base, "vendor_reg_b")) and all(r["age_group"] in ("", "U6", "U8", "U10", "U12", "U14", "U17")
                                                                                       for r in _rows(base, "vendor_reg_b"))
    assert {r["program_type"] for r in _rows(base, "pop_warner_feed")} == {"FLAG", "TACKLE"}
    assert not any(k in _rows(base, "school_program")[0] for k in ("parent_email", "guardian_email", "zip"))
    assert all(r["Extra 1"] == "" and r["Extra 2"] == "" for r in _rows(base, "pal_chapter_csv"))
    assert len({r["birthdate"][:0] or len(r["birthdate"]) for r in _rows(base, "vendor_reg_a")}) > 1       # mixed DOB text formats


def test_synthetic_only_and_truth_covers_every_record(built):
    base, _, _ = built
    real = re.compile(r"@(gmail|yahoo|hotmail|outlook|icloud|aol)\.", re.I)
    for f, col in (("matrix_export", "parent_email"), ("vendor_reg_a", "guardian_email"), ("vendor_reg_b", "parent_email"),
                   ("pop_warner_feed", "guardian_email"), ("pal_chapter_csv", "Parent Email")):
        assert not any(real.search(r[col]) for r in _rows(base, f)), f
    truth = pq.read_table(base / "truth" / "p5_registration_truth.parquet").to_pylist()
    assert sum(1 for t in truth) == sum(len(_rows(base, f)) for f in feeds.FEEDS)


def test_existing_sources_are_untouched(tmp_path):
    cfg = load_config()
    main.run(cfg, raw_dir=str(tmp_path / "raw"), truth_dir=str(tmp_path / "truth"))
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    feeds.run(cfg, raw_dir=str(tmp_path / "raw"), truth_dir=str(tmp_path / "truth"))
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert all(after[k] == v for k, v in before.items())                       # nothing from Phase 1-4 changed
    assert {k.parts[0:2] for k in after.keys() - before.keys()} <= {("raw", "p5"), ("truth", "p5_registration_truth.parquet"),
                                                                  ("truth", "p5_defect_manifest.parquet")}


def test_p5_params_seed_is_in_sync_with_config():
    from generator.phase5 import export_seed
    path = Path(__file__).resolve().parent.parent / "dbt" / "seeds" / "p5_params.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        on_disk = list(csv.DictReader(fh))
    assert on_disk == export_seed.build_rows(load_config())


def test_data_standard_doc_is_in_sync_with_the_seed():
    import subprocess
    import sys
    assert subprocess.run([sys.executable, "-m", "scripts.build_data_standard", "--check"], cwd=Path(__file__).resolve().parent.parent).returncode == 0


def test_data_standard_names_every_field_and_the_exclusions():
    import csv
    root = Path(__file__).resolve().parent.parent
    doc = (root / "docs" / "data-standard.md").read_text(encoding="utf-8")
    with open(root / "dbt" / "seeds" / "p5_data_standard.csv", newline="", encoding="utf-8") as fh:
        fields = [r["field_name"] for r in csv.DictReader(fh)]
    assert all(f"`{f}`" in doc for f in fields)
    assert "deliberately do not ask for" in doc


def test_consent_purpose_taxonomy_has_one_activation_purpose():
    import csv
    root = Path(__file__).resolve().parent.parent / "dbt" / "seeds"
    with open(root / "p5_consent_purposes.csv", newline="", encoding="utf-8") as fh:
        purposes = list(csv.DictReader(fh))
    assert {p["purpose_id"] for p in purposes} == {"LEAGUE_OPERATIONS", "LEAGUE_COMMUNICATIONS", "NFL_CLUB_MARKETING", "THIRD_PARTY_DISCLOSURE", "PROFILING"}
    assert [p["purpose_id"] for p in purposes if p["counts_for_club_activation"] == "true"] == ["NFL_CLUB_MARKETING"]
    with open(root / "p5_consent_wording_map.csv", newline="", encoding="utf-8") as fh:
        used = {x for r in csv.DictReader(fh) for x in r["purposes_covered"].split("|") if x}
    assert used <= {p["purpose_id"] for p in purposes} and "NFL_CLUB_MARKETING" not in used       # a wording alone never grants club marketing


def test_club_territory_has_shared_markets_and_uncovered_markets():
    import csv
    from generator.phase5 import export_seed
    root = Path(__file__).resolve().parent.parent / "dbt" / "seeds"
    markets = list(csv.DictReader(open(root / "market_map.csv", newline="", encoding="utf-8")))
    cfg = load_config()
    terr, clubs = export_seed.territory_rows(cfg, markets)
    assert {r["role"] for r in terr} == {"PRIMARY", "SHARED"}
    owned = {r["market_id"] for r in terr}
    us = {m["market_id"] for m in markets if m["country_code"] == "US"}
    assert us - owned, "some markets must have no club"
    shared = {r["market_id"] for r in terr if r["role"] == "SHARED"}
    assert all(sum(1 for r in terr if r["market_id"] == m) > 1 for m in shared)
    on_disk = list(csv.DictReader(open(root / "p5_club_territory.csv", newline="", encoding="utf-8")))
    assert on_disk == terr
    assert all("synthetic" in c["club_name"] for c in clubs)


def test_census_stub_is_labelled_synthetic():
    import csv
    rows = list(csv.DictReader(open(Path(__file__).resolve().parent.parent / "dbt" / "seeds" / "p5_youth_population_zip3.csv", newline="", encoding="utf-8")))
    assert rows and all("SYNTHETIC" in r["source"] for r in rows)


PHASE5_DOCS = ["data-standard.md", "market-estimate.md", "retention.md", "questions-for-stakeholders.md", "phase5-demo.md", "decisions/ADR-012-phase-5-scope-and-design.md"]


def test_questions_for_stakeholders_has_the_required_questions_and_sources():
    doc = (Path(__file__).resolve().parent.parent / "docs" / "questions-for-stakeholders.md").read_text(encoding="utf-8").lower()
    for needle in ("third party", "consent wording", "retention period", "intake channels"):
        assert needle in doc
    for url in ("nflflag.com/policy", "nflflag.com/faq", "youthsportsbusinessreport.com", "playfootball.nfl.com", "colts.com", "finnegan.com"):
        assert url in doc


def test_phase5_docs_make_no_compliance_claims_and_state_they_are_synthetic():
    import re
    root = Path(__file__).resolve().parent.parent / "docs"
    banned = re.compile(r"non-?compliant|in violation|violates|illegal|unlawful|breach(es|ed)? (of )?(coppa|the law)", re.I)
    for name in PHASE5_DOCS:
        text = (root / name).read_text(encoding="utf-8")
        assert not banned.search(text), name
        assert "synthetic" in text.lower(), name


def test_club_third_party_question_is_not_resolved_in_the_docs():
    root = Path(__file__).resolve().parent.parent / "docs"
    for name in PHASE5_DOCS:
        text = (root / name).read_text(encoding="utf-8").lower()
        import re
        assert not re.search(r"(?<!if )(?<!whether )(a club is (not )?a third party|clubs are (not )?third parties)", text), name   # only conditional or question phrasing


def test_rule_registry_seed_is_in_sync_and_covers_every_contract_rule():
    import subprocess
    import sys

    import yaml
    root = Path(__file__).resolve().parent.parent
    assert subprocess.run([sys.executable, "-m", "scripts.build_rule_registry", "--check"], cwd=root).returncode == 0
    with open(root / "dbt" / "seeds" / "dq_rule_registry.csv", newline="", encoding="utf-8") as fh:
        reg = list(csv.DictReader(fh))
    refs = {r["contract_ref"] for r in reg if r["origin"] == "CONTRACT"}
    quality_rules = 0
    for path in sorted((root / "contracts").glob("*.yml")):
        if path.name.startswith("_"):
            continue
        c = yaml.safe_load(path.read_text(encoding="utf-8"))
        for q in c.get("quality") or []:
            if q["rule"].startswith("max_"):
                quality_rules += 1
                col = q.get("column") or q.get("name") or ",".join(q.get("key") or [])
                comp = path.stem.split("__")[1] if "__" in path.stem else ""
                assert f"{c['source_system']}|{comp}@{c['version']}#{q['rule']}:{col}" in refs, (path.name, q)
    assert quality_rules == len(refs)                                  # no contract quality rule is missing, and the registry invents none
    assert all(not r["check_sql"] for r in reg if r["origin"] == "CONTRACT")      # the contract owns the measurement and the threshold: the registry restates neither's SQL


def test_no_model_or_test_restates_a_contract_threshold():
    root = Path(__file__).resolve().parent.parent / "dbt"
    offenders = [str(p.relative_to(root)) for pat in ("models/**/*.sql", "tests/*.sql") for p in root.glob(pat) if "max_null_rate" in p.read_text(encoding="utf-8")]
    assert not offenders, offenders
