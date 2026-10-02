"""Export configured defect-injection rates to dbt/seeds/dq_defect_config.csv.

dq_summary compares OBSERVED defect rates (from the SQL pipeline) with these CONFIGURED rates
(from config/generation.yaml). The catalog below adds, per defect: how the rate is defined
(denominator), whether Phase 1 SQL can detect it, and a rule description for dq_defect_log.
Every defect in the config must have a catalog entry (tests/test_config_seed.py enforces this).
"""
from __future__ import annotations

import csv
from pathlib import Path

from generator.population import load_config

# (source_system, defect_id, kind, denominator_kind, denominator_description, detectable, rule_description)
#   kind: rate (configured rate), structural (configured exact count), zero (nothing injected; expect 0)
ROWS, REREG, ZIP, CONSENTS, UK = "rows", "reregistrations", "zip_eligible_rows", "rows_with_consents_object", "uk_rows"
CATALOG = [
    # ---- US_LEAGUE ----
    ("US_LEAGUE", "name_typo_reregistration", "rate", REREG, "re-registrations", False,
     "Name has a one-character typo on a re-registration. Needs identity matching to see (Phase 2)."),
    ("US_LEAGUE", "nickname_reregistration", "rate", REREG, "re-registrations (drawn only from people who have a nickname)", False,
     "Nickname used instead of given name on a re-registration. Needs identity matching (Phase 2)."),
    ("US_LEAGUE", "exact_duplicate", "rate", ROWS, "all rows", True,
     "Row is byte-identical to an earlier row in the same file (double submit)."),
    ("US_LEAGUE", "near_duplicate", "rate", ROWS, "all rows", True,
     "Same name keys, league and season as an earlier row but a different registration_id and timestamp."),
    ("US_LEAGUE", "impossible_dob", "rate", ROWS, "all rows", True,
     "Age at the Dec 31 cutoff is below 0 (future DOB) or above 80."),
    ("US_LEAGUE", "dob_day_month_swapped", "rate", ROWS, "all rows", False,
     "Day and month of the DOB are swapped but the date is still plausible. Not detectable in isolation."),
    ("US_LEAGUE", "guardian_email_case_whitespace", "rate", ROWS, "all rows", True,
     "Guardian email differs from its lowercased, trimmed form."),
    ("US_LEAGUE", "guardian_email_changed_between_seasons", "rate", REREG, "re-registrations", False,
     "Guardian email differs from the person's earlier registration. Needs identity matching (Phase 2)."),
    ("US_LEAGUE", "missing_gender", "rate", ROWS, "all rows", True, "player_gender is blank (mapped to U)."),
    ("US_LEAGUE", "missing_photo_consent", "rate", ROWS, "all rows", True,
     "photo_consent is blank: not captured (NULL), never FALSE."),
    ("US_LEAGUE", "missing_marketing_opt_in", "rate", ROWS, "all rows", True,
     "marketing_opt_in is blank: not captured (NULL), never FALSE."),
    ("US_LEAGUE", "zip_leading_zero_dropped", "rate", ZIP, "zips that start with 0 (including those that lost it)", True,
     "ZIP has 4 digits: a leading zero was dropped upstream and is restored in staging."),
    ("US_LEAGUE", "unmapped_division", "zero", ROWS, "all rows", True, "Division label is missing from division_map."),
    ("US_LEAGUE", "unmapped_gender", "zero", ROWS, "all rows", True, "Non-blank gender value missing from gender_map."),
    ("US_LEAGUE", "dob_unparseable", "zero", ROWS, "all rows", True, "DOB is blank, ambiguous or not a real date."),
    # ---- CA_CLUB ----
    ("CA_CLUB", "accents_stripped", "rate", "accented_records", "records whose participant name has an accent", False,
     "Accents removed from a name (Élodie -> Elodie). The original is unknown, so not detectable."),
    ("CA_CLUB", "all_caps_names", "rate", ROWS, "all records", True, "Participant family name is entirely upper case."),
    ("CA_CLUB", "postal_code_format", "rate", ROWS, "all records", True,
     "Postal code is not in the standard 'A1A 1A1' form (lowercase or no space)."),
    ("CA_CLUB", "missing_consents_object", "rate", ROWS, "all records", True,
     "The record has no consents object: consent not captured (NULL)."),
    ("CA_CLUB", "pagination_overlap_duplicate", "rate", ROWS, "all records", True,
     "Record is identical to one already seen on an earlier API page."),
    ("CA_CLUB", "birth_year_off_by_one", "rate", ROWS, "all records", False,
     "Birth year is one year off the truth. Not detectable without a second source."),
    ("CA_CLUB", "null_photo_media", "rate", CONSENTS, "records that have a consents object", True,
     "consents.photo_media is null: not captured (NULL)."),
    ("CA_CLUB", "null_casl_marketing", "rate", CONSENTS, "records that have a consents object", True,
     "consents.casl_marketing is null: not captured (NULL)."),
    ("CA_CLUB", "unmapped_division", "zero", ROWS, "all records", True, "Program label is missing from division_map."),
    ("CA_CLUB", "unmapped_gender", "zero", ROWS, "all records", True, "Sex value missing from gender_map."),
    ("CA_CLUB", "dob_unparseable", "zero", ROWS, "all records", True, "birth_year is not a 4-digit year."),
    # ---- INTL_FED ----
    ("INTL_FED", "uk_dob_excel_serial", "rate", UK, "rows on the United Kingdom sheets", True,
     "Date of birth is an Excel date serial instead of a DD/MM/YYYY string (decoded in staging)."),
    ("INTL_FED", "country_value_inconsistency", "rate", ROWS, "all rows", True,
     "Country spelling differs from the dominant spelling on its sheet (MEX / Mexico / MX)."),
    ("INTL_FED", "missing_media_consent", "rate", ROWS, "all rows", True,
     "Media Consent is blank: not captured (NULL)."),
    ("INTL_FED", "junk_title_row", "structural", "structural", "title rows above the header (DE, AT)", True,
     "Worksheet title row above the header; dropped in staging."),
    ("INTL_FED", "junk_blank_row", "structural", "structural", "blank rows above the header (DE, AT)", True,
     "Blank row between title and header; dropped in staging."),
    ("INTL_FED", "junk_summary_row", "structural", "structural", "trailing 'Total: N' rows", True,
     "Trailing summary row ('Total: N'); dropped in staging."),
    ("INTL_FED", "junk_header_row", "structural", "structural", "one header row per sheet", True,
     "The column header row, landed as data by the raw loader; dropped in staging."),
    ("INTL_FED", "name_order_inverted", "structural", "structural", "all rows on family-name-first sheets (JP)", False,
     "Family name precedes given name (Japan). Handled by sheet rule in staging; a configuration, not a data signal."),
    ("INTL_FED", "family_name_change", "structural", "structural", "records of adult women after a change of family name", False,
     "Family name differs from the same player's earlier registrations, and a new Player ID is issued. Needs identity matching (Phase 2)."),
    ("INTL_FED", "player_id_reissued", "structural", "structural", "all rows on unstable-ID sheets (PA)", False,
     "Player ID is reissued each year (Panama). Needs identity matching to see (Phase 2)."),
    ("INTL_FED", "unmapped_division", "zero", ROWS, "all rows", True, "Category label is missing from division_map."),
    ("INTL_FED", "unmapped_gender", "zero", ROWS, "all rows", True, "Gender value missing from gender_map."),
    ("INTL_FED", "unmapped_country", "zero", ROWS, "all rows", True, "Country value missing from country_map."),
    ("INTL_FED", "dob_unparseable", "zero", ROWS, "all rows", True, "DOB is blank, ambiguous or not a real date."),
    ("INTL_FED", "exact_duplicate", "zero", ROWS, "all rows", True, "Row is identical to an earlier row on the same sheet."),
    # flags that can appear on any source but are never injected
    ("CA_CLUB", "impossible_dob", "zero", ROWS, "all records", True, "Age at the Dec 31 cutoff is below 0 or above 80."),
    ("INTL_FED", "impossible_dob", "zero", ROWS, "all rows", True, "Age at the Dec 31 cutoff is below 0 or above 80."),
]
SOURCE_KEY = {"US_LEAGUE": "us_league", "CA_CLUB": "ca_club", "INTL_FED": "intl_federation"}
COLUMNS = ["source_system", "defect_id", "kind", "configured_rate", "configured_count", "denominator_kind",
           "denominator_description", "detectable_phase1", "rule_description"]


def _structural_count(cfg: dict, defect_id: str) -> int | None:
    sc, years = cfg["sources"]["intl"], len(cfg["seasons"]["years"])
    return {
        "junk_title_row": len(sc["sheets_with_title_rows"]) * years,
        "junk_blank_row": len(sc["sheets_with_title_rows"]) * years,
        "junk_summary_row": len(sc["sheets_with_summary_row"]) * years,
        "junk_header_row": 6 * years,   # one sheet per country (6) per season workbook
    }.get(defect_id)


def build_rows(cfg: dict) -> list[dict]:
    rows = []
    for source, defect, kind, dkind, ddesc, detectable, rule in CATALOG:
        rate = count = None
        if kind == "rate":
            rate = cfg["defects"][SOURCE_KEY[source]][defect]
        elif kind == "zero":
            rate = 0.0
        else:
            count = _structural_count(cfg, defect)
        rows.append({"source_system": source, "defect_id": defect, "kind": kind,
                     "configured_rate": "" if rate is None else rate,
                     "configured_count": "" if count is None else count,
                     "denominator_kind": dkind, "denominator_description": ddesc,
                     "detectable_phase1": str(detectable).lower(), "rule_description": rule})
    return rows


def main(cfg: dict | None = None, out: str = "dbt/seeds/dq_defect_config.csv") -> int:
    cfg = cfg or load_config()
    rows = build_rows(cfg)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    print(f"wrote {main()} rows to dbt/seeds/dq_defect_config.csv")
