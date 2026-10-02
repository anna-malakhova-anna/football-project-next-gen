import csv
from pathlib import Path

from generator import export_config_seed as ecs
from generator.population import load_config

SEED = Path(__file__).resolve().parent.parent / "dbt" / "seeds" / "dq_defect_config.csv"


def test_every_configured_defect_has_a_catalog_entry_and_vice_versa():
    cfg = load_config()
    catalog = {(s, d) for s, d, kind, *_ in ecs.CATALOG if kind == "rate"}
    configured = {(src, d) for src, key in ecs.SOURCE_KEY.items() for d in cfg["defects"][key]}
    assert catalog == configured


def test_catalog_has_no_duplicates():
    keys = [(s, d) for s, d, *_ in ecs.CATALOG]
    assert len(keys) == len(set(keys))


def test_seed_file_is_in_sync_with_config():
    with open(SEED, newline="", encoding="utf-8") as f:
        on_disk = list(csv.DictReader(f))
    assert on_disk == [{k: str(v) for k, v in r.items()} for r in ecs.build_rows(load_config())]


def test_observation_window_and_reporting_periods_seeds_are_in_sync_with_config():
    import pytest
    cfg = load_config()
    seeds = SEED.parent
    with open(seeds / "observation_window.csv", newline="", encoding="utf-8") as f:
        assert list(csv.DictReader(f)) == [{k: str(v) for k, v in r.items()} for r in ecs.window_rows(cfg)]
    with open(seeds / "reporting_periods.csv", newline="", encoding="utf-8") as f:
        assert list(csv.DictReader(f)) == [{k: str(v) for k, v in r.items()} for r in ecs.period_rows(cfg)]
    assert len(ecs.period_rows(cfg)) == 3 * len(cfg["seasons"]["years"])
    bad = {**cfg, "seasons": {**cfg["seasons"], "first_observed_year": cfg["seasons"]["years"][0] + 1}}
    with pytest.raises(ValueError):
        ecs.window_rows(bad)
