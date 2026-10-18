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


@pytest.mark.skipif(not WAREHOUSE.exists(), reason="needs a built warehouse (make all-phases)")
def test_no_contact_field_sits_in_a_share_or_a_reporting_mart_except_the_guardian_contact_list():
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        rows = con.execute("""select table_schema, table_name, column_name from information_schema.columns
                              where table_schema like 'share\\_%' escape '\\' or table_schema in ('measurement', 'facts', 'retention', 'audit_share_policy', 'published')""").fetchall()
    except duckdb.Error as e:
        pytest.skip(f"warehouse not fully built: {e}")
    contact = re.compile(r"email|phone|address|street|^contact_")
    bad = [f"{s}.{t}.{c}" for s, t, c in rows
           if contact.search(c.lower()) and not re.search(r"contactable|contact_fields_held|email_present|email_wellformed|contact_role", c.lower())
           and not (s == "share_marketing" and t == "share_marketing__contact_list")
           and s != "share_ops"]
    assert bad == [], bad
    cols = {c for s, t, c in rows if (s, t) == ("share_marketing", "share_marketing__contact_list")}
    assert "contact_role" in cols, "the marketing list must say whose contact it is"
    assert not any(re.search(r"participant|child|person|dob|birth|last_name", c.lower()) for c in cols), cols
