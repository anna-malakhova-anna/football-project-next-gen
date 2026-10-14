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
