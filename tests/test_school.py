import collections
import csv
import hashlib

import pyarrow.parquet as pq
import pytest

from generator import main
from generator.population import load_config
from generator.sources import school


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    base = tmp_path_factory.mktemp("gen_school")
    cfg = load_config()
    res = main.run(cfg, raw_dir=str(base / "raw"), truth_dir=str(base / "truth"))
    out = next(o for o in res["outputs"] if o.source_system == "SCHOOL_AGGREGATES")
    return cfg, base, out


def _rows(base):
    out = []
    for f in sorted((base / "raw" / "school").glob("headcounts_*.csv")):
        with open(f, newline="", encoding="utf-8") as fh:
            out += [{**r, "_file": f.name} for r in csv.DictReader(fh)]
    return out


def test_one_file_per_year_with_the_documented_columns_and_no_individuals(run):
    cfg, base, _ = run
    names = sorted(p.name for p in (base / "raw" / "school").glob("*.csv"))
    assert names == [f"headcounts_{y}.csv" for y in cfg["seasons"]["years"]]
    with open(base / "raw" / "school" / names[0], encoding="utf-8") as f:
        assert next(csv.reader(f)) == school.COLUMNS
    assert not {"name", "first_name", "last_name", "dob", "email", "participant_id"} & set(school.COLUMNS)


def test_program_types_and_countries_are_the_documented_values(run):
    _, base, _ = run
    rows = _rows(base)
    assert {r["program_type"] for r in rows} == {"PE_UNIT", "INTRAMURAL", "AFTER_SCHOOL"}
    assert {r["country"] for r in rows} <= {"US", "CA", "MX", "GB", "JP", "DE", "AT", "PA"}
    assert all(r["region"] == "" for r in rows if r["country"] not in ("US", "CA"))


def test_defect_counts_are_exact_and_visible_in_the_raw_files(run):
    cfg, base, out = run
    rates = cfg["defects"]["school_aggregates"]
    rows = _rows(base)
    base_rows = len(rows) - collections.Counter(m["defect_id"] for m in out.manifest)["duplicate_report"]
    counts = collections.Counter(m["defect_id"] for m in out.manifest)
    for d in ("total_mismatch", "missing_grade_band", "duplicate_report", "round_number"):
        assert counts[d] == round(rates[d] * base_rows), d
    mismatch = sum(int(r["girls_count"]) + int(r["boys_count"]) != int(r["total_count"]) for r in rows)
    assert mismatch >= counts["total_mismatch"] - 1                      # the duplicate-report perturbation can add a few
    blank = sum(r["grade_band"] == "" for r in rows)
    assert counts["missing_grade_band"] <= blank <= counts["missing_grade_band"] + counts["duplicate_report"]      # a duplicate report of a blank-band row repeats the blank
    assert sum(int(r["total_count"]) in cfg["sources"]["school"]["round_values"] for r in rows) >= counts["round_number"]


def test_double_reports_come_from_a_different_reporter_and_a_later_date(run):
    _, base, _ = run
    by_prog = collections.defaultdict(list)
    for r in _rows(base):
        by_prog[(r["_file"], r["district"], r["school_or_program"])].append(r)
    dups = [v for v in by_prog.values() if len(v) > 1]
    assert dups
    for v in dups:
        assert len(v) == 2 and v[0]["reported_by"] != v[1]["reported_by"] and v[0]["report_date"] <= v[1]["report_date"]


def test_truth_is_consistent_and_overlap_is_bounded(run):
    cfg, base, _ = run
    truth = pq.read_table(base / "truth" / "school_truth.parquet").to_pylist()
    overlap = pq.read_table(base / "truth" / "school_overlap_truth.parquet").to_pylist()
    cap = cfg["sources"]["school"]["max_overlap_share_of_program"]
    for t in truth:
        assert t["true_girls"] + t["true_boys"] == t["true_total"] and t["overlap_count"] <= cap * t["true_total"] + 1
    n = collections.Counter((o["program_key"], o["year"]) for o in overlap)
    assert all(n[(t["program_key"], t["year"])] == t["overlap_count"] for t in truth)
    assert len({(o["year"], o["true_person_id"]) for o in overlap}) == len(overlap)        # a person is in at most one program a year
    reg = {p["true_person_id"]: p for p in pq.read_table(base / "truth" / "person_registry.parquet").to_pylist()}
    for o in overlap:
        assert 5 <= o["year"] - reg[o["true_person_id"]]["dob"].year <= 17                  # overlapping kids are school-age youth


def test_overlap_people_are_registered_in_the_same_year_and_place(run):
    _, base, _ = run
    plan = pq.read_table(base / "truth" / "participation_plan.parquet").to_pylist()
    where = collections.defaultdict(set)
    for r in plan:
        where[(r["true_person_id"], r["season_year"])].add((r["country_code"], r["region_code"] or ""))
    prog = {(t["program_key"], t["year"]): t for t in pq.read_table(base / "truth" / "school_truth.parquet").to_pylist()}
    for o in pq.read_table(base / "truth" / "school_overlap_truth.parquet").to_pylist():
        t = prog[(o["program_key"], o["year"])]
        assert (t["country"], t["region"]) in where[(o["true_person_id"], o["year"])]


def test_truth_never_lands_in_the_raw_directory_and_files_are_deterministic(run, tmp_path):
    cfg, base, _ = run
    assert not list((base / "raw").rglob("*.parquet"))
    hashes = []
    for i in range(2):
        main.run(cfg, raw_dir=str(tmp_path / f"r{i}"), truth_dir=str(tmp_path / f"t{i}"))
        hashes.append({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (tmp_path / f"r{i}" / "school").glob("*.csv")})
    assert hashes[0] == hashes[1] and len(hashes[0]) == len(cfg["seasons"]["years"])
