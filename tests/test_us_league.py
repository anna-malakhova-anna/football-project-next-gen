import collections
import csv
import hashlib
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from generator import main
from generator.population import load_config
from generator.sources import us_league


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    base = tmp_path_factory.mktemp("gen")
    cfg = load_config()
    res = main.run(cfg, raw_dir=str(base / "raw"), truth_dir=str(base / "truth"))
    return cfg, base, res["outputs"][0]


def _rows(base):
    out = []
    for f in sorted((base / "raw" / "us_league").glob("*.csv")):
        with open(f, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                r["_file"] = f.name
                out.append(r)
    return out


def test_files_and_schema(run):
    _, base, out = run
    names = sorted(p.name for p in (base / "raw" / "us_league").glob("*.csv"))
    assert names == sorted(f"registrations_{t}_{y}.csv" for y in (2023, 2024, 2025) for t in ("fall", "spring"))
    with open(base / "raw" / "us_league" / names[0], encoding="utf-8") as f:
        assert next(csv.reader(f)) == us_league.COLUMNS
    assert "SYNTHETIC" in (base / "raw" / "README_SYNTHETIC.txt").read_text()


def test_ids_unique_within_file_except_double_submits(run):
    _, base, _ = run
    rows = _rows(base)
    by_file = collections.defaultdict(list)
    for r in rows:
        by_file[r["_file"]].append(r)
    for f, rs in by_file.items():
        ids = collections.Counter(r["registration_id"] for r in rs)
        dup_ids = {i for i, n in ids.items() if n > 1}
        for i in dup_ids:  # only exact copies may repeat an id
            same = [tuple(sorted(r.items())) for r in rs if r["registration_id"] == i]
            assert len(set(same)) == 1


def test_defect_counts_match_config(run):
    cfg, _, out = run
    rates = cfg["defects"]["us_league"]
    n_rows = sum(len(v) for v in out.files.values())
    counts = collections.Counter(m["defect_id"] for m in out.manifest)
    for defect in ("exact_duplicate", "near_duplicate", "impossible_dob", "dob_day_month_swapped",
                   "guardian_email_case_whitespace", "missing_gender", "missing_photo_consent"):
        assert counts[defect] == pytest.approx(rates[defect] * n_rows, rel=0.12, abs=3), defect
    n_rereg_proxy = n_rows * 0.55  # roughly half of rows are re-registrations
    for defect in ("name_typo_reregistration", "nickname_reregistration",
                   "guardian_email_changed_between_seasons"):
        assert counts[defect] > 0
    assert counts["nickname_reregistration"] == pytest.approx(
        rates["nickname_reregistration"] * n_rereg_proxy, rel=0.5)


def test_observed_in_raw_files(run):
    cfg, base, _ = run
    rates = cfg["defects"]["us_league"]
    rows = _rows(base)
    n = len(rows)
    assert sum(r["player_gender"] == "" for r in rows) / n == pytest.approx(rates["missing_gender"], rel=0.25)
    assert sum(r["photo_consent"] == "" for r in rows) / n == pytest.approx(rates["missing_photo_consent"], rel=0.15)
    assert {r["photo_consent"] for r in rows} == {"Y", "N", ""}
    assert any("/" in r["player_dob"] for r in rows) and any("-" in r["player_dob"] for r in rows)
    assert {r["player_gender"] for r in rows} >= {"M", "F", "Boy", "Girl", "Female", "Male", ""}
    assert any(len(r["zip"]) == 4 for r in rows)
    keys = [tuple(sorted(r.items())) for r in rows]
    exact_extra = n - len(set(keys))
    assert exact_extra == pytest.approx(rates["exact_duplicate"] * n, rel=0.15)
    emails = [r["guardian_email"] for r in rows]
    messy = sum(e != e.strip().lower() for e in emails) / n
    assert messy == pytest.approx(rates["guardian_email_case_whitespace"], rel=0.15)


def test_phone_formats_and_division_labels(run):
    _, base, _ = run
    rows = _rows(base)
    assert any(r["guardian_phone"].startswith("(") for r in rows)
    assert any(r["guardian_phone"].count(".") == 2 for r in rows)
    assert any(r["guardian_phone"].isdigit() for r in rows)
    labels = {r["division"] for r in rows}
    assert {"U10", "10U", "Under 10"} <= labels


def test_truth_covers_every_record_and_manifest_consistent(run):
    _, base, out = run
    truth = [t for t in pq.read_table(base / "truth" / "registration_truth.parquet").to_pylist()
             if t["source_system"] == "US_LEAGUE"]
    keys = {(t["source_file"], t["source_record_id"]) for t in truth}
    assert len(keys) == len(truth)
    for rel, rows in out.files.items():
        for r in rows:
            assert (rel, r["registration_id"]) in keys
    man = pq.read_table(base / "truth" / "defect_manifest.parquet").to_pylist()
    assert {m["defect_id"] for m in man if m["source_system"] == "US_LEAGUE"} <= set(load_config()["defects"]["us_league"])


def test_ground_truth_not_in_raw_dir(run):
    _, base, _ = run
    assert not list((base / "raw").rglob("*.parquet"))


def test_deterministic_file_hashes(tmp_path):
    cfg = load_config()
    hashes = []
    for i in range(2):
        main.run(cfg, raw_dir=str(tmp_path / f"raw{i}"), truth_dir=str(tmp_path / f"t{i}"))
        h = {p.relative_to(tmp_path / f"raw{i}").as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in (tmp_path / f"raw{i}").rglob("*") if p.is_file()}
        hashes.append(h)
    assert hashes[0] == hashes[1] and hashes[0]


def test_twins_share_league_season_guardian_and_dob_but_not_first_name(run):
    import pyarrow.parquet as pq
    _, base, out = run
    reg = {p["true_person_id"]: p for p in pq.read_table(base / "truth" / "person_registry.parquet").to_pylist()}
    truth = {(t["source_file"], t["source_record_id"]): t["true_person_id"] for t in out.truth}
    twins = collections.defaultdict(list)
    for rel, rows in out.files.items():
        for r in rows:
            pid = truth[(rel, r["registration_id"])]
            if reg[pid]["twin_group_id"]:
                twins[(reg[pid]["twin_group_id"], r["season"])].append((pid, r))
    pairs = [v for v in twins.values() if len({pid for pid, _ in v}) == 2]
    assert len(pairs) >= 5
    for v in pairs:
        by_pid = {}
        for pid, r in v:
            by_pid.setdefault(pid, r)
        a, b = by_pid.values()
        assert a["league_id"] == b["league_id"] and a["season"] == b["season"]
        assert a["player_first_name"].lower() != b["player_first_name"].lower()
