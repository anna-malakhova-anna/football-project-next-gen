"""Build dbt/seeds/dq_rule_registry.csv: the ONE registry of data quality rules (phase-5-spec section 4.1, ADR-014).

  uv run python -m scripts.build_rule_registry           # rewrite the seed
  uv run python -m scripts.build_rule_registry --check   # exit 1 if the committed seed is out of date

Four origins, one table:
  PHASE1    every Phase 1 data-quality flag (dq_flag_severity) is checked by a registry rule: `not list_has_any(dq_flags, [...])` over dq_record_base. Flag treatment in the counting
            rules (AFFECTS_COUNT, MISSING_VALUE, NORMALIZED) stays in dq_flag_severity; the registry measures how often each flag fires. The two answer different questions (ADR-014).
  CONTRACT  every `quality:` rule of every contract (contracts/*.yml). Contracts keep owning schema, thresholds and validation (scripts/validate_contracts.py, quality.dq_contract_results);
            the registry row references the contract and its version and turns the contract's maximum violation rate into a minimum pass rate. No threshold is restated here: it is read.
  STANDARD  one INFO rule per field of the data standard (data_standard_fields): conformance of each source to the ask, measured by the validate_against_standard macro, never scored.
  PHASE5    rules the earlier phases did not have: the Phase 5 v1 rules that no Phase 1 flag covers, and the organization-level and consent-provenance rules.

Rules are data: `check_sql` is a SQL predicate over the columns of dq_record_base (record grain) or dq_org_season_base (ORG_SEASON grain): TRUE passes, FALSE fails, NULL = not applicable.
Thresholds are minimum pass rates per purpose; a blank means the rule does not apply to that purpose. Severity: ERROR = a record failing it is not fit for the purposes it lists
(dq_record_fitness); WARN = counted in the score only; INFO = measured and reported, never scored against a threshold.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "dbt" / "seeds" / "dq_rule_registry.csv"
PURPOSES = ["COUNT", "SEGMENT", "GEO", "RETAIN", "ACTIVATE"]
FIELDS = ["rule_id", "dimension", "applies_to", "grain", "check_sql", "purposes", *[f"threshold_{p}" for p in PURPOSES], "severity", "owner_role", "fix_guidance", "origin", "contract_ref", "plain_label", "plain_action"]

LEAGUE_OPS, DATA_LEAD, PRIVACY, PROGRAM = "League Ops, US", "Flag Football Data Lead", "Privacy Lead", "Program Insights Lead"


def flag_rule(rid, dim, flags, thresholds, severity, owner, fix, applies="dq_record_base.dq_flags"):
    """A Phase 1 flag rule: passes when none of the flags is present."""
    arr = "[" + ", ".join(f"'{f}'" for f in flags) + "]"
    return dict(rule_id=rid, dimension=dim, applies_to=applies, grain="RECORD", check_sql=f"not list_has_any(dq_flags, {arr})", thresholds=thresholds,
                severity=severity, owner_role=owner, fix_guidance=fix, origin="PHASE1")


def rec_rule(rid, dim, col, sql, thresholds, severity, owner, fix, origin="PHASE5", grain="RECORD"):
    return dict(rule_id=rid, dimension=dim, applies_to=col, grain=grain, check_sql=sql, thresholds=thresholds, severity=severity, owner_role=owner, fix_guidance=fix, origin=origin)


# --- PHASE1: one or more flags per rule; every flag in dq_flag_severity appears in exactly one rule (a test enforces it) -------------------------------------------------
PHASE1 = [
    flag_rule("DQ-UNIQ-EXACT-DUPLICATE", "UNIQUENESS", ["exact_duplicate", "pagination_overlap_duplicate"], dict(COUNT=0.98, RETAIN=0.98, ACTIVATE=0.98), "ERROR", DATA_LEAD,
              "Remove duplicated rows from the upload: the same registration was submitted or delivered twice."),
    flag_rule("DQ-UNIQ-NEAR-DUPLICATE", "UNIQUENESS", ["near_duplicate"], dict(COUNT=0.97), "WARN", LEAGUE_OPS,
              "The same player is registered twice in one league and season under different ids: keep one registration per player."),
    flag_rule("DQ-VAL-IMPOSSIBLE-DOB", "VALIDITY", ["impossible_dob"], dict(SEGMENT=0.98, RETAIN=0.98), "WARN", LEAGUE_OPS,
              "Correct the date of birth: it is in the future or implies an age over 80."),
    flag_rule("DQ-VAL-DOB-UNPARSEABLE", "VALIDITY", ["dob_unparseable"], dict(SEGMENT=0.98, RETAIN=0.98), "WARN", LEAGUE_OPS,
              "Send dates of birth as YYYY-MM-DD with a four-digit year: the value could not be read without guessing."),
    flag_rule("DQ-COMP-DOB-DIVISION-ONLY", "COMPLETENESS", ["dob_age_group_only"], dict(SEGMENT=0.95, RETAIN=0.95), "WARN", LEAGUE_OPS,
              "Collect a birth year: the file carries a division but no date of birth, so age bands and retention cannot be computed."),
    flag_rule("DQ-COMP-SEX", "COMPLETENESS", ["missing_gender"], dict(SEGMENT=0.90), "WARN", LEAGUE_OPS,
              "Collect gender (with a prefer-not-to-say option): girls' participation cannot be reported without it, and blanks are not random."),
    flag_rule("DQ-COMP-POSTAL", "COMPLETENESS", ["missing_zip"], dict(GEO=0.90, ACTIVATE=0.95), "WARN", LEAGUE_OPS,
              "Require a ZIP (at least the first three digits) on the registration form: without it a registration cannot be placed in a club market."),
    flag_rule("DQ-CONF-DIVISION-UNMAPPED", "CONFORMITY", ["unmapped_division"], dict(SEGMENT=0.99), "WARN", DATA_LEAD,
              "Use a division label from the standard list: the label is not in division_map."),
    flag_rule("DQ-CONF-GENDER-UNMAPPED", "CONFORMITY", ["unmapped_gender"], dict(SEGMENT=0.99), "WARN", DATA_LEAD,
              "Use M, F, X or U for gender: the value is not in gender_map."),
    flag_rule("DQ-CONF-COUNTRY-UNMAPPED", "CONFORMITY", ["unmapped_country"], dict(GEO=0.99), "WARN", DATA_LEAD,
              "Use an ISO country code: the value is not in country_map."),
    flag_rule("DQ-CONF-DIVISION-FREE-TEXT", "CONFORMITY", ["free_text_division"], dict(SEGMENT=0.95), "WARN", LEAGUE_OPS,
              "Pick the division from a list instead of typing it: spreadsheet labels map only to a coarse age band."),
    flag_rule("DQ-CONF-COUNTRY-VARIANT", "CONFORMITY", ["country_value_inconsistency"], dict(), "INFO", DATA_LEAD,
              "Use one spelling of the country on a sheet (repaired in staging through country_map)."),
    flag_rule("DQ-CONF-POSTAL-FORMAT", "CONFORMITY", ["zip_leading_zero_dropped", "postal_code_format"], dict(), "INFO", LEAGUE_OPS,
              "Store ZIPs and postal codes as text in the standard form (repaired in staging)."),
    flag_rule("DQ-CONF-EMAIL-FORMAT", "CONFORMITY", ["guardian_email_case_whitespace", "email_case_whitespace"], dict(), "INFO", LEAGUE_OPS,
              "Trim and lower-case emails at capture (repaired in staging)."),
    flag_rule("DQ-CONF-NAME-CASE", "CONFORMITY", ["all_caps_names"], dict(), "INFO", LEAGUE_OPS,
              "Capture names in normal case (repaired in staging)."),
    flag_rule("DQ-CONF-DOB-EXCEL-SERIAL", "CONFORMITY", ["uk_dob_excel_serial"], dict(), "INFO", LEAGUE_OPS,
              "Export dates as dates, not spreadsheet serial numbers (decoded in staging)."),
    flag_rule("DQ-COMP-CONSENT-PHOTO", "CONSENT_PROVENANCE", ["missing_photo_consent", "null_photo_media", "missing_media_consent"], dict(), "INFO", PRIVACY,
              "Capture photo and media consent as an explicit yes or no; a blank is recorded as not captured, never as no."),
    flag_rule("DQ-COMP-CONSENT-MARKETING", "CONSENT_PROVENANCE", ["missing_marketing_opt_in", "null_casl_marketing", "missing_consents_object"], dict(ACTIVATE=0.90), "WARN", PRIVACY,
              "Capture the marketing choice as an explicit yes or no on every registration; a household with no recorded choice cannot be contacted."),
    # --- flags from the aggregate and fan sources (Phase 4): measured by the same engine over their own record streams ---
    flag_rule("DQ-UNIQ-DUPLICATE-REPORT", "UNIQUENESS", ["duplicate_report", "duplicate_event", "duplicate_account"], dict(COUNT=0.95), "WARN", DATA_LEAD,
              "Report each programme year, event or account once.", applies="dq_record_base.dq_flags (school, fan)"),
    flag_rule("DQ-VAL-TOTAL-MISMATCH", "VALIDITY", ["total_mismatch", "round_number"], dict(COUNT=0.90), "WARN", DATA_LEAD,
              "Make the total equal girls plus boys, and send counted figures, not round estimates.", applies="dq_record_base.dq_flags (school)"),
    flag_rule("DQ-COMP-GRADE-BAND", "COMPLETENESS", ["missing_grade_band"], dict(SEGMENT=0.95), "WARN", DATA_LEAD,
              "Report the grade band of each programme.", applies="dq_record_base.dq_flags (school)"),
    flag_rule("DQ-TIME-LATE-OR-SKEWED", "TIMELINESS", ["late_arriving_event", "clock_skew"], dict(), "INFO", DATA_LEAD,
              "Deliver events in the month they happened.", applies="dq_record_base.dq_flags (fan)"),
    flag_rule("DQ-CONS-CONSENT-ORDER", "CONSISTENCY", ["consent_out_of_order", "refund_without_original"], dict(), "INFO", PRIVACY,
              "Timestamp consent changes in order; every refund must name its original transaction.", applies="dq_record_base.dq_flags (fan)"),
    flag_rule("DQ-STRUCT-JUNK-ROW", "CONFORMITY", ["junk_title_row", "junk_blank_row", "junk_summary_row", "junk_header_row"], dict(), "INFO", DATA_LEAD,
              "Send data rows only: no title, blank, header or total rows in a federation sheet (dropped in staging).", applies="dq_record_base.dq_flags (intl)"),
]

# --- PHASE5: new rules (the v1 rules that no Phase 1 flag covers, plus organization-level and consent provenance) -----------------------------------------------------
PHASE5 = [
    rec_rule("DQ-COMP-ORG-KNOWN", "COMPLETENESS", "dq_record_base.org_resolved", "org_resolved", dict(COUNT=0.98, GEO=0.98, ACTIVATE=0.98), "WARN", DATA_LEAD,
             "Send the canonical organization id with every registration: records that cannot be attributed to an organization cannot be fixed at the source."),
    rec_rule("DQ-COMP-AGE-SIGNAL", "COMPLETENESS", "dq_record_base.has_age_signal", "has_age_signal", dict(SEGMENT=0.90, RETAIN=0.90), "WARN", LEAGUE_OPS,
             "Collect a birth year, an age group or a grade: participation by age band cannot be reported without one."),
    rec_rule("DQ-COMP-EMAIL", "COMPLETENESS", "dq_record_base.email_present", "email_present", dict(ACTIVATE=0.95), "WARN", LEAGUE_OPS,
             "Collect one parent email: without it the household cannot be reached."),
    rec_rule("DQ-VAL-POSTAL-KNOWN", "VALIDITY", "dq_record_base.postal_known", "postal_known", dict(GEO=0.95, ACTIVATE=0.98), "WARN", LEAGUE_OPS,
             "Validate the ZIP on entry: it is not a known ZIP."),
    rec_rule("DQ-VAL-EMAIL-WELLFORMED", "VALIDITY", "dq_record_base.email_wellformed", "email_wellformed", dict(ACTIVATE=0.98), "WARN", LEAGUE_OPS,
             "Validate the email on entry: it is malformed and cannot be used."),
    rec_rule("DQ-UNIQ-CHILD-SEASON", "UNIQUENESS", "dq_record_base.is_first_of_person_season", "is_first_of_person_season", dict(COUNT=0.90, RETAIN=0.90, ACTIVATE=0.95), "WARN", DATA_LEAD,
             "The same child is registered more than once in a season term, here or through another channel: agree one registration channel per child."),
    rec_rule("DQ-TIME-REGISTERED-ON-TIME", "TIMELINESS", "dq_record_base.registered_late", "not registered_late", dict(COUNT=0.90), "WARN", LEAGUE_OPS,
             "Register players before the season starts: late registrations arrive after the data cut."),
    rec_rule("DQ-CONS-DOB-AGREES", "CONSISTENCY", "dq_record_base.dob_consistent", "dob_consistent", dict(SEGMENT=0.98, RETAIN=0.98), "WARN", DATA_LEAD,
             "The child's date of birth differs between registrations: reconcile with the parent."),
    rec_rule("DQ-CONS-SEX-AGREES", "CONSISTENCY", "dq_record_base.sex_consistent", "sex_consistent", dict(SEGMENT=0.98), "WARN", DATA_LEAD,
             "The child's gender differs between registrations."),
    rec_rule("DQ-CONS-POSTAL-AGREES", "CONSISTENCY", "dq_record_base.zip3_consistent", "zip3_consistent", dict(GEO=0.95), "WARN", DATA_LEAD,
             "The home ZIP differs between registrations: confirm the family's address."),
    rec_rule("DQ-CONS-AGE-GROUP-AGREES", "CONSISTENCY", "dq_record_base.age_group_consistent", "age_group_consistent", dict(SEGMENT=0.98), "WARN", DATA_LEAD,
             "The age group contradicts the child's date of birth in another registration."),
    rec_rule("DQ-TIME-ORG-REPORTED", "TIMELINESS", "dq_org_season_base.reported", "reported", dict(COUNT=0.90, SEGMENT=0.90, GEO=0.90, RETAIN=0.90, ACTIVATE=0.90), "WARN", PROGRAM,
             "This organization sent no file this season: its players are missing from every count.", grain="ORG_SEASON"),
    rec_rule("DQ-PROV-CONSENT-RECORDED", "CONSENT_PROVENANCE", "dq_record_base.consent_recorded", "consent_recorded", dict(ACTIVATE=0.90), "WARN", PRIVACY,
             "Record a consent with every registration: without one nobody knows what the parent agreed to."),
    rec_rule("DQ-PROV-CONSENT-WORDING", "CONSENT_PROVENANCE", "dq_record_base.consent_version_known", "consent_version_known", dict(ACTIVATE=0.90), "WARN", PRIVACY,
             "Record which consent wording (version) the parent saw."),
    rec_rule("DQ-PROV-CONSENT-TIMESTAMP", "CONSENT_PROVENANCE", "dq_record_base.consent_ts_known", "consent_ts_known", dict(ACTIVATE=0.90), "WARN", PRIVACY,
             "Record when consent was given."),
    rec_rule("DQ-PROV-MARKETING-PURPOSE-COVERED", "CONSENT_PROVENANCE", "dq_record_base.marketing_form_covers_purpose", "marketing_form_covers_purpose", dict(ACTIVATE=0.98), "ERROR", PRIVACY,
             "A marketing opt-in was recorded on a form whose wording has no club-marketing purpose: it is not evidence of that consent. Use a form that names the purpose."),
]

# which purposes a contract rule column serves (a transparent mapping; the contract itself says nothing about purposes)
CONTRACT_PURPOSES = [(r"dob|birth|date_of_birth", ["SEGMENT", "RETAIN"]), (r"zip|postal", ["GEO"]), (r"email|phone", ["ACTIVATE"]),
                     (r"consent|marketing|photo|media|casl", []), (r"registration_id|uuid|player_id|key|account", ["COUNT"])]


def contract_rules() -> list[dict]:
    out = []
    for path in sorted((ROOT / "contracts").glob("*.yml")):
        if path.name.startswith("_"):
            continue
        c = yaml.safe_load(path.read_text(encoding="utf-8"))
        for q in c.get("quality") or []:
            rule, column = q["rule"], q.get("column") or q.get("name") or ",".join(q.get("key") or [])
            if rule not in ("max_null_rate", "max_nonmatching_rate", "max_invalid_rate", "max_duplicate_rate", "max_expression_rate"):
                continue
            purposes = next((p for pat, p in CONTRACT_PURPOSES if re.search(pat, column.lower())), ["COUNT"])
            dim = {"max_null_rate": "COMPLETENESS", "max_nonmatching_rate": "VALIDITY", "max_invalid_rate": "VALIDITY", "max_duplicate_rate": "UNIQUENESS", "max_expression_rate": "CONSISTENCY"}[rule]
            if "consent" in column.lower() or "marketing" in column.lower() or "casl" in column.lower():
                dim = "CONSENT_PROVENANCE"
            out.append(dict(rule_id=f"DQ-CTR-{path.stem.upper()}-{rule.replace('max_', '').replace('_rate', '').upper()}-{re.sub('[^A-Za-z0-9]+', '-', column).strip('-').upper()}",
                            dimension=dim, applies_to=f"{c.get('raw', {}).get('table', c['source_system'])}.{column}", grain="SOURCE_SEASON", check_sql="",
                            thresholds={p: round(1 - float(q["threshold"]), 4) for p in purposes}, severity=(q.get("severity", "WARN") if purposes else "INFO"), owner_role=c.get("owner_role", DATA_LEAD),
                            fix_guidance=f"The contract limits {rule.replace('_', ' ')} on {column} to {float(q['threshold']):.0%}: bring the partner's file within it.",
                            origin="CONTRACT", contract_ref=f"{c['source_system']}|{path.stem.split('__')[1] if '__' in path.stem else ''}@{c['version']}#{rule}:{column}"))
    return out


def standard_rules() -> list[dict]:
    """One INFO rule per field of the data standard (seed data_standard_fields): conformance of a source to the ASK, measured by the validate_against_standard macro and reported in
    dq_rule_results with origin STANDARD. INFO, so it is never scored into a purpose score (a missing ZIP would count twice: here and in DQ-COMP-POSTAL)."""
    out = []
    with open(ROOT / "dbt" / "seeds" / "data_standard_fields.csv", newline="", encoding="utf-8") as fh:
        for f in csv.DictReader(fh):
            out.append(dict(rule_id="DQ-STD-" + f["field_name"].upper().replace("_", "-"), dimension="CONFORMITY", applies_to=f"dq_standardized_records.{f['field_name']}",
                            grain="ORG_SEASON", check_sql="", thresholds={}, severity="INFO", owner_role=DATA_LEAD,
                            fix_guidance=f"Send {f['field_name']}: {f['definition'].rstrip('.')} ({f['format']}). {f['requirement'].title()} in the data standard.", origin="STANDARD"))
    return out


PLAIN = ROOT / "config" / "rule_plain_text.csv"


def _words(text: str, n: int) -> str:
    return " ".join(re.sub(r"[^A-Za-z0-9 ]+", " ", text.split(".")[-1].replace("_", " ")).split()[:n]).lower()


def plain_text(r: dict, hand: dict) -> tuple[str, str]:
    """Plain label (<= 6 words) and action (<= 15 words, starts with a verb) for the site. Hand-written for the rules people act on (config/rule_plain_text.csv); templated for the
    contract and data-standard rules, which only appear in analyst detail."""
    if r["rule_id"] in hand:
        return hand[r["rule_id"]]
    m = re.search(r"#(max_[a-z_]+):", r.get("contract_ref", ""))
    rule = m.group(1) if m else ""
    if r["origin"] == "CONTRACT":
        if rule == "max_expression_rate":
            col = _words(r["applies_to"], 5)
            return col.capitalize(), f"Fix the rows that fail this check: {col}."
        col = _words(r["applies_to"], 3)
        label = {"max_null_rate": f"{col} often blank", "max_nonmatching_rate": f"{col} in wrong format", "max_invalid_rate": f"{col} has odd values",
                 "max_duplicate_rate": f"duplicate {col}"}.get(rule, f"{col} outside agreed limit")
        return label.capitalize(), f"Bring {col} within the limit agreed with the partner."
    if r["origin"] == "STANDARD":
        col = _words(r["applies_to"], 3)
        return f"{col} off standard".capitalize(), f"Send {col} as the data standard asks."
    raise KeyError(r["rule_id"])


def all_rules() -> list[dict]:
    rules = PHASE1 + PHASE5 + contract_rules() + standard_rules()
    rows = []
    for r in rules:
        th = r.pop("thresholds")
        purposes = [p for p in PURPOSES if p in th]
        rows.append({**{f: "" for f in FIELDS}, **r, "purposes": "|".join(purposes), **{f"threshold_{p}": th[p] for p in purposes}})
    with open(PLAIN, newline="", encoding="utf-8") as fh:
        hand = {x["rule_id"]: (x["plain_label"], x["plain_action"]) for x in csv.DictReader(fh)}
    for r in rows:
        r["plain_label"], r["plain_action"] = plain_text(r, hand)
    ids = [r["rule_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate rule ids"
    return rows


def render() -> str:
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writeheader()
    w.writerows(all_rules())
    return buf.getvalue()


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv:
        sys.exit(0 if SEED.exists() and SEED.read_text(encoding="utf-8") == text else 1)
    SEED.write_text(text, encoding="utf-8")
    print(f"{len(text.splitlines()) - 1} rules written to {SEED.relative_to(ROOT)}")
