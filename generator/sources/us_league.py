"""Source A: US league registrations (CSV, one file per season export). SYNTHETIC data.

Grain: one row per registration (person x league x season). Defects are injected at
exact counts, round(rate * rows), from the config. Rate denominators:
  rows            : name defects excluded below; exact/near duplicates, email case/whitespace,
                    missing gender / photo / marketing consent, impossible DOB, DOB swap
  re-registrations: name typo, nickname, guardian email changed (rows where the person
                    already has an earlier US registration)
Nickname is only possible for people who have one, so it is drawn from that eligible
set at rate / nickname_share (keeps the overall rate near the configured one).
"""
from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

from generator import defects as D
from generator.population import random_us_zip

SOURCE = "US_LEAGUE"
COLUMNS = [
    "registration_id", "league_id", "league_name", "season", "division",
    "player_first_name", "player_last_name", "player_dob", "player_gender",
    "guardian_name", "guardian_email", "guardian_phone", "zip", "team_name",
    "registered_at", "waiver_signed", "photo_consent", "marketing_opt_in",
]
TERM_ORDER = {"SPRING": 0, "FALL": 1}

# Division label styles; a league uses one style consistently. Seeds must map all of these.
YOUTH_LABELS = {
    "U6": ["U6", "6U", "Under 6"], "U8": ["U8", "8U", "Under 8"],
    "U10": ["U10", "10U", "Under 10"], "U12": ["U12", "12U", "Under 12"],
    "U14": ["U14", "14U", "Under 14"], "U17": ["U17", "17U", "Under 17"],
}
ADULT_LABELS = {
    "ADULT_W": ["Adult Women", "Women's Open", "Womens"],
    "ADULT_M": ["Adult Men", "Men's Open", "Mens"],
    "ADULT_MIXED": ["Adult Co-ed", "Coed Adult", "Co-Ed"],
}
GENDER_STYLES = [("M", "F"), ("Boy", "Girl"), ("Male", "Female")]
DOB_FORMATS = ["%m/%d/%Y", "%Y-%m-%d"]
LEAGUES_PER_STATE = 6
LEAGUE_PREFIXES = ["North", "South", "East", "West", "Central", "Greater", "Lakeside", "Metro"]
LEAGUE_PLACES = ["Austin", "Dallas", "Tampa", "Newark", "Boston", "Albany", "Joliet", "Dayton", "Tacoma",
                 "Macon", "Boulder", "Mesa", "Erie", "Hartford", "Plano", "Orlando", "Trenton", "Salem"]
TEAM_NAMES = ["Blue Jays", "Thunder", "Comets", "Rockets", "Sharks", "Wildcats", "Falcons", "Storm",
              "Panthers", "Lightning", "Hawks", "Stingers"]


def division_for(age: int, sex: str, rng: random.Random) -> str:
    """Canonical division from age at Dec 31 of the season year (ADR-002)."""
    if age >= 18:
        return "ADULT_MIXED" if rng.random() < 0.5 else ("ADULT_W" if sex == "F" else "ADULT_M")
    for key, top in (("U6", 5), ("U8", 7), ("U10", 9), ("U12", 11), ("U14", 13)):
        if age <= top:
            return key
    return "U17"


def _league_catalog(rng: random.Random, states: list[str]) -> dict[str, list[dict]]:
    cat = {}
    used = set()
    for st in states:
        leagues = []
        for _ in range(LEAGUES_PER_STATE):
            while True:
                num = rng.randint(1, 9999)
                if (st, num) not in used:
                    used.add((st, num))
                    break
            leagues.append({
                "league_id": f"L-{st}-{num:04d}",
                "league_name": f"{rng.choice(LEAGUE_PREFIXES)} {rng.choice(LEAGUE_PLACES)} FLAG",
                "label_style": rng.randrange(3),
                "gender_style": rng.randrange(3),
                "dob_format": rng.choice(DOB_FORMATS),
                "teams": rng.sample(TEAM_NAMES, 4),
            })
        cat[st] = leagues
    return cat


def _registered_at(rng: random.Random, year: int, term: str) -> dt.datetime:
    start, end = ((dt.date(year, 1, 5), dt.date(year, 2, 28)) if term == "SPRING"
                  else (dt.date(year, 6, 1), dt.date(year, 8, 20)))
    day = start + dt.timedelta(days=rng.randint(0, (end - start).days))
    return dt.datetime(day.year, day.month, day.day, rng.randint(6, 23), rng.randint(0, 59), rng.randint(0, 59))


def _fmt_phone(rng: random.Random, e164: str) -> str:
    d = e164[-10:]
    return rng.choice([f"({d[:3]}) {d[3:6]}-{d[6:]}", f"{d[:3]}.{d[3:6]}.{d[6:]}", d])


def _yn(rng: random.Random, value: bool) -> str:
    return rng.choice(["Y", "yes", "TRUE"] if value else ["N", "no", "FALSE"])


def generate(people: list[dict], parts: list[dict], cfg: dict) -> D.SourceOutput:
    rng = random.Random(cfg["seed"] + 1)
    rates = cfg["defects"]["us_league"]
    by_id = {p["true_person_id"]: p for p in people}
    plan = sorted((r for r in parts if r["source_system"] == SOURCE),
                  key=lambda r: (r["true_person_id"], r["season_year"], TERM_ORDER[r["season_term"]], r["league_slot"]))
    states = sorted({r["region_code"] for r in plan})
    catalog = _league_catalog(rng, states)

    # ---- 1. base rows (clean) ----
    rows: list[dict] = []
    home_league: dict[tuple, dict] = {}
    season_league: dict[tuple, dict] = {}
    seen_time: dict[str, tuple] = {}
    zips: dict[tuple, str] = {}
    for r in plan:
        p = by_id[r["true_person_id"]]
        st, year, term = r["region_code"], r["season_year"], r["season_term"]
        t = (year, TERM_ORDER[term])
        rereg = r["true_person_id"] in seen_time and seen_time[r["true_person_id"]] < t
        seen_time.setdefault(r["true_person_id"], t)
        group = p["twin_group_id"] or p["true_person_id"]    # twins share their league every season
        key = (group, st)
        if r["league_slot"] == 1:
            cache_key = (group, year, term)
            if cache_key not in season_league:
                if key not in home_league or (rereg and rng.random() < 0.15):
                    home_league[key] = rng.choice(catalog[st])
                season_league[cache_key] = home_league[key]
            league = season_league[cache_key]
        else:
            first = home_league[key]
            league = rng.choice([l for l in catalog[st] if l is not first])
        age = year - p["dob"].year
        division = division_for(age, p["sex"], rng)
        if st == p["home_region"]:
            zip_code = p["postal_code"]
        else:  # cross-border mover registering in the US
            zip_code = zips.setdefault(key, random_us_zip(rng, st))      # (drawn as before, so the random stream is unchanged)
            zip_code = p["alt_postal"] or zip_code                       # the mover's postal code in the market they moved to, which has launched by then
        if p["is_minor"]:
            contact = (p["guardian_name"], p["guardian_email"], p["guardian_phone"])
        else:  # adult rows carry the registrant's own contact in the guardian_* columns
            contact = (f"{p['given_name']} {p['family_name']}", p["own_email"], p["own_phone"])
        rows.append({
            "pid": p["true_person_id"], "year": year, "term": term, "slot": r["league_slot"],
            "league": league, "rereg": rereg, "division": division, "sex": p["sex"], "adult": not p["is_minor"],
            "first": p["given_name"], "last": p["family_name"], "nickname": p["nickname"],
            "dob": p["dob"], "g_name": contact[0], "email": contact[1], "phone": contact[2],
            "zip": zip_code, "team": rng.choice(league["teams"]),
            "registered_at": _registered_at(rng, year, term),
            "waiver": rng.random() < 0.95, "photo": p["photo_consent"], "marketing": p["marketing_opt_in"],
            "defects": [], "marks": {},
        })

    # ---- 2. near-duplicates: same person/league/season, new id and timestamp ----
    n_base = len(rows)
    for i in D.pick(rng, list(range(n_base)), rates["near_duplicate"], n_base):
        dup = {**rows[i], "defects": ["near_duplicate"], "marks": {}}
        dup["registered_at"] = rows[i]["registered_at"] + dt.timedelta(minutes=rng.randint(30, 2880))
        rows.append(dup)
    N = len(rows)
    all_idx = list(range(N))
    rereg_idx = [i for i in all_idx if rows[i]["rereg"]]

    def mark(i, defect):
        rows[i]["defects"].append(defect)

    # ---- 3. name defects (re-registrations only) ----
    typo_rows = D.pick(rng, rereg_idx, rates["name_typo_reregistration"], len(rereg_idx))
    for i in typo_rows:
        field = rng.choice(["first", "last"])
        rows[i][field] = D.typo(rng, rows[i][field])
        mark(i, "name_typo_reregistration")
    nick_pool = [i for i in rereg_idx if rows[i]["nickname"] and "name_typo_reregistration" not in rows[i]["defects"]]
    nick_share = cfg["population"]["nickname_share"]
    for i in D.pick(rng, nick_pool, rates["nickname_reregistration"] / nick_share, len(nick_pool)):
        rows[i]["first"] = rows[i]["nickname"]
        mark(i, "nickname_reregistration")

    # ---- 4. DOB defects (swap first, impossible from the untouched rest) ----
    swappable = [i for i in all_idx if D.can_swap_day_month(rows[i]["dob"])]
    for i in D.pick(rng, swappable, rates["dob_day_month_swapped"], N):
        rows[i]["dob"] = D.swap_day_month(rows[i]["dob"])
        mark(i, "dob_day_month_swapped")
    untouched = [i for i in all_idx if "dob_day_month_swapped" not in rows[i]["defects"]]
    for i in D.pick(rng, untouched, rates["impossible_dob"], N):
        rows[i]["dob"] = D.impossible_dob(rng, rows[i]["dob"], rows[i]["year"])
        mark(i, "impossible_dob")

    # ---- 5. guardian email: change (persists for later seasons), then case/whitespace ----
    changed = set(D.pick(rng, rereg_idx, rates["guardian_email_changed_between_seasons"], len(rereg_idx)))
    order = sorted(all_idx, key=lambda i: (rows[i]["pid"], rows[i]["year"], TERM_ORDER[rows[i]["term"]], rows[i]["registered_at"]))
    current: dict[str, str] = {}
    for i in order:
        r = rows[i]
        if i in changed:
            local, domain = r["email"].split("@")
            current[r["pid"]] = f"{local.rstrip('0123456789')}{rng.randint(1, 9999)}.alt@{rng.choice(['example.com', 'example.org'])}"
            mark(i, "guardian_email_changed_between_seasons")
        if r["pid"] in current:
            r["email"] = current[r["pid"]]
    for i in D.pick(rng, all_idx, rates["guardian_email_case_whitespace"], N):
        rows[i]["email"] = D.email_variant(rng, rows[i]["email"])
        mark(i, "guardian_email_case_whitespace")

    # ---- 6. missing values ----
    for i in D.pick(rng, all_idx, rates["missing_gender"], N):
        rows[i]["sex"] = None
        mark(i, "missing_gender")
    for i in D.pick(rng, all_idx, rates["missing_photo_consent"], N):
        rows[i]["photo"] = None
        mark(i, "missing_photo_consent")
    for i in D.pick(rng, all_idx, rates["missing_marketing_opt_in"], N):
        rows[i]["marketing"] = None
        mark(i, "missing_marketing_opt_in")
    lead0 = [i for i in all_idx if rows[i]["zip"].startswith("0")]
    for i in D.pick(rng, lead0, rates["zip_leading_zero_dropped"], len(lead0)):
        rows[i]["zip"] = rows[i]["zip"].lstrip("0")
        mark(i, "zip_leading_zero_dropped")

    # ---- 7. ids: sequential within each season file, in registration order ----
    files: dict[tuple, list[dict]] = {}
    for i in sorted(all_idx, key=lambda i: (rows[i]["registered_at"], rows[i]["pid"], rows[i]["slot"])):
        files.setdefault((rows[i]["year"], rows[i]["term"]), []).append(rows[i])
    out = D.SourceOutput(SOURCE)
    for (year, term), frows in sorted(files.items()):
        tag = f"{year}{term[0]}"
        fname = f"us_league/registrations_{term.lower()}_{year}.csv"
        # ---- 8. exact duplicates (double submit) copy a finished row, id included ----
        for n, r in enumerate(frows, start=1):
            r["rid"] = f"USR-{tag}-{n:06d}"
        dup_src = [n for n, r in enumerate(frows) if "near_duplicate" not in r["defects"]]
        n_dup = round(rates["exact_duplicate"] * len(frows))
        dups = sorted(rng.sample(dup_src, min(n_dup, len(dup_src))))
        # ---- 9. render to strings (once per row, so exact copies are byte-identical) ----
        rendered = []
        for n, r in enumerate(frows):
            lg = r["league"]
            if r["sex"] is None:
                gender = ""
            else:
                style = GENDER_STYLES[lg["gender_style"]]
                if r["adult"] and style[0] == "Boy":
                    style = GENDER_STYLES[2]
                gender = style[0 if r["sex"] == "M" else 1]
            label = (ADULT_LABELS if r["adult"] else YOUTH_LABELS)[r["division"]][lg["label_style"]]
            row = {
                "registration_id": r["rid"], "league_id": lg["league_id"], "league_name": lg["league_name"],
                "season": f"{term.title()} {year}", "division": label,
                "player_first_name": r["first"], "player_last_name": r["last"],
                "player_dob": r["dob"].strftime(lg["dob_format"]), "player_gender": gender,
                "guardian_name": r["g_name"], "guardian_email": r["email"],
                "guardian_phone": _fmt_phone(rng, r["phone"]), "zip": r["zip"], "team_name": r["team"],
                "registered_at": r["registered_at"].strftime("%Y-%m-%d %H:%M:%S"),
                "waiver_signed": _yn(rng, r["waiver"]),
                "photo_consent": "" if r["photo"] is None else ("Y" if r["photo"] else "N"),
                "marketing_opt_in": "" if r["marketing"] is None else ("Y" if r["marketing"] else "N"),
            }
            rendered.append(row)
            out.truth.append({"source_system": SOURCE, "source_file": fname,
                              "source_record_id": r["rid"], "true_person_id": r["pid"]})
            defects = list(r["defects"]) + (["exact_duplicate"] if n in dups else [])
            for d in defects:
                out.manifest.append({"source_system": SOURCE, "source_file": fname,
                                     "source_record_id": r["rid"], "defect_id": d})
            if n in dups:
                rendered.append(dict(row))
        out.files[fname] = rendered
        out.n_records += len(rendered)
    return out


def write(out: D.SourceOutput, raw: Path) -> None:
    for rel, rows in out.files.items():
        path = raw / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
