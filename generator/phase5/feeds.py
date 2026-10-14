"""Phase 5: six US registration feeds with different schemas and realistic defects. SYNTHETIC data.

Isolated scope: the feeds are derived from the existing true US youth registry using their own random stream (seed + phase5.seed_offset), so no Phase 1-4
file changes. Each child is placed in one primary feed (weights in config), some also in a second feed (the cross-source duplicate), for the seasons in
`phase5.seasons`. Defects are injected at exact counts, round(rate * rows), as in the other sources.

Writes (relative to raw_dir):  p5/<feed>/<feed>_<year>.csv, p5/reference/league_catalog.csv, p5/reference/league_alias_map.csv
Writes (relative to truth_dir): p5_registration_truth.parquet, p5_defect_manifest.parquet   (ground truth: evaluation only)
All feed names, shapes and consent wordings are ASSUMPTIONS made for the demonstration; nothing here describes a real system.
"""
from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from generator import defects as D
from generator import population

FEEDS = ["matrix_export", "vendor_reg_a", "vendor_reg_b", "pop_warner_feed", "pal_chapter_csv", "school_program"]
OPERATOR = {"matrix_export": "league", "vendor_reg_a": "league", "vendor_reg_b": "league", "pop_warner_feed": "association",
            "pal_chapter_csv": "chapter", "school_program": "school"}
COLUMNS = {
    "matrix_export": ["registration_id", "league_id", "season_label", "participant_first_name", "participant_last_name", "date_of_birth", "gender",
                      "parent_email", "parent_zip", "registered_at", "consent_version", "consent_ts", "consent_scope", "marketing_opt_in"],
    "vendor_reg_a": ["reg_ref", "org_name", "season", "child_fname", "child_lname", "birthdate", "child_sex", "guardian_email", "postal_code",
                     "registered_at", "tos_accepted_text", "tos_accepted_at", "marketing_checkbox"],
    "vendor_reg_b": ["confirmation_no", "org_code", "term", "age_group", "child_first", "child_last", "parent_name", "parent_email", "zip",
                     "confirmation_date", "consent_given"],
    "pop_warner_feed": ["record_id", "association_id", "association_name", "flag_league_code", "program_type", "season_year", "player_first",
                        "player_last", "birth_date", "gender", "guardian_email", "guardian_zip", "created_at", "waiver_signed"],
    "pal_chapter_csv": ["Chapter", "Season", "Player First", "Player Last", "DOB", "Sex", "Parent/Guardian", "Parent Email", "ZIP", "Permission Slip",
                        "Notes", "Extra 1", "Extra 2"],
    "school_program": ["roster_id", "school_code", "school_name", "school_year", "grade", "student_first", "student_last", "sex"],
}
TOS_TEXTS = ["I accept the terms and the privacy notice", "Accepted by parent/guardian", "I agree to receive league emails and updates"]
PAL_CONSENT_YES = ["Y", "yes", "signed", "parent signed form", "on file"]
PAL_CONSENT_NO = ["N", "no", "refused"]
MX_VERSIONS = ["2023-09", "2024-04"]
SECOND_PARENT = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Chris"]
LEAGUE_STYLE = ["Youth Flag League", "FLAG", "Flag Football", "Flag Association"]
PLACES = ["Lakeside", "Riverton", "Oakdale", "Fairview", "Summit", "Harbor", "Cedar Park", "Maple Grove", "Stonebridge", "Pinecrest", "Westfield",
          "Eastbrook", "Northgate", "Southport", "Hillcrest", "Brookside"]


def _age_group(age: int) -> str:
    for label, top in (("U6", 5), ("U8", 7), ("U10", 9), ("U12", 11), ("U14", 13)):
        if age <= top:
            return label
    return "U17"


def _grade(age: int) -> str:
    return "K" if age <= 5 else str(min(age - 5, 12))


def _catalog(rng: random.Random, cfg5: dict, states: list[str]) -> list[dict]:
    """Canonical leagues. `source_key` is how a feed refers to the league (vendor_reg_a has only free text, so no key)."""
    out, used = [], set()
    for feed in FEEDS:
        for st in states:
            for i in range(cfg5["leagues_per_state"][feed]):
                while True:
                    name = f"{rng.choice(PLACES)} {rng.choice(LEAGUE_STYLE)}"
                    if (st, name) not in used:
                        used.add((st, name))
                        break
                n = len(out) + 1
                lid = f"P5L-{st}-{n:04d}"
                key = {"matrix_export": f"MX-{st}-{n:04d}", "vendor_reg_a": "", "vendor_reg_b": f"VB{rng.randint(1000, 9999)}",
                       "pop_warner_feed": f"PW-{rng.randint(100, 999)}", "pal_chapter_csv": f"PAL Chapter {rng.randint(10, 399)}",
                       "school_program": f"SCH{rng.randint(10000, 99999)}"}[feed]
                out.append({"league_id": lid, "league_name": f"{name} ({st})", "source_feed": feed, "source_key": key, "state": st,
                            "operator_type": OPERATOR[feed], "_short": name, "_place": name.split(" Youth")[0].split(" FLAG")[0].split(" Flag")[0], "_two": False, "_stale": False})
    # Pop Warner: an association is not a league; some associations run two flag leagues told apart only by flag_league_code
    for lg in [l for l in out if l["source_feed"] == "pop_warner_feed"]:
        if rng.random() < cfg5["pop_warner_two_league_association_share"]:
            twin = {**lg, "league_id": f"P5L-{lg['state']}-{len(out) + 1:04d}", "league_name": lg["league_name"].replace(")", " B)"), "_two": True}
            lg["_two"] = True
            lg["flag_code"], twin["flag_code"] = "A", "B"
            out.append(twin)
    for lg in out:
        lg.setdefault("flag_code", "")
        lg["_stale"] = rng.random() < cfg5["stale_league_share"]
    return out


def _aliases(rng: random.Random, lg: dict) -> list[str]:
    """Free-text spellings of a league's name in vendor_reg_a."""
    short, st = lg["_short"], lg["state"]
    base = [f"{short} ({st})", f"{short.upper()}", f"{short} - {st}", f"{short.split()[0]} Flag {st}", f"NFL FLAG {short}"]
    return [base[0]] + rng.sample(base[1:], 3)


def _dob_text(rng: random.Random, d: dt.date) -> str:
    return rng.choice([d.strftime("%m/%d/%Y"), d.isoformat(), d.strftime("%B %d, %Y"), f"{d.day} {d.strftime('%b %Y')}"])


def generate(cfg: dict | None = None) -> dict:
    cfg = cfg or population.load_config()
    c5 = cfg["phase5"]
    rng = random.Random(cfg["seed"] + c5["seed_offset"])
    people, parts = population.build_population(cfg)
    by_id = {p["true_person_id"]: p for p in people}
    # (person, season) pairs: US youth participating in the Phase 5 seasons, from the existing participation plan
    plan: dict[str, dict[tuple, str]] = {}
    for r in parts:
        if r["source_system"] == "US_LEAGUE" and r["season_year"] in c5["seasons"] and r["league_slot"] == 1 and by_id[r["true_person_id"]]["is_minor"] and by_id[r["true_person_id"]]["home_country"] == "US":
            plan.setdefault(r["true_person_id"], {})[(r["season_year"], r["season_term"])] = r["region_code"]
    pids = sorted(plan)
    states = sorted({p["home_region"] for p in (by_id[i] for i in pids)})
    catalog = _catalog(rng, c5, states)
    by_feed_state: dict[tuple, list[dict]] = {}
    for lg in catalog:
        by_feed_state.setdefault((lg["source_feed"], lg["state"]), []).append(lg)
    for lg in catalog:
        lg["_aliases"] = _aliases(rng, lg) if lg["source_feed"] == "vendor_reg_a" else []

    # second parent emails for a share of households
    hh_ids = sorted({by_id[i]["household_id"] for i in pids})
    two_email = set(rng.sample(hh_ids, round(c5["two_parent_email_household_share"] * len(hh_ids))))
    alt_email: dict[str, str] = {}
    for i in pids:
        p = by_id[i]
        if p["household_id"] in two_email and p["household_id"] not in alt_email:
            fam = p["guardian_name"].split()[-1].lower()
            alt_email[p["household_id"]] = f"{rng.choice(SECOND_PARENT).lower()}.{fam}{rng.randint(10, 9999)}@example.com"

    weights = [c5["feed_weights"][f] for f in FEEDS]
    school_seen: set = set()
    rows: dict[str, list[dict]] = {f: [] for f in FEEDS}     # internal rows: canonical values + rendering inputs
    for pid in pids:
        p = by_id[pid]
        primary = rng.choices(FEEDS, weights=weights)[0]
        feeds = [primary]
        if rng.random() < c5["second_feed_share"]:
            feeds.append(rng.choice([f for f in FEEDS if f != primary]))
        league_of = {}
        for f in feeds:
            league_of[f] = rng.choice(by_feed_state[(f, p["home_region"])])
        for (year, term), _st in sorted(plan[pid].items()):
            for fi, f in enumerate(feeds):
                lg = league_of[f]
                if lg["_stale"] and year == max(c5["seasons"]):
                    continue                                # a stale league never sent its latest season
                start = dt.date(year, int(c5["season_start"][term][:2]), int(c5["season_start"][term][3:]))
                if f == "school_program":                   # a school roster is annual: one row per student per school year
                    if (pid, year) in school_seen:
                        continue
                    school_seen.add((pid, year))
                rows[f].append({"p": p, "league": lg, "year": year, "term": term, "start": start, "second": fi > 0, "tackle": False})

    # Pop Warner tackle rows: out of scope, must be filtered by program_type. They reuse other children's names but are not flag registrations.
    pw = rows["pop_warner_feed"]
    for r in rng.sample(pw, round(c5["pop_warner_tackle_share"] * len(pw))):
        pid2 = rng.choice(pids)
        lg = rng.choice(by_feed_state.get(("pop_warner_feed", by_id[pid2]["home_region"])) or [r["league"]])
        pw.append({**r, "p": by_id[pid2], "league": lg, "tackle": True, "second": False})

    manifest: list[dict] = []
    truth: list[dict] = []
    out_rows: dict[str, list[dict]] = {}
    for f in FEEDS:
        rs = rows[f]
        rng.shuffle(rs)
        rs.sort(key=lambda r: (r["year"], r["term"]))
        out_rows[f] = _render(f, rs, rng, c5, alt_email, manifest, truth)
    # consent revocations: a share of households (by the parent email on the registry) asked for their consent to be withdrawn. Own random stream; the households are chosen after everything else.
    rr = c5["retention"]
    rrng = random.Random(cfg["seed"] + c5["seed_offset"] + 3)
    emails = sorted({by_id[i]["guardian_email"] for i in pids})
    d0, d1 = dt.date.fromisoformat(rr["revocation_from"]), dt.date.fromisoformat(rr["revocation_to"])
    revocations = [{"parent_email": e, "revoked_at": (d0 + dt.timedelta(days=rrng.randint(0, (d1 - d0).days))).isoformat() + f" {rrng.randint(6, 22):02d}:{rrng.randint(0, 59):02d}:00",
                    "scope": "ALL", "channel": rrng.choice(["EMAIL", "WEB_FORM"])}
                   for e in rrng.sample(emails, round(rr["revocation_share"] * len(emails)))]
    revocations.sort(key=lambda r: r["revoked_at"])
    return {"catalog": catalog, "revocations": revocations, "rows": out_rows, "truth": truth, "manifest": manifest, "n_children": len(pids)}


def _ts(rng: random.Random, start: dt.date, late: bool) -> dt.datetime:
    day = start + dt.timedelta(days=rng.randint(10, 60) if late else -rng.randint(5, 60))
    return dt.datetime(day.year, day.month, day.day, rng.randint(6, 23), rng.randint(0, 59), rng.randint(0, 59))


def _render(feed: str, rs: list[dict], rng: random.Random, c5: dict, alt_email: dict, manifest: list[dict], truth: list[dict]) -> list[dict]:
    rates = c5["defects"][feed]
    n = len(rs)
    idx = list(range(n))
    chosen: dict[str, set[int]] = {}

    def mark(defect: str, eligible: list[int] | None = None, total: int | None = None) -> set[int]:
        chosen[defect] = set(D.pick(rng, idx if eligible is None else eligible, rates[defect], n if total is None else total))
        return chosen[defect]

    for d in rates:
        if d == "blank_flag_league_code":
            mark(d, [i for i in idx if rs[i]["league"]["_two"] and not rs[i]["tackle"]], total=sum(1 for r in rs if r["league"]["_two"] and not r["tackle"]))
        elif d == "duplicate_row":
            continue            # handled after rendering
        elif d == "name_variant":
            mark(d)
        else:
            mark(d)
    late = set(D.pick(rng, idx, c5["late_submission"], n))
    chosen["late_submission"] = late
    chosen["email_case_whitespace"] = set(D.pick(rng, idx, c5["email_case_whitespace"], n))
    chosen["second_parent_email"] = set()
    truth_ix: dict[str, int] = {}

    out: list[dict] = []
    pal_row: dict[int, int] = {}
    for i, r in enumerate(rs):
        p, lg, y, term = r["p"], r["league"], r["year"], r["term"]
        first, last = p["given_name"], p["family_name"]
        if i in chosen.get("name_variant", ()):
            first = p["nickname"] if p["nickname"] and rng.random() < 0.5 else D.typo(rng, first)
        if i in chosen.get("typo_name", ()):
            last = D.typo(rng, last)
        email = p["guardian_email"]
        if p["household_id"] in alt_email and rng.random() < 0.5:
            email = alt_email[p["household_id"]]
            chosen["second_parent_email"].add(i)
        if i in chosen.get("typo_email", ()):
            email = D.typo(rng, email)
        if i in chosen["email_case_whitespace"]:
            email = D.email_variant(rng, email)            # raw capture noise; cleaned in staging
        zip_ = p["postal_code"]
        if i in chosen.get("missing_zip", ()):
            zip_ = ""
        elif i in chosen.get("invalid_zip", ()):
            zip_ = rng.choice(["00000", "1234", "ABCDE", zip_[:3]])
        elif i in chosen.get("zip_plus4", ()):
            zip_ = f"{zip_}-{rng.randint(1000, 9999)}"
        ts = _ts(rng, r["start"], i in late)
        age = y - p["dob"].year
        rid_no = i + 1
        ts_s = ts.strftime("%Y-%m-%d %H:%M:%S")
        no_consent = i in chosen.get("no_consent_record", ())
        marketing = p["marketing_opt_in"]
        if feed == "matrix_export":
            ver = MX_VERSIONS[0 if ts.year < 2024 or (ts.year == 2024 and ts.month < 4) else 1]
            rec = {"registration_id": f"MX-{y}{term[0]}-{rid_no:06d}", "league_id": lg["source_key"], "season_label": f"{y} {term.title()}",
                   "participant_first_name": first, "participant_last_name": last, "date_of_birth": p["dob"].isoformat(), "gender": p["sex"],
                   "parent_email": email, "parent_zip": zip_, "registered_at": ts_s, "consent_version": ver, "consent_ts": ts_s,
                   "consent_scope": "OPS+COMMS", "marketing_opt_in": "Y" if marketing else "N"}
            if no_consent:
                rec.update(consent_version="", consent_ts="", consent_scope="", marketing_opt_in="")
            if i in chosen["missing_consent_ts"]:
                rec["consent_ts"] = ""
            if i in chosen["missing_consent_version"]:
                rec["consent_version"] = ""
        elif feed == "vendor_reg_a":
            dob = p["dob"]
            if i in chosen["impossible_dob"]:
                dob = D.impossible_dob(rng, dob, y)
            rec = {"reg_ref": f"VA{rng.randint(10**7, 10**8 - 1)}", "org_name": rng.choice(lg["_aliases"]) if lg["_aliases"] else lg["league_name"],
                   "season": f"{term.title()} {y}", "child_fname": first, "child_lname": last, "birthdate": _dob_text(rng, dob),
                   "child_sex": {"M": "Boy", "F": "Girl"}[p["sex"]], "guardian_email": email, "postal_code": zip_, "registered_at": ts_s,
                   "tos_accepted_text": rng.choice(TOS_TEXTS), "tos_accepted_at": ts_s,
                   "marketing_checkbox": "checked" if marketing else "unchecked"}
            if no_consent:
                rec.update(tos_accepted_text="", tos_accepted_at="", marketing_checkbox="")
            if i in chosen["missing_tos_ts"]:
                rec["tos_accepted_at"] = ""
        elif feed == "vendor_reg_b":
            pn = p["guardian_name"]
            fam = pn.split()[-1]
            rec = {"confirmation_no": f"B{rng.randint(10**8, 10**9 - 1)}", "org_code": lg["source_key"], "term": f"{term.title()} {y}",
                   "age_group": "" if i in chosen["missing_age_group"] else _age_group(age), "child_first": first, "child_last": last,
                   "parent_name": rng.choice([pn, f"{fam}, {' '.join(pn.split()[:-1])}"]), "parent_email": email, "zip": zip_,
                   "confirmation_date": ts.date().isoformat(), "consent_given": "" if no_consent else "Y"}
        elif feed == "pop_warner_feed":
            code = lg["flag_code"]
            if i in chosen["blank_flag_league_code"]:
                code = ""
            rec = {"record_id": f"PW{y}-{rid_no:06d}", "association_id": lg["source_key"], "association_name": lg["league_name"].split(" (")[0].upper(),
                   "flag_league_code": code, "program_type": "TACKLE" if r["tackle"] else "FLAG", "season_year": str(y), "player_first": first,
                   "player_last": last, "birth_date": p["dob"].isoformat(), "gender": p["sex"], "guardian_email": email, "guardian_zip": zip_,
                   "created_at": ts_s, "waiver_signed": "" if no_consent else "Y"}
        elif feed == "pal_chapter_csv":
            dob = p["dob"].strftime("%m/%d/%Y")
            if rng.random() < rates["short_year_dob"]:
                dob = p["dob"].strftime("%m/%d/%y")
            consent = "" if no_consent else rng.choice(PAL_CONSENT_YES if rng.random() < 0.9 else PAL_CONSENT_NO)
            rec = {"Chapter": lg["source_key"], "Season": f"{term.title()} {y}", "Player First": first, "Player Last": last, "DOB": dob, "Sex": p["sex"],
                   "Parent/Guardian": p["guardian_name"], "Parent Email": email, "ZIP": zip_, "Permission Slip": consent,
                   "Notes": "", "Extra 1": "", "Extra 2": ""}
        else:  # school_program
            rec = {"roster_id": f"SR{y}-{rid_no:06d}", "school_code": lg["source_key"], "school_name": lg["_place"] + (" Elementary" if len(lg["_place"]) % 2 else " Middle School"),
                   "school_year": f"{y - 1}-{str(y)[2:]}", "grade": "" if i in chosen["missing_grade"] else _grade(age), "student_first": first,
                   "student_last": last, "sex": p["sex"]}
        rec["_y"] = y
        if feed == "pal_chapter_csv":                           # PAL has no record id: the staging id is year + data row number of its file
            pal_row[y] = pal_row.get(y, 0) + 1
            rec["_rid"] = f"PAL-{y}-{pal_row[y]:06d}"
        out.append(rec)
        rid = rec.get("_rid") or next(iter(rec.values()))
        truth_ix[rid] = len(truth)
        truth.append({"feed": feed, "source_record_id": rid, "true_person_id": p["true_person_id"], "household_id": p["household_id"],
                      "league_id": lg["league_id"], "season_year": y, "season_term": term, "is_flag": not r["tackle"],
                      "is_second_feed": r["second"]})
    ids = [o.get("_rid") or next(iter(o.values())) for o in out]
    manifest.extend({"feed": feed, "defect_id": d, "record_id": ids[j]} for d, s_ in chosen.items() for j in sorted(s_))
    if feed == "pal_chapter_csv":                                    # manual uploads: whole rows pasted twice (same Chapter/Season/Name, same row)
        dup = D.pick(rng, list(range(len(out))), rates["duplicate_row"], len(out))
        for j in sorted(dup):
            y = out[j]["_y"]
            pal_row[y] += 1
            out.append({**out[j], "_rid": f"PAL-{y}-{pal_row[y]:06d}"})
            truth.append({**truth[truth_ix[ids[j]]], "source_record_id": out[-1]["_rid"]})
            manifest.append({"feed": feed, "defect_id": "duplicate_row", "record_id": out[-1]["_rid"]})
    return out


def write(res: dict, raw_dir: str | Path, truth_dir: str | Path, cfg: dict) -> dict:
    raw, tdir = Path(raw_dir) / "p5", Path(truth_dir)
    (raw / "reference").mkdir(parents=True, exist_ok=True)
    tdir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for f in FEEDS:
        (raw / f).mkdir(parents=True, exist_ok=True)
        for old in (raw / f).glob("*.csv"):
            old.unlink()
        by_year: dict[int, list[dict]] = {}
        for rec in res["rows"][f]:
            by_year.setdefault(rec["_y"], []).append(rec)
        for y, recs in sorted(by_year.items()):
            with open(raw / f / f"{f}_{y}.csv", "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=COLUMNS[f], extrasaction="ignore")
                w.writeheader()
                w.writerows(recs)
        counts[f] = len(res["rows"][f])
    with open(raw / "reference" / "league_catalog.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["league_id", "league_name", "source_feed", "source_key", "flag_code", "state", "operator_type"], extrasaction="ignore")
        w.writeheader()
        w.writerows(res["catalog"])
    # the alias map covers only part of the free-text spellings (a steward maintains it; the rest stay unmapped and are a completeness finding)
    arng = random.Random(cfg["seed"] + cfg["phase5"]["seed_offset"] + 1)
    with open(raw / "reference" / "league_alias_map.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["alias", "league_id"])
        for lg in res["catalog"]:
            for a in lg["_aliases"]:
                if arng.random() < cfg["phase5"]["alias_map_coverage"]:
                    w.writerow([a, lg["league_id"]])
    (raw / "revocations").mkdir(parents=True, exist_ok=True)
    with open(raw / "revocations" / "revocations.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["parent_email", "revoked_at", "scope", "channel"])
        w.writeheader()
        w.writerows(res["revocations"])
    pq.write_table(pa.Table.from_pylist(res["truth"]), tdir / "p5_registration_truth.parquet")
    pq.write_table(pa.Table.from_pylist(res["manifest"]), tdir / "p5_defect_manifest.parquet")
    return counts


def run(cfg: dict | None = None, raw_dir: str | None = None, truth_dir: str | None = None) -> dict:
    cfg = cfg or population.load_config()
    res = generate(cfg)
    counts = write(res, raw_dir or cfg["paths"]["raw_dir"], truth_dir or cfg["paths"]["ground_truth_dir"], cfg)
    return {"rows": counts, "children": res["n_children"], "leagues": len(res["catalog"])}


if __name__ == "__main__":
    print(run())
