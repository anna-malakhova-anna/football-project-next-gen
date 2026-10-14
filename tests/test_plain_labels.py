"""Phase 5.1: the plain-language labels read as plain language (the dbt test checks coverage; this checks wording)."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERBS = {"Remove", "Keep", "Correct", "Send", "Collect", "Ask", "Require", "Pick", "Use", "Let", "Store", "Trim", "Capture", "Export", "Record", "Make", "Report", "Deliver", "Timestamp",
         "Open", "Check", "Confirm", "Bring", "Fix", "Name"}
BANNED = ("interval", "bound", "sigma", "registry", "provenance", "suppress", "cohort", "schema", "grain")


def _rules():
    with open(ROOT / "dbt" / "seeds" / "dq_rule_registry.csv", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_every_rule_has_a_short_plain_label_and_an_action_that_starts_with_a_verb():
    for r in _rules():
        assert r["plain_label"].strip() and len(r["plain_label"].split()) <= 6, r["rule_id"]
        assert r["plain_action"].strip() and len(r["plain_action"].split()) <= 15, r["rule_id"]
        assert r["plain_action"].split()[0] in VERBS, (r["rule_id"], r["plain_action"])


def test_hand_written_rule_text_has_no_jargon_or_codes():
    with open(ROOT / "config" / "rule_plain_text.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            text = (r["plain_label"] + " " + r["plain_action"]).lower()
            assert not any(b in text for b in BANNED), r["rule_id"]
            assert "dq-" not in text and "_" not in text, r["rule_id"]


def test_purpose_labels_are_the_agreed_plain_names():
    with open(ROOT / "dbt" / "seeds" / "dq_purposes.csv", newline="", encoding="utf-8") as fh:
        got = {r["purpose"]: r["plain_label"] for r in csv.DictReader(fh)}
    assert got == {"COUNT": "Counting players", "SEGMENT": "Breaking down by age and gender", "GEO": "Placing players on the map", "RETAIN": "Tracking who comes back", "ACTIVATE": "Contacting families"}


def test_market_plain_names_are_state_and_number_and_never_a_team():
    from generator.phase5.export_seed import plain_market_name
    assert plain_market_name("CM-GA-02") == "Georgia market 2"
    assert plain_market_name("NO_CLUB_MARKET") == "Outside any club market"
