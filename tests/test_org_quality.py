"""Phase 5 spec section 3: organization quality profiles, missing-not-at-random patterns, dark organizations, consent wording. SYNTHETIC data."""
import collections
import csv

import pyarrow.parquet as pq
import pytest

from generator import main
from generator import profiles as P
from generator.population import load_config


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    base = tmp_path_factory.mktemp("oq")
    cfg = load_config()
    main.run(cfg, raw_dir=str(base / "raw"), truth_dir=str(base / "truth"))
    return base, cfg


def _t(base, name):
    return pq.read_table(base / "truth" / name).to_pylist()


def test_profile_mix_is_exact_and_correlates_with_size(built):
    base, cfg = built
    orgs = _t(base, "org_quality_truth.parquet")
    mix = cfg["org_quality"]["profile_mix"]
    counts = collections.Counter(o["profile"] for o in orgs)
    n = len(orgs)
    assert set(counts) == set(P.PROFILES)
    assert abs(counts["DISCIPLINED"] - mix["DISCIPLINED"] * n) <= 2 and abs(counts["STRUGGLING"] - mix["STRUGGLING"] * n) <= 2
    us = [o for o in orgs if o["source_system"] == "US_LEAGUE"]
    mean = lambda ps: sum(o["n_records_all_seasons"] for o in us if o["profile"] in ps) / max(1, sum(1 for o in us if o["profile"] in ps))   # noqa: E731
    assert mean({"STRUGGLING", "MANUAL"}) < mean({"DISCIPLINED"})          # small organizations skew to the worse profiles


def test_defects_concentrate_in_worse_profiles_but_overall_rates_hold(built):
    base, cfg = built
    prof = {o["org_id"]: o["profile"] for o in _t(base, "org_quality_truth.parquet")}
    league_of = {}
    with open(base / "raw" / "us_league" / "registrations_fall_2023.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            league_of[r["registration_id"]] = r["league_id"]
    rows_by_profile = collections.Counter()
    for f in (base / "raw" / "us_league").glob("*.csv"):
        with open(f, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows_by_profile[prof[r["league_id"]]] += 1
    man = [m for m in _t(base, "defect_manifest.parquet") if m["source_system"] == "US_LEAGUE" and m["defect_id"] == "guardian_email_case_whitespace"]
    # the manifest holds a mechanism for every record
    assert all(m["mechanism"] and m["mechanism"].startswith(("ORG_PROFILE", "MNAR", "MANUAL_ORG")) for m in man)
    by_prof = collections.Counter(m["mechanism"].split(":")[-1] for m in man)
    rate = {p: by_prof[p] / rows_by_profile[p] for p in P.PROFILES if rows_by_profile[p] >= 200}
    assert rate["STRUGGLING"] > 2 * rate["DISCIPLINED"]
    total = sum(by_prof.values()) / sum(rows_by_profile.values())
    assert abs(total - cfg["defects"]["us_league"]["guardian_email_case_whitespace"]) < 0.01      # exact-count placement keeps the configured overall rate


def test_missing_gender_is_not_missing_at_random(built):
    base, _ = built
    man = [m for m in _t(base, "defect_manifest.parquet") if m["source_system"] == "US_LEAGUE" and m["defect_id"] == "missing_gender"]
    mechs = collections.Counter(m["mechanism"].split(":")[1] for m in man)
    assert mechs["COED_YOUNGER_DIVISION"] > 0 and mechs["MANUAL_ORG"] > 0
    young = {"U6", "U8", "U10", "Under 6", "Under 8", "Under 10", "6U", "8U", "10U"}
    blank = collections.Counter()
    seen = collections.Counter()
    for f in (base / "raw" / "us_league").glob("*.csv"):
        with open(f, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                key = r["division"] in young
                seen[key] += 1
                blank[key] += r["player_gender"] == ""
    assert blank[True] / seen[True] > 1.5 * blank[False] / seen[False]      # blank gender concentrates in co-ed younger divisions: the girls' share is biased


def test_dark_organizations_exist_only_in_the_truth(built):
    base, cfg = built
    lo, hi = cfg["org_quality"]["unreporting"]["share_range"]
    with open(base / "raw" / "org_registry.csv", newline="", encoding="utf-8") as fh:
        reg = list(csv.DictReader(fh))
    assert "profile" not in reg[0] and "dark" not in reg[0]                   # the registry is what the program knows: it carries the channel, never the profile
    by_year = collections.defaultdict(list)
    for r in reg:
        by_year[r["season_year"]].append(r["reports_data"] == "N")
    for y, flags in by_year.items():
        assert lo - 0.03 <= sum(flags) / len(flags) <= hi + 0.03
    unreported = _t(base, "unreported_participation_truth.parquet")
    assert unreported
    dark = {(r["org_id"], int(r["season_year"])) for r in reg if r["reports_data"] == "N"}
    assert {(u["org_id"], u["season_year"]) for u in unreported} <= dark
    # no file row exists for a dark organization-season
    leagues_in_files = collections.Counter()
    for f in (base / "raw" / "us_league").glob("*.csv"):
        with open(f, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                leagues_in_files[(r["league_id"], int(r["season"].split()[-1]))] += 1
    assert not (set(leagues_in_files) & dark)


def test_manual_orgs_have_blank_consent_free_text_divisions_and_age_group_only_files(built):
    base, cfg = built
    orgs = {o["org_id"]: o for o in _t(base, "org_quality_truth.parquet")}
    manual = {o for o, v in orgs.items() if v["profile"] == "MANUAL" and v["source_system"] == "US_LEAGUE"}
    assert manual
    age_only = {o for o in manual if orgs[o]["age_group_only"]}
    rows = []
    for f in (base / "raw" / "us_league").glob("*.csv"):
        with open(f, newline="", encoding="utf-8") as fh:
            rows += [r for r in csv.DictReader(fh) if r["league_id"] in manual]
    assert rows and all(r["consent_text_version"] == "" for r in rows)       # the wording is unknown
    assert sum(r["photo_consent"] == "" for r in rows) > 0.5 * len(rows)       # the consent fields are missing entirely
    assert all(r["player_dob"] == "" for r in rows if r["league_id"] in age_only)
    assert any(r["division"] in {"Littles", "Middle kids", "Teens", "Open"} for r in rows)


def test_consent_wording_versions_follow_the_configured_set(built):
    base, cfg = built
    versions = set(cfg["org_quality"]["consent_text_versions"])
    seen = set()
    for f in (base / "raw" / "us_league").glob("*.csv"):
        with open(f, newline="", encoding="utf-8") as fh:
            seen |= {r["consent_text_version"] for r in csv.DictReader(fh)}
    assert seen - {""} <= versions and len(seen - {""}) >= 3
    assert "" in seen                                                         # some forms emit no wording at all


def test_pick_weighted_is_exact_and_respects_weights():
    import random
    rng = random.Random(1)
    idx = list(range(1000))
    w = {i: (50.0 if i < 100 else 1.0) for i in idx}
    got = P.pick_weighted(rng, idx, w, 0.1, 1000)
    assert len(got) == 100 and len(set(got)) == 100
    assert sum(1 for i in got if i < 100) > 60            # the heavy rows are chosen far more often than their 10% share
    assert len(P.pick_weighted(rng, idx[:5], {i: 1.0 for i in idx[:5]}, 0.9, 1000)) == 5       # never more than are eligible


def test_a_rerun_leaves_no_files_from_an_earlier_run(tmp_path):
    """A run that writes fewer API pages must not leave the previous run's extra pages to be loaded as data (found when stale Canadian pages inflated the warehouse)."""
    cfg = load_config()
    raw = tmp_path / "raw"
    main.run(cfg, raw_dir=str(raw), truth_dir=str(tmp_path / "truth"))
    stale = raw / "ca_club" / "page_9999.json"
    stale.write_text('{"page": 9999, "next_page": null, "records": [{"stale": true}]}', encoding="utf-8")
    main.run(cfg, raw_dir=str(raw), truth_dir=str(tmp_path / "truth"))
    assert not stale.exists()


def test_fix_list_adoption_is_off_by_default_exact_and_improves_only_the_final_season():
    from generator import profiles as P
    cfg = load_config()
    profs = {f"O{i}": ("STRUGGLING" if i < 10 else "TYPICAL") for i in range(40)}
    assert P.fix_list_adopters(cfg, profs) == set()                                  # off by default
    on = {**cfg, "org_quality": {**cfg["org_quality"], "fix_list_adoption": {"enabled": True, "share_of_struggling_orgs": 0.5, "final_season_improves_to": "TYPICAL"}}}
    adopters = P.fix_list_adopters(on, profs)
    assert len(adopters) == 5 and all(profs[o] == "STRUGGLING" for o in adopters)
    assert adopters == P.fix_list_adopters(on, profs)                                # deterministic
    o = sorted(adopters)[0]
    last, first = max(cfg["seasons"]["years"]), min(cfg["seasons"]["years"])
    assert P.profile_in_season(on, o, last, "STRUGGLING", adopters) == "TYPICAL"
    assert P.profile_in_season(on, o, first, "STRUGGLING", adopters) == "STRUGGLING"
    assert P.profile_in_season(on, "O20", last, "TYPICAL", adopters) == "TYPICAL"
