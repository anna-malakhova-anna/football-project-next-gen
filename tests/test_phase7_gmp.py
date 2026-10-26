"""Phase 7 (ADR-025): the dark-market answer key and the GMP_PROXY returns are deterministic, isolated, and built to the stated design."""
import csv
from pathlib import Path

import pytest

from generator.phase7 import gmp
from generator.population import load_config

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "data" / "ground_truth" / "participation_plan.parquet"

pytestmark = pytest.mark.skipif(not PLAN.exists(), reason="needs the generated population (make generate)")


@pytest.fixture(scope="module")
def built():
    cfg = load_config()
    return cfg, *gmp.build(cfg)


def _markets():
    with open(ROOT / "dbt" / "seeds" / "gmp_markets.csv", newline="", encoding="utf-8") as fh:
        return {r["country_code"]: r["country_name"] for r in csv.DictReader(fh)}


def test_build_is_deterministic(built):
    cfg, truth, rows = built
    assert gmp.build(cfg) == (truth, rows)


def test_truth_covers_exactly_the_markets_with_no_participation_source(built):
    cfg, truth, _ = built
    markets = _markets()
    dark = {r["country_code"] for r in truth}
    assert dark < set(markets)
    assert not dark & {"AT", "CA", "DE", "ES", "GB", "JP", "MX"}       # the seven markets with data keep the existing registry as their truth
    assert len(truth) == len(dark) * len(cfg["seasons"]["years"])


def test_exactly_the_configured_share_is_set_against_comparables(built):
    cfg, truth, _ = built
    flags = {r["country_code"]: r["set_against_comparables"] for r in truth}
    assert sum(flags.values()) == round(cfg["phase7"]["truth"]["share_against_comparables"] * len(flags))
    assert all(r["comparable_basis"] in {"REGION_AND_REGIME", "REGION", "ALL"} for r in truth)


def test_proxy_names_only_program_markets_and_never_files_for_a_forced_dark_market(built):
    cfg, _, rows = built
    markets = _markets()
    assert {r["market"] for r in rows} <= set(markets.values())
    forced = {markets[c] for c in cfg["phase7"]["proxy"]["force_dark"]}
    assert not forced & {r["market"] for r in rows}


def test_proxy_defects_are_injected_at_exact_counts(built):
    _, _, rows = built
    base = len({(r["market"], r["season"]) for r in rows})
    assert len(rows) - base == round(gmp.DUPLICATE_SHARE * base)
    assert sum(r["club_events"] == "" for r in rows) == round(gmp.BLANK_EVENTS_SHARE * base)


def test_generator_reads_existing_truth_but_never_writes_it(tmp_path):
    before = {p.name: p.stat().st_mtime_ns for p in (ROOT / "data" / "ground_truth").glob("*.parquet") if p.name != "gmp_market_truth.parquet"}
    (tmp_path / "truth_out").mkdir()
    gmp.run(raw_dir=str(tmp_path / "raw"), truth_dir=str(tmp_path / "truth_out"))
    after = {p.name: p.stat().st_mtime_ns for p in (ROOT / "data" / "ground_truth").glob("*.parquet") if p.name != "gmp_market_truth.parquet"}
    assert before == after
    assert (tmp_path / "truth_out" / "gmp_market_truth.parquet").exists()
    assert sorted(p.name for p in (tmp_path / "raw" / "gmp_proxy").glob("*.csv"))
