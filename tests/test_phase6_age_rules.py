"""Phase 6 (ADR-022): the age-tier rules are complete, documented, and no contact field sits where it should not."""
import csv
import re
from pathlib import Path

import duckdb
import pytest

from scripts import build_age_rules_doc

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = ROOT / "warehouse" / "flag.duckdb"
MAP = ROOT / "dbt" / "seeds" / "age_consent_jurisdiction_map.csv"


def _rules():
    return build_age_rules_doc.rows()


def test_every_rule_row_has_verified_set_and_the_open_items_are_documented():
    rs = _rules()
    assert rs and all(r["verified"] in {"Y", "N"} for r in rs)
    text = build_age_rules_doc.OUT.read_text(encoding="utf-8")
    assert text == build_age_rules_doc.render(), "run `make docs`"
    for j in {r["jurisdiction"] for r in rs if r["verified"] != "Y"}:
        assert f"**{j}**" in text


def test_every_jurisdiction_covers_every_age_without_gaps_or_overlaps():
    by: dict = {}
    for r in _rules():
        by.setdefault(r["jurisdiction"], []).append((int(r["age_min"]), int(r["age_max"])))
    for j, bands in by.items():
        bands.sort()
        assert bands[0][0] == 0, j
        for (lo1, hi1), (lo2, _) in zip(bands, bands[1:]):
            assert lo2 == hi1 + 1, f"{j}: bands {hi1} and {lo2} leave a gap or overlap"
        assert bands[-1][1] >= 100, j


def test_every_minor_row_is_guardian_only_and_forbids_profiling_and_disclosure():
    for r in _rules():
        if int(r["age_max"]) < 18:
            assert r["who_consents"] == "GUARDIAN", r["jurisdiction"]
            assert {"PROFILING", "PARTNER_DISCLOSURE"} <= set(r["prohibited_purposes"].split("|")), r["jurisdiction"]
            assert r["project_policy"] in {"Y", "N"}


def test_every_mapped_jurisdiction_has_rules_and_a_default_exists():
    with open(MAP, newline="", encoding="utf-8") as fh:
        mapped = {r["jurisdiction"] for r in csv.DictReader(fh)}
    have = {r["jurisdiction"] for r in _rules()}
    assert mapped <= have and "DEFAULT" in have


# Zones that hold identifying data by design. Everything else must carry no contact, name or exact birth-date VALUE column.
#   pipeline   raw, staging, intermediate: the sources as loaded and cleaned
#   identity   identity, marts: the participant master (dim_participant)
#   linkage    linkage (households, fan accounts, links), pii_store (the retention store)
#   restricted phase5_restricted, phase6_restricted, quality_restricted: working tables of the Phase 5 and 6 models
#   answer key eval: the synthetic ground truth, quarantined (CLAUDE.md); never read outside models/evaluation
RESTRICTED_ZONES = {"raw", "staging", "intermediate", "identity", "marts", "linkage", "pii_store", "phase5_restricted", "phase6_restricted", "quality_restricted", "eval"}
# Shares that carry identifiers on purpose, by audience policy (docs/access_policy.md): the guardian contact list (marketing), the cleared-photo roster (media), the ops audience.
BY_DESIGN = {("share_marketing", "share_marketing__contact_list"), ("share_media", "share_media__roster"), ("share_ops", "share_ops__participant"), ("share_ops", "share_ops__registration")}
IDENTIFYING = re.compile(r"email|phone|address|street|first_name|last_name|family_name|given_name|full_name|^dob$|birth_date|date_of_birth|^contact_")
NOT_A_VALUE = re.compile(r"contactable|contact_fields_held|email_present|email_wellformed|contact_role|_key$|^dob_(consistent|status|in_youth|precision|raw)|has_contact|_level$|_treatment$")


@pytest.mark.skipif(not WAREHOUSE.exists(), reason="needs a built warehouse (make all-phases)")
def test_no_identifying_value_column_sits_outside_the_restricted_zones_except_by_design():
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        rows = con.execute("select table_schema, table_name, column_name from information_schema.columns where table_schema not in ('information_schema', 'pg_catalog', 'main')").fetchall()
    except duckdb.Error as e:
        pytest.skip(f"warehouse not fully built: {e}")
    bad = sorted(f"{s}.{t}.{c}" for s, t, c in rows
                 if s not in RESTRICTED_ZONES and (s, t) not in BY_DESIGN and IDENTIFYING.search(c.lower()) and not NOT_A_VALUE.search(c.lower()))
    assert bad == [], bad
    cols = {c for s, t, c in rows if (s, t) == ("share_marketing", "share_marketing__contact_list")}
    assert "contact_role" in cols, "the marketing list must say whose contact it is"
    assert not any(re.search(r"participant|child|person|dob|birth|last_name", c.lower()) for c in cols), cols
    media = {c for s, t, c in rows if (s, t) == ("share_media", "share_media__roster")}
    assert not any(re.search(r"email|phone|address|dob|birth", c.lower()) for c in media), media          # names of cleared participants only: no contact detail, no birth date


def test_every_verified_row_carries_a_source_link_and_the_anchors_are_the_only_verified_rows():
    rs = _rules()
    for r in rs:
        if r["verified"] == "Y":
            assert r["source_url"].startswith("https://"), f"{r['jurisdiction']} {r['age_min']}-{r['age_max']}: a verified row needs a source link"
    anchors = {(r["jurisdiction"], r["age_min"], r["age_max"]) for r in rs if r["verified"] == "Y"}
    assert anchors == {("US_FED", "0", "12"), ("US_CA", "13", "15"), ("CA_QC", "0", "13"), ("EU", "0", "12"), ("EU", "13", "15")}
