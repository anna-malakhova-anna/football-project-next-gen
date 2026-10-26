"""Phase 7 step 8 (ADR-030): every artifact a walkthrough stage points to exists, each market walks the playbook's six stages in order, and the
Italy experiment's report exists and says the published build keeps Italy dark."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGES = ["Discovery", "Profiling", "Contracted", "Staged", "Modelled", "Production"]


def _rows():
    with open(ROOT / "dbt" / "seeds" / "gmp_walkthrough_stages.csv", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_every_artifact_exists():
    missing = [r["artifact"] for r in _rows() if r["artifact"] and not (ROOT / r["artifact"]).exists()]
    assert not missing


def test_each_market_walks_the_six_stages_in_order():
    by = {}
    for r in _rows():
        by.setdefault(r["country_code"], []).append((int(r["stage_order"]), r["stage"]))
    assert set(by) == {"CA", "IT"}
    assert all([s for _, s in sorted(v)] == STAGES for v in by.values())


def test_only_a_not_started_stage_lacks_an_artifact():
    assert all(r["artifact"] or r["state"] == "NOT_STARTED" for r in _rows())


def test_the_experiment_report_exists_and_keeps_italy_dark_in_the_published_build():
    text = (ROOT / "docs" / "reports" / "p7_italy_experiment.md").read_text(encoding="utf-8")
    assert "copy" in text and "keep Italy dark" in text
