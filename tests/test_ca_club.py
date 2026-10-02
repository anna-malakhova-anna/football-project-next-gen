import collections
import hashlib
import json

import pyarrow.parquet as pq
import pytest

from generator import main
from generator.population import load_config
from generator.sources import ca_club


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    base = tmp_path_factory.mktemp("gen_ca")
    cfg = load_config()
    res = main.run(cfg, raw_dir=str(base / "raw"), truth_dir=str(base / "truth"))
    out = next(o for o in res["outputs"] if o.source_system == "CA_CLUB")
    return cfg, base, out


def _pages(base):
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((base / "raw" / "ca_club").glob("page_*.json"))]


def _records(base):
    return [r for pg in _pages(base) for r in pg["records"]]


def test_pagination_shape(run):
    cfg, base, _ = run
    pages = _pages(base)
    size = cfg["sources"]["ca_club"]["page_size"]
    assert [p["page"] for p in pages] == list(range(1, len(pages) + 1))
    for p in pages[:-1]:
        assert len(p["records"]) == size
        assert p["next_page"] == p["page"] + 1
    assert pages[-1]["next_page"] is None and 0 < len(pages[-1]["records"]) <= size


def test_record_schema(run):
    _, base, _ = run
    for r in _records(base):
        assert set(r) - {"consents"} == {"member_uuid", "club", "season_year", "program", "participant",
                                         "guardian", "postal_code", "updated_at"}
        assert set(r["club"]) == {"club_code", "club_name", "province"}
        assert set(r["participant"]) == {"prenom_first", "nom_last", "birth_year", "sex", "language"}
        assert set(r["guardian"]) == {"full_name", "email", "phone"}
        if "consents" in r:
            assert set(r["consents"]) == {"casl_marketing", "photo_media", "consent_captured_at"}


def test_defect_counts_match_config(run):
    cfg, base, out = run
    rates = cfg["defects"]["ca_club"]
    recs = _records(base)
    unique = {(r["member_uuid"], r["season_year"]) for r in recs}
    n = len(unique)
    counts = collections.Counter(m["defect_id"] for m in out.manifest)
    for d in ("all_caps_names", "birth_year_off_by_one", "postal_code_format", "missing_consents_object",
              "null_photo_media", "null_casl_marketing"):
        assert counts[d] == pytest.approx(rates[d] * n, rel=0.1, abs=2), d
    assert counts["pagination_overlap_duplicate"] == pytest.approx(rates["pagination_overlap_duplicate"] * n, abs=2)
    assert len(recs) - n == counts["pagination_overlap_duplicate"]
    assert counts["accents_stripped"] > 10


def test_observed_in_raw(run):
    cfg, base, _ = run
    rates = cfg["defects"]["ca_club"]
    recs = _records(base)
    uniq = list({(r["member_uuid"], r["season_year"]): r for r in recs}.values())
    n = len(uniq)
    assert sum("consents" not in r for r in uniq) / n == pytest.approx(rates["missing_consents_object"], rel=0.15)
    odd_postal = sum((" " not in r["postal_code"]) or r["postal_code"].islower() for r in uniq) / n
    assert odd_postal == pytest.approx(rates["postal_code_format"], rel=0.15)
    caps = sum(r["participant"]["nom_last"].isupper() for r in uniq) / n
    assert caps == pytest.approx(rates["all_caps_names"], rel=0.2)
    assert any(r["consents"]["photo_media"] is None for r in uniq if "consents" in r)
    assert {r["participant"]["language"] for r in uniq} == {"fr", "en"}


def test_overlap_duplicates_sit_on_different_pages_and_are_identical(run):
    _, base, _ = run
    where = collections.defaultdict(list)
    for pg in _pages(base):
        for r in pg["records"]:
            where[(r["member_uuid"], r["season_year"])].append((pg["page"], json.dumps(r, sort_keys=True)))
    dups = {k: v for k, v in where.items() if len(v) > 1}
    assert dups
    for v in dups.values():
        assert len(v) == 2 and v[0][0] != v[1][0] and v[0][1] == v[1][1]


def test_uuid_stable_within_club_and_changes_with_club(run):
    _, base, out = run
    truth = pq.read_table(base / "truth" / "registration_truth.parquet").to_pylist()
    person = {t["source_record_id"]: t["true_person_id"] for t in truth if t["source_system"] == "CA_CLUB"}
    by_person = collections.defaultdict(list)
    for r in {(r["member_uuid"], r["season_year"]): r for r in _records(base)}.values():
        by_person[person[f"{r['member_uuid']}|{r['season_year']}"]].append((r["season_year"], r["club"]["club_code"], r["member_uuid"]))
    switched = 0
    for rows in by_person.values():
        mapping = {}
        for _, club, uid in rows:
            assert mapping.setdefault(club, uid) == uid          # one uuid per (person, club)
        assert len(set(mapping.values())) == len(mapping)         # new club -> new uuid
        switched += len(mapping) > 1
    assert switched > 0


def test_programs_cover_known_labels(run):
    _, base, _ = run
    allowed = {l for _, _, opts in ca_club.YOUTH_PROGRAMS for l in opts} | {l for o in ca_club.ADULT_PROGRAMS.values() for l in o}
    assert {r["program"] for r in _records(base)} <= allowed
    assert any("é" in r["program"] for r in _records(base))
    assert any(r["program"].startswith("U") for r in _records(base))


def test_truth_complete_and_deterministic(run, tmp_path):
    cfg, base, out = run
    keys = {t["source_record_id"] for t in out.truth}
    assert keys == {f"{r['member_uuid']}|{r['season_year']}" for r in _records(base)}
    hashes = []
    for i in range(2):
        main.run(cfg, raw_dir=str(tmp_path / f"r{i}"), truth_dir=str(tmp_path / f"t{i}"))
        hashes.append({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (tmp_path / f"r{i}" / "ca_club").glob("*.json")})
    assert hashes[0] == hashes[1] and hashes[0]
