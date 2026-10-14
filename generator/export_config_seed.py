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
    ("US_LEAGUE", "missing_zip", "rate", ROWS, "all rows", True,
     "ZIP is blank. Placed with weights: likelier where the organization's registration form does not require a ZIP (missing not at random)."),
    ("US_LEAGUE", "dob_age_group_only", "rate", ROWS, "all rows", True,
     "DOB is blank and only the division gives an age band. Whole MANUAL organizations, chosen so their row mass is closest to the configured share, so the observed rate is approximate."),
    ("US_LEAGUE", "free_text_division", "rate", ROWS, "all rows", True,
     "Division is a spreadsheet label (Littles, Middle kids, Teens, Open) from a MANUAL organization; mapped in division_map to a coarser band."),
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
    # ---- SCHOOL_AGGREGATES (aggregate headcounts: program x year) ----
    ("SCHOOL_AGGREGATES", "total_mismatch", "rate", ROWS, "all rows", True,
     "total_count differs from girls_count + boys_count."),
    ("SCHOOL_AGGREGATES", "missing_grade_band", "rate", ROWS, "all rows", True, "grade_band is blank."),
    ("SCHOOL_AGGREGATES", "duplicate_report", "rate", ROWS, "all rows", True,
     "The same program-year was reported by two different reporters; one report is kept (the latest)."),
    ("SCHOOL_AGGREGATES", "round_number", "rate", ROWS, "all rows", True,
     "total_count is a suspiciously round number (100, 150, 200, 250, 300): possibly an estimate, not a count."),
    ("SCHOOL_AGGREGATES", "unmapped_program_type", "zero", ROWS, "all rows", True, "program_type is not PE_UNIT, INTRAMURAL or AFTER_SCHOOL."),
    ("SCHOOL_AGGREGATES", "unmapped_country", "zero", ROWS, "all rows", True, "country is not an ISO 3166-1 alpha-2 code in country_map."),
    # ---- FAN_ENGAGEMENT (accounts, consent events, engagement events, transactions) ----
    ("FAN_ENGAGEMENT", "duplicate_event", "rate", "events", "all delivered event lines", True,
     "The same event_id was delivered twice; only the first delivery is counted."),
    ("FAN_ENGAGEMENT", "late_arriving_event", "rate", "events", "all delivered event lines", True,
     "The event landed in a later month's file than its event_ts; it is counted in the month of event_ts."),
    ("FAN_ENGAGEMENT", "clock_skew", "rate", "events", "all delivered event lines", False,
     "event_ts is shifted by up to two days (a device clock error); not recoverable from the data, so not detected."),
    ("FAN_ENGAGEMENT", "email_case_whitespace", "rate", "accounts", "all accounts", True,
     "Account email has capitals or surrounding spaces; normalized in staging."),
    ("FAN_ENGAGEMENT", "email_differs_from_registration", "rate", "participant_accounts", "accounts that belong to a participant household", False,
     "The account email is not the guardian's registration email. Needs the household linkage to see."),
    ("FAN_ENGAGEMENT", "phone_shared_with_participant_household", "rate", "accounts", "accounts that carry a phone", False,
     "The account phone number is a participant household's number: a false-link hazard for phone matching. Needs ground truth to see."),
    ("FAN_ENGAGEMENT", "duplicate_account", "rate", "accounts", "all accounts", True,
     "The household opened a second account (same email, or the same phone and postal prefix). Collapsed in dim_fan_account. International phone numbers are not normalized, so a duplicate matched only by one is missed."),
    ("FAN_ENGAGEMENT", "refund_without_original", "rate", "transactions", "all non-refund transactions", True,
     "A refund whose original_txn_id matches no transaction. Excluded from revenue and counted here, never repaired."),
    ("FAN_ENGAGEMENT", "consent_out_of_order", "rate", "consent_pairs", "preference-centre opt-outs (each follows an opt-in)", True,
     "A preference-centre opt-out with no earlier opt-in on that account and channel: its timestamp predates the opt-in it follows. Resolved by timestamp and flagged."),
    ("FAN_ENGAGEMENT", "duplicate_txn", "zero", "transactions", "all transaction lines", True, "The same txn_id was delivered twice."),
    ("FAN_ENGAGEMENT", "orphan_transaction", "zero", "transactions", "all transaction lines", True, "The transaction's account_id is not in the accounts snapshot."),
    ("FAN_ENGAGEMENT", "unmapped_txn_category", "zero", "transactions", "all transaction lines", True, "category is not ticket, merch, subscription or other."),
    ("FAN_ENGAGEMENT", "non_numeric_amount", "zero", "transactions", "all transaction lines", True, "amount is not a number."),
    ("FAN_ENGAGEMENT", "orphan_consent_event", "zero", "consent_pairs", "all consent lines", True, "The consent line's account_id is not in the accounts snapshot."),
    ("FAN_ENGAGEMENT", "unmapped_consent_value", "zero", "consent_pairs", "all consent lines", True, "status, channel or capture_point is not one of the contract's values."),
    ("FAN_ENGAGEMENT", "unmapped_event_type", "zero", "events", "all delivered event lines", True, "event_type is not one of the six known engagement event types."),
    ("FAN_ENGAGEMENT", "orphan_event", "zero", "events", "all delivered event lines", True, "The event's account_id is not in the accounts snapshot."),
    # flags that can appear on any source but are never injected
    ("CA_CLUB", "impossible_dob", "zero", ROWS, "all records", True, "Age at the Dec 31 cutoff is below 0 or above 80."),
    ("INTL_FED", "impossible_dob", "zero", ROWS, "all rows", True, "Age at the Dec 31 cutoff is below 0 or above 80."),
]
SOURCE_KEY = {"US_LEAGUE": "us_league", "CA_CLUB": "ca_club", "INTL_FED": "intl_federation", "SCHOOL_AGGREGATES": "school_aggregates", "FAN_ENGAGEMENT": "fan"}
COLUMNS = ["source_system", "defect_id", "kind", "configured_rate", "configured_count", "denominator_kind",
           "denominator_description", "detectable_phase1", "rule_description"]


def _structural_count(cfg: dict, defect_id: str) -> int | None:
    """Expected counts of the structural international defects. A country has a worksheet only in the years its market has launched (and so has registrations):
    one sheet per country per season workbook from the launch year on."""
    sc = cfg["sources"]["intl"]
    years = cfg["seasons"]["years"]
    launch = cfg["markets"]["intl_launch_years"]
    sheet_years = {c: sum(1 for y in years if y >= int(launch[c])) for c in launch}
    title = sum(sheet_years[c] for c in sc["sheets_with_title_rows"])
    return {
        "junk_title_row": title,
        "junk_blank_row": title,
        "junk_summary_row": sum(sheet_years[c] for c in sc["sheets_with_summary_row"]),
        "junk_header_row": sum(sheet_years.values()),
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


def window_rows(cfg: dict) -> list[dict]:
    years = cfg["seasons"]["years"]
    first = cfg["seasons"]["first_observed_year"]
    if first != years[0] or years != list(range(years[0], years[-1] + 1)):
        raise ValueError(f"seasons.first_observed_year ({first}) must equal the first of a contiguous years list {years}")
    return [{"first_observed_year": first, "last_observed_year": years[-1]}]


def period_rows(cfg: dict) -> list[dict]:
    """Participation years (calendar) and US seasons, with the December 31 age cutoff (ADR-002)."""
    rows = []
    for y in cfg["seasons"]["years"]:
        rows.append((f"Y{y}", "YEAR", y, "ANNUAL", f"{y}-01-01", f"{y}-12-31", f"{y}-12-31"))
        rows.append((f"Y{y}-SPRING", "US_SEASON", y, "SPRING", f"{y}-01-01", f"{y}-05-31", f"{y}-12-31"))
        rows.append((f"Y{y}-FALL", "US_SEASON", y, "FALL", f"{y}-06-01", f"{y}-12-31", f"{y}-12-31"))
    keys = ["period_id", "period_type", "participation_year", "term", "start_date", "end_date", "cutoff_date"]
    return [dict(zip(keys, r)) for r in rows]


def _write(path: str, fieldnames: list[str], rows: list[dict]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def market_rows(cfg: dict) -> tuple[list[dict], list[dict]]:
    """market_map and market_geo_map, from the same function the population generator uses (generator/markets.py): they cannot disagree."""
    from generator import markets
    built = markets.build_markets(cfg)
    mm = [{"market_id": m["market_id"], "market_name": m["market_name"], "country_code": m["country_code"], "region_code": m["region_code"],
           "is_team_market": "Y" if m["is_team_market"] else "N", "household_population": m["household_population"],
           "launch_year": "" if m["launch_year"] is None else m["launch_year"], "notes": m["notes"]} for m in built["markets"]]
    return mm, built["geo"]


def main(cfg: dict | None = None, out: str = "dbt/seeds/dq_defect_config.csv") -> int:
    cfg = cfg or load_config()
    seeds = Path(out).parent
    mm, geo = market_rows(cfg)
    _write(str(seeds / "market_map.csv"), ["market_id", "market_name", "country_code", "region_code", "is_team_market", "household_population", "launch_year", "notes"], mm)
    _write(str(seeds / "market_geo_map.csv"), ["country_code", "prefix", "market_id"], geo)
    _write(str(seeds / "observation_window.csv"), ["first_observed_year", "last_observed_year"], window_rows(cfg))
    _write(str(seeds / "reporting_periods.csv"), ["period_id", "period_type", "participation_year", "term", "start_date", "end_date", "cutoff_date"], period_rows(cfg))
    rows = build_rows(cfg)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    print(f"wrote {main()} rows to dbt/seeds/dq_defect_config.csv")
