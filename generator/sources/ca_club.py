"""Source B: Canadian club registrations (paginated JSON API dump). SYNTHETIC data.

Grain: one record per member per calendar-year season. There is no record id in the API;
a record is identified by (member_uuid, season_year). The truth/manifest `source_record_id`
is therefore "<member_uuid>|<season_year>".

Key quirks: birth year only; member_uuid is stable within a club but changes when a player
switches clubs; free-text bilingual `program`; nested objects, some without `consents`.
Adult records carry the registrant's own contact in the `guardian` object.

Rate denominators: all records, except accents_stripped, whose denominator is records that
have an accent in the participant name (otherwise a 10% rate is unreachable).
"""
from __future__ import annotations

import datetime as dt
import json
import random
import uuid
from pathlib import Path

from generator import defects as D
from generator import profiles as P
from generator.population import random_ca_postal

SOURCE = "CA_CLUB"

# Free-text program labels by age band; seeds must map every one. (fr, bilingual prefix, U-label)
YOUTH_PROGRAMS = [
    (5, 7, ["Atome", "Flag 5v5 – Atome", "U8"]),
    (8, 9, ["Benjamin", "Flag 5v5 – Benjamin", "U10"]),
    (10, 11, ["Junior", "Flag 5v5 – Junior", "U12"]),
    (12, 13, ["Cadet", "Flag 5v5 – Cadet", "U14"]),
    (14, 17, ["Juvénile", "Flag 5v5 – Juvénile", "U17"]),
]
ADULT_PROGRAMS = {
    "ADULT_W": ["Senior Féminin", "Women's Senior"],
    "ADULT_M": ["Senior Masculin", "Men's Senior"],
    "ADULT_MIXED": ["Senior Mixte", "Co-ed Senior"],
}
PROGRAM_WEIGHTS = {"fr": [0.50, 0.35, 0.15], "en": [0.20, 0.30, 0.50]}

PLACES = {
    "QC": ["Rosemont", "Laval", "Québec", "Gatineau", "Longueuil", "Sherbrooke"],
    "NB": ["Moncton", "Dieppe", "Fredericton"],
    "ON": ["Ottawa", "Toronto", "Kingston", "Hamilton", "London", "Sudbury"],
    "BC": ["Vancouver", "Surrey", "Victoria"],
    "AB": ["Calgary", "Edmonton", "Red Deer"],
    "NS": ["Halifax", "Dartmouth"],
    "MB": ["Winnipeg", "Brandon"],
}
FR_TEMPLATES = ["Les Éclairs de {p}", "Les Aigles de {p}", "Les Rapides de {p}", "Flag {p}"]
EN_TEMPLATES = ["{p} Thunder", "{p} Flag Football Club", "{p} Rebels", "{p} Stingers"]


def _club_catalog(rng: random.Random) -> dict[str, list[dict]]:
    cat = {}
    for prov, places in PLACES.items():
        clubs = []
        for n, place in enumerate(places, start=1):
            french = prov in ("QC", "NB") or (prov == "ON" and place in ("Ottawa", "Sudbury"))
            tmpl = rng.choice(FR_TEMPLATES if french else EN_TEMPLATES)
            clubs.append({
                "club_code": f"{prov}-{D.strip_accents(place)[:3].upper()}-{n:02d}",
                "club_name": tmpl.format(p=place),
                "province": prov,
                "lang": "fr" if french else "en",
            })
        cat[prov] = clubs
    return cat


def _program(rng: random.Random, age: int, sex: str, club_lang: str) -> tuple[str, str]:
    """-> (program label, canonical division it should map to)"""
    w = PROGRAM_WEIGHTS[club_lang]
    if age >= 18:
        key = "ADULT_MIXED" if rng.random() < 0.5 else ("ADULT_W" if sex == "F" else "ADULT_M")
        opts = ADULT_PROGRAMS[key]
        return (opts[0] if rng.random() < w[0] + w[1] else opts[1]), key
    for lo, hi, opts in YOUTH_PROGRAMS:
        if lo <= age <= hi:
            return rng.choices(opts, weights=w)[0], opts[2]
    raise ValueError(age)


def _has_accent(s: str) -> bool:
    return D.strip_accents(s) != s


def _fmt_phone(e164: str) -> str:
    d = e164[-10:]
    return f"+1 {d[:3]} {d[3:6]} {d[6:]}"


def _iso(d: dt.datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate(people: list[dict], parts: list[dict], cfg: dict) -> D.SourceOutput:
    rng = random.Random(cfg["seed"] + 2)
    rates = cfg["defects"]["ca_club"]
    page_size = cfg["sources"]["ca_club"]["page_size"]
    by_id = {p["true_person_id"]: p for p in people}
    plan = sorted((r for r in parts if r["source_system"] == SOURCE),
                  key=lambda r: (r["true_person_id"], r["season_year"]))
    catalog = _club_catalog(rng)

    # ---- 1. clean records ----
    recs: list[dict] = []
    home_club: dict[str, dict] = {}
    season_club: dict[tuple, dict] = {}
    uuids: dict[tuple, str] = {}
    postals: dict[str, str] = {}
    for r in plan:
        p = by_id[r["true_person_id"]]
        prov, year = r["region_code"], r["season_year"]
        group = p["twin_group_id"] or p["true_person_id"]    # twins share their club every season
        if (group, year) not in season_club:
            old = home_club.get(group)
            if old is None or old["province"] != prov or rng.random() < 0.10:  # new club: new member_uuid
                pool = catalog[prov]
                same_lang = [c for c in pool if c["lang"] == p["language"]]
                use = same_lang if same_lang and rng.random() < 0.85 else pool
                home_club[group] = rng.choice(use)
            season_club[(group, year)] = home_club[group]
        club = season_club[(group, year)]
        key = (p["true_person_id"], club["club_code"])
        if key not in uuids:
            uuids[key] = str(uuid.UUID(int=rng.getrandbits(128), version=4))
        if prov == p["home_region"]:
            postal = p["postal_code"]
        else:  # cross-border mover registering in Canada
            postal = postals.setdefault(p["true_person_id"], random_ca_postal(rng, prov))      # (drawn as before, so the random stream is unchanged)
            postal = p["alt_postal"] or postal                                                 # the mover's postal code in the market they moved to, which has launched by then
        program, division = _program(rng, year - p["dob"].year, p["sex"], club["lang"])
        if p["is_minor"]:
            contact = {"full_name": p["guardian_name"], "email": p["guardian_email"], "phone": _fmt_phone(p["guardian_phone"])}
        else:
            contact = {"full_name": f"{p['given_name']} {p['family_name']}", "email": p["own_email"], "phone": _fmt_phone(p["own_phone"])}
        captured = dt.datetime(year, 1, 5, rng.randint(6, 22), rng.randint(0, 59), rng.randint(0, 59)) + dt.timedelta(days=rng.randint(0, 55))
        updated = captured + dt.timedelta(days=rng.randint(1, 200), hours=rng.randint(0, 20))
        consents = {
            "casl_marketing": p["marketing_opt_in"], "photo_media": p["photo_consent"],
            "consent_captured_at": _iso(captured),
        }
        recs.append({
            "_pid": p["true_person_id"], "_defects": [], "_division": division,
            "member_uuid": uuids[key],
            "club": {k: club[k] for k in ("club_code", "club_name", "province")},
            "season_year": year, "program": program,
            "participant": {
                "prenom_first": p["given_name"], "nom_last": p["family_name"],
                "birth_year": p["dob"].year, "sex": p["sex"], "language": p["language"],
            },
            "guardian": contact, "postal_code": postal, "consents": consents, "updated_at": _iso(updated),
        })
    # ---- 1b. structure (phase 5 spec section 3): org profiles, dark clubs, consent wording ----
    prng = random.Random(cfg["seed"] + 52)
    club_ids = sorted({r["club"]["club_code"] for r in recs})
    province_of = {c["club_code"]: prov for prov, cl in catalog.items() for c in cl}
    counts: dict[str, int] = {}
    for r in recs:
        counts[r["club"]["club_code"]] = counts.get(r["club"]["club_code"], 0) + 1
    profile = P.assign_profiles(prng, [{"org_id": o, "region": province_of[o], "n_records": counts[o]} for o in club_ids], cfg)
    version_of = P.assign_consent_versions(prng, club_ids, profile, cfg)
    channel = {o: P.channel_for(prng, profile[o]) for o in club_ids}
    first_year = {}
    for r in recs:
        first_year[r["club"]["club_code"]] = min(first_year.get(r["club"]["club_code"], r["season_year"]), r["season_year"])
    dark = P.pick_unreporting(prng, {y: [o for o in club_ids if first_year[o] <= y] for y in cfg["seasons"]["years"]}, cfg)
    postal3: dict[str, dict[str, int]] = {}
    for r in recs:
        z = r["postal_code"][:3]
        postal3.setdefault(r["club"]["club_code"], {})[z] = postal3.setdefault(r["club"]["club_code"], {}).get(z, 0) + 1
    unreported = [{"source_system": SOURCE, "org_id": r["club"]["club_code"], "season_year": r["season_year"], "season_term": "ANNUAL", "true_person_id": r["_pid"]}
                  for r in recs if r["club"]["club_code"] in dark[r["season_year"]]]
    recs = [r for r in recs if r["club"]["club_code"] not in dark[r["season_year"]]]
    adopters = P.fix_list_adopters(cfg, profile)
    for r in recs:
        r["_profile"] = P.profile_in_season(cfg, r["club"]["club_code"], r["season_year"], profile[r["club"]["club_code"]], adopters)
        r["_mech"] = {}
        if version_of[r["club"]["club_code"]] and "consents" in r:
            r["consents"]["text_version"] = version_of[r["club"]["club_code"]]
    N = len(recs)
    all_idx = list(range(N))

    def wpick(eligible, rate, total):
        """Exact-count defect placement weighted by the org's profile (the overall rate is unchanged)."""
        w = {i: P.multiplier(cfg, recs[i]["_profile"]) for i in eligible}
        return P.pick_weighted(rng, eligible, w, rate, total)

    def mark(i, d):
        recs[i]["_defects"].append(d)

    # ---- 2. field defects ----
    accented = [i for i in all_idx if _has_accent(recs[i]["participant"]["prenom_first"] + recs[i]["participant"]["nom_last"])]
    for i in wpick(accented, rates["accents_stripped"], len(accented)):
        pt, g = recs[i]["participant"], recs[i]["guardian"]
        pt["prenom_first"], pt["nom_last"] = D.strip_accents(pt["prenom_first"]), D.strip_accents(pt["nom_last"])
        g["full_name"] = D.strip_accents(g["full_name"])
        mark(i, "accents_stripped")
    for i in wpick(all_idx, rates["all_caps_names"], N):
        pt = recs[i]["participant"]
        pt["prenom_first"], pt["nom_last"] = pt["prenom_first"].upper(), pt["nom_last"].upper()
        mark(i, "all_caps_names")
    for i in wpick(all_idx, rates["birth_year_off_by_one"], N):
        recs[i]["participant"]["birth_year"] += rng.choice([-1, 1])
        mark(i, "birth_year_off_by_one")
    for i in wpick(all_idx, rates["postal_code_format"], N):
        pc = recs[i]["postal_code"]
        recs[i]["postal_code"] = rng.choice([pc.replace(" ", ""), pc.lower(), pc.replace(" ", "").lower()])
        mark(i, "postal_code_format")
    for i in wpick(all_idx, rates["null_photo_media"], N):
        recs[i]["consents"]["photo_media"] = None
        mark(i, "null_photo_media")
    for i in wpick(all_idx, rates["null_casl_marketing"], N):
        recs[i]["consents"]["casl_marketing"] = None
        mark(i, "null_casl_marketing")
    for i in wpick(all_idx, rates["missing_consents_object"], N):
        del recs[i]["consents"]
        mark(i, "missing_consents_object")

    # ---- 3. order like an API (by updated_at), then paginate with overlap duplicates ----
    order = sorted(all_idx, key=lambda i: (recs[i]["updated_at"], recs[i]["member_uuid"]))
    last_page_start = max(0, N - page_size)
    dup_pos = set(rng.sample(range(0, last_page_start), min(round(rates["pagination_overlap_duplicate"] * N), last_page_start)))
    pages: list[list[tuple]] = []   # (record index, is_copy)
    cur: list[tuple] = []
    pending: list[tuple] = []
    for pos, i in enumerate(order):
        cur.append((i, False))
        if pos in dup_pos:
            pending.append((i, True))
        if len(cur) >= page_size:
            pages.append(cur)
            cur, pending = pending[:], []
    cur.extend(pending)
    if cur:
        pages.append(cur)

    out = D.SourceOutput(SOURCE)
    for n, page in enumerate(pages, start=1):
        fname = f"ca_club/page_{n:04d}.json"
        body = []
        for i, is_copy in page:
            r = recs[i]
            rid = f"{r['member_uuid']}|{r['season_year']}"
            body.append({k: v for k, v in r.items() if not k.startswith("_")})
            if is_copy:
                out.manifest.append({"source_system": SOURCE, "source_file": fname, "source_record_id": rid,
                                     "defect_id": "pagination_overlap_duplicate"})
                continue
            out.truth.append({"source_system": SOURCE, "source_file": fname, "source_record_id": rid,
                              "true_person_id": r["_pid"]})
            for d in r["_defects"]:
                out.manifest.append({"source_system": SOURCE, "source_file": fname, "source_record_id": rid, "defect_id": d,
                                     "mechanism": f"ORG_PROFILE:{r['_profile']}"})
        out.files[fname] = [{"page": n, "next_page": n + 1 if n < len(pages) else None, "records": body}]
        out.n_records += len(body)
    club_name = {c["club_code"]: c["club_name"] for cl in catalog.values() for c in cl}
    out.extra["orgs"] = [{"source_system": SOURCE, "org_id": o, "org_name": club_name[o], "region_code": province_of[o], "zip3": max(postal3[o], key=postal3[o].get),
                          "channel": channel[o], "profile": profile[o], "first_year": first_year[o], "zip_optional_form": False, "age_group_only": False,
                          "consent_text_version": version_of[o], "n_records_all_seasons": counts[o], "adopted_fix_list": o in adopters} for o in club_ids]
    out.extra["dark"] = {y: sorted(v) for y, v in dark.items()}
    out.extra["unreported"] = unreported
    return out


def write(out: D.SourceOutput, raw: Path) -> None:
    for rel, payload in out.files.items():
        path = raw / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload[0], f, ensure_ascii=False, indent=1)
            f.write("\n")
