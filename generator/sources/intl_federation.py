"""Source C: international federation returns (XLSX, one workbook per season, one sheet per country).
SYNTHETIC data.

Grain: one row per registered player per season. A record is identified by
(Player ID, season): truth/manifest `source_record_id` is "<Player ID>|<season_year>".

Structural defects (config `sources.intl`): title row + blank row above the header (DE, AT),
trailing "Total: N" row on some sheets, Japanese sheet gives family name first, Panama reissues
Player IDs every year. Rate defects: UK DOB as Excel serial (20% of UK DOBs), inconsistent Country
values (25% of rows). Minors' email is usually blank. Rate denominators are all rows on the sheet
(UK DOB) or all rows (country, media consent).
"""
from __future__ import annotations

import datetime as dt
import random
import re
import shutil
import zipfile
from pathlib import Path

from openpyxl import Workbook

from generator import defects as D
from generator import profiles as P

SOURCE = "INTL_FED"
COLUMNS = ["Player ID", "Full Name", "Date of Birth", "Gender", "Category", "Club", "Country", "Email", "Media Consent"]
COUNTRY_ORDER = ["MX", "GB", "JP", "DE", "AT", "PA"]
SHEET_NAME = {"MX": "Mexico", "GB": "United Kingdom", "JP": "Japan", "DE": "Germany", "AT": "Austria", "PA": "Panama"}
ISO3 = {"MX": "MEX", "GB": "GBR", "JP": "JPN", "DE": "DEU", "AT": "AUT", "PA": "PAN"}
# Alternative Country spellings used by the 25% inconsistency defect (base spelling is ISO-3).
COUNTRY_ALT = {
    "MX": ["MX", "Mexico", "México"], "GB": ["GB", "United Kingdom", "UK"], "JP": ["JP", "Japan", "Nippon"],
    "DE": ["DE", "Germany", "Deutschland"], "AT": ["AT", "Austria", "Österreich"], "PA": ["PA", "Panama", "Panamá"],
}
GENDER_LABELS = {  # per sheet: (F label, M label)
    "MX": ("Mujer", "Hombre"), "PA": ("Mujer", "Hombre"), "GB": ("F", "M"),
    "JP": ("F", "M"), "DE": ("W", "M"), "AT": ("W", "M"),
}
# Category labels per country. Seeds must map every label; notes on boundaries live in division_map.
CATEGORY_LABELS = {
    "default": {"U8": "U8", "U10": "U10", "U12": "U12", "U14": "U15", "U17": "Juniors",
                "ADULT_W": "Senior Women", "ADULT_M": "Senior Men", "ADULT_MIXED": "Masters"},
    "MX": {"U17": "Juvenil", "ADULT_W": "Senior Femenil", "ADULT_M": "Senior Varonil"},
    "PA": {"U17": "Juvenil", "ADULT_W": "Senior Femenil", "ADULT_M": "Senior Varonil"},
    "DE": {"U17": "Junioren", "ADULT_W": "Damen", "ADULT_M": "Herren"},
    "AT": {"U17": "Junioren", "ADULT_W": "Damen", "ADULT_M": "Herren"},
}
CLUB_PLACES = {
    "MX": ["CDMX", "Guadalajara", "Monterrey", "Puebla", "Querétaro", "Mérida"],
    "GB": ["London", "Manchester", "Glasgow", "Bristol", "Leeds", "Cardiff"],
    "JP": ["Tokyo", "Osaka", "Nagoya", "Fukuoka", "Sapporo", "Kobe"],
    "DE": ["Berlin", "Hamburg", "München", "Köln", "Frankfurt", "Dresden"],
    "AT": ["Wien", "Graz", "Linz", "Salzburg", "Innsbruck"],
    "PA": ["Panamá", "Colón", "David", "Chitré"],
}
CLUB_STYLES = ["{p} Flag Club", "{p} Titans", "Club Flag {p}", "{p} Vipers"]
EXCEL_EPOCH = dt.date(1899, 12, 30)


def _category(rng: random.Random, country: str, age: int, sex: str) -> str:
    if age >= 18:
        key = "ADULT_MIXED" if (age >= 40 and rng.random() < 0.7) else ("ADULT_W" if sex == "F" else "ADULT_M")
    else:
        key = "U8" if age <= 7 else "U10" if age <= 9 else "U12" if age <= 11 else "U14" if age <= 14 else "U17"
    labels = {**CATEGORY_LABELS["default"], **CATEGORY_LABELS.get(country, {})}
    return labels[key]


def generate(people: list[dict], parts: list[dict], cfg: dict) -> D.SourceOutput:
    rng = random.Random(cfg["seed"] + 3)
    rates = cfg["defects"]["intl_federation"]
    sc = cfg["sources"]["intl"]
    by_id = {p["true_person_id"]: p for p in people}
    plan = sorted((r for r in parts if r["source_system"] == SOURCE), key=lambda r: (r["season_year"], r["true_person_id"]))
    clubs = {c: [t.format(p=p) for p, t in zip(places, CLUB_STYLES * 3)] for c, places in CLUB_PLACES.items()}

    # ---- 1. Player IDs: federation-local number, issued in shuffled order per country-year ----
    first_year: dict[str, int] = {}
    for r in plan:
        first_year.setdefault(r["true_person_id"], r["season_year"])

    def id_year(p: dict, year: int, country: str) -> int:
        """Year in which the ID shown for this player-season was issued."""
        if country in sc["unstable_player_id_sheets"]:
            return year                                  # reissued every year
        if p["name_change_season"] and year >= p["name_change_season"]:
            return p["name_change_season"]               # new ID when she re-registers under a new name
        return first_year[p["true_person_id"]]

    issued: dict[tuple, int] = {}
    for year in cfg["seasons"]["years"]:
        for c in COUNTRY_ORDER:
            needs = [r["true_person_id"] for r in plan
                     if r["season_year"] == year and r["country_code"] == c
                     and id_year(by_id[r["true_person_id"]], year, c) == year]
            rng.shuffle(needs)
            for n, pid in enumerate(needs, start=1):
                issued[(pid, year)] = n

    # ---- 2. clean rows ----
    rows: list[dict] = []
    club_of: dict[str, str] = {}
    season_club: dict[tuple, str] = {}
    for r in plan:
        p, c, year = by_id[r["true_person_id"]], r["country_code"], r["season_year"]
        iy = id_year(p, year, c)
        pid = f"{ISO3[c]}-{iy % 100:02d}-{issued[(p['true_person_id'], iy)]:04d}"
        group = p["twin_group_id"] or p["true_person_id"]     # twins share their club every season
        if (group, year) not in season_club:
            if group not in club_of or rng.random() < 0.15:
                club_of[group] = rng.choice(clubs[c])
            season_club[(group, year)] = club_of[group]
        changed = bool(p["name_change_season"]) and year >= p["name_change_season"]
        family = p["later_family_name"] if changed else p["family_name"]
        name = (f"{family} {p['given_name']}" if c in sc["family_name_first_sheets"]
                else f"{p['given_name']} {family}")
        age = year - p["dob"].year
        if p["is_minor"]:
            email = p["guardian_email"] if rng.random() < sc["email_present_minor"] else None
        else:
            email = p["own_email"] if rng.random() < sc["email_present_adult"] else None
        rows.append({
            "pid": p["true_person_id"], "country": c, "year": year, "player_id": pid, "name": name,
            "dob": p["dob"], "serial": False, "gender": GENDER_LABELS[c][0 if p["sex"] == "F" else 1],
            "category": _category(rng, c, age, p["sex"]), "club": season_club[(group, year)],
            "country_cell": ISO3[c], "email": email,
            "media": "Yes" if p["photo_consent"] else "No", "defects": [],
        })
        if changed:
            rows[-1]["defects"].append("family_name_change")
        if c in sc["family_name_first_sheets"]:
            rows[-1]["defects"].append("name_order_inverted")
        if c in sc["unstable_player_id_sheets"]:
            rows[-1]["defects"].append("player_id_reissued")
    # ---- 2b. structure (phase 5 spec section 3): org profiles, dark clubs ----
    prng = random.Random(cfg["seed"] + 53)
    org = lambda r: f"{r['country']}|{r['club']}"           # noqa: E731  the organization id staging derives (country | club name)
    club_ids = sorted({org(r) for r in rows})
    country_of = {org(r): r["country"] for r in rows}
    name_of = {org(r): r["club"] for r in rows}
    counts: dict[str, int] = {}
    for r in rows:
        counts[org(r)] = counts.get(org(r), 0) + 1
    profile = P.assign_profiles(prng, [{"org_id": o, "region": country_of[o], "n_records": counts[o]} for o in club_ids], cfg)
    channel = {o: P.channel_for(prng, profile[o]) for o in club_ids}
    org_first_year = {}
    for r in rows:
        org_first_year[org(r)] = min(org_first_year.get(org(r), r["year"]), r["year"])
    dark = P.pick_unreporting(prng, {y: [o for o in club_ids if org_first_year[o] <= y] for y in cfg["seasons"]["years"]}, cfg)
    unreported = [{"source_system": SOURCE, "org_id": org(r), "season_year": r["year"], "season_term": "ANNUAL", "true_person_id": r["pid"]}
                  for r in rows if org(r) in dark[r["year"]]]
    rows = [r for r in rows if org(r) not in dark[r["year"]]]
    for r in rows:
        r["profile"] = profile[org(r)]
    N = len(rows)
    all_idx = list(range(N))

    def wpick(eligible, rate, total):
        w = {i: P.multiplier(cfg, rows[i]["profile"]) for i in eligible}
        return P.pick_weighted(rng, eligible, w, rate, total)

    # ---- 3. rate defects ----
    uk = [i for i in all_idx if rows[i]["country"] == "GB"]
    for i in wpick(uk, rates["uk_dob_excel_serial"], len(uk)):
        rows[i]["serial"] = True
        rows[i]["defects"].append("uk_dob_excel_serial")
    for i in wpick(all_idx, rates["country_value_inconsistency"], N):
        rows[i]["country_cell"] = rng.choice(COUNTRY_ALT[rows[i]["country"]])
        rows[i]["defects"].append("country_value_inconsistency")
    for i in wpick(all_idx, rates["missing_media_consent"], N):
        rows[i]["media"] = None
        rows[i]["defects"].append("missing_media_consent")

    # ---- 4. build workbooks ----
    out = D.SourceOutput(SOURCE)
    for year in cfg["seasons"]["years"]:
        fname = f"intl/federation_returns_{year}.xlsx"
        sheets = []
        for c in COUNTRY_ORDER:
            srows = sorted((rows[i] for i in all_idx if rows[i]["country"] == c and rows[i]["year"] == year),
                           key=lambda r: r["player_id"])
            if not srows:
                continue
            title = c in sc["sheets_with_title_rows"]
            first_data_row = 4 if title else 2
            cells = []
            for r in srows:
                dob = (r["dob"] - EXCEL_EPOCH).days if r["serial"] else r["dob"].strftime("%d/%m/%Y")
                cells.append([r["player_id"], r["name"], dob, r["gender"], r["category"], r["club"], r["country_cell"],
                              r["email"], r["media"]])
            summary = f"Total: {len(srows)}" if c in sc["sheets_with_summary_row"] else None
            sheets.append({"name": SHEET_NAME[c], "title": f"Federation Return {year} – {SHEET_NAME[c]}" if title else None,
                           "rows": cells, "summary": summary})
            for n, r in enumerate(srows):
                rid = f"{r['player_id']}|{year}"
                out.truth.append({"source_system": SOURCE, "source_file": fname, "source_record_id": rid, "true_person_id": r["pid"]})
                for d in r["defects"]:
                    out.manifest.append({"source_system": SOURCE, "source_file": fname, "source_record_id": rid, "defect_id": d, "mechanism": f"ORG_PROFILE:{r['profile']}"})
            n_rows = len(srows)
            junk = []
            if title:
                junk += [(1, "junk_title_row"), (2, "junk_blank_row")]
            if summary:
                junk.append((first_data_row + n_rows, "junk_summary_row"))
            for row_no, d in junk:
                out.manifest.append({"source_system": SOURCE, "source_file": fname,
                                     "source_record_id": f"{SHEET_NAME[c]}|row{row_no}", "defect_id": d})
            out.n_records += n_rows
        out.files[fname] = [{"sheets": sheets}]
    out.extra["orgs"] = [{"source_system": SOURCE, "org_id": o, "org_name": name_of[o], "region_code": country_of[o], "zip3": "", "channel": channel[o], "profile": profile[o], "first_year": org_first_year[o],
                          "zip_optional_form": False, "age_group_only": False, "consent_text_version": None, "n_records_all_seasons": counts[o]} for o in club_ids]
    out.extra["dark"] = {y: sorted(v) for y, v in dark.items()}
    out.extra["unreported"] = unreported
    return out


def _normalize_zip(path: Path) -> None:
    """Rewrite the xlsx zip with fixed timestamps so repeated runs give identical bytes."""
    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in sorted(src.infolist(), key=lambda i: i.filename):
            zi = zipfile.ZipInfo(info.filename, date_time=(2000, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o600 << 16
            data = src.read(info.filename)
            if info.filename == "docProps/core.xml":  # openpyxl stamps `modified` with the wall clock
                data = re.sub(rb"(<dcterms:modified[^>]*>)[^<]*", rb"\g<1>2000-01-01T00:00:00Z", data)
            dst.writestr(zi, data)
    shutil.move(tmp, path)


def write(out: D.SourceOutput, raw: Path) -> None:
    for rel, payload in out.files.items():
        path = raw / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        wb = Workbook()
        wb.remove(wb.active)
        wb.properties.creator = "counting-flag-football (synthetic)"
        wb.properties.created = wb.properties.modified = dt.datetime(2000, 1, 1)
        for sh in payload[0]["sheets"]:
            ws = wb.create_sheet(sh["name"])
            if sh["title"]:
                ws.append([sh["title"]])
                ws.append([])
            ws.append(COLUMNS)
            for row in sh["rows"]:
                ws.append(row)
            if sh["summary"]:
                ws.append([sh["summary"]])
        wb.save(path)
        _normalize_zip(path)
