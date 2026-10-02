"""Source E: school and recreation program aggregate headcounts (CSV per year). SYNTHETIC data.

Grain: program x year. There are NO individuals in this source. Each row says how many children (girls, boys, total) took part in a
program (a PE unit, an intramural, an after-school program) in a school or recreation department.

Built-in overlap (ground truth): some children in these programs are also registered participants. For every program-year the generator
knows how many (`overlap_count`) and which people they are; none of that is in the source file. A fraction of registered youth
(`school.overlap_share_of_participants`) is placed in a program in their own country and region whose grade band fits their age.

Defects (exact counts, from config `defects.school_aggregates`): total != girls + boys, missing grade band, the same program-year reported
twice by different reporters, suspiciously round totals.
"""
from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

from faker import Faker

from generator import defects as D

SOURCE = "SCHOOL_AGGREGATES"
COLUMNS = ["district", "school_or_program", "country", "region", "program_type", "grade_band", "girls_count", "boys_count",
           "total_count", "reported_by", "report_date"]
REPORTERS = ["District PE Coordinator", "Principal's office", "Recreation department coordinator", "Teacher in charge", "Program administrator"]
DISTRICT_SUFFIX = {"US": ["Unified School District", "Independent School District"], "CA": ["District School Board", "School Division"],
                   "MX": ["Distrito Escolar"], "GB": ["Local Authority Schools"], "JP": ["Board of Education"],
                   "DE": ["Schulamt"], "AT": ["Bezirksschulrat"], "PA": ["Distrito Escolar"]}
SCHOOL_WORD = {"K-2": "Elementary School", "3-5": "Elementary School", "6-8": "Middle School", "9-12": "High School"}


def _fakers(cfg: dict) -> dict[str, Faker]:
    out = {}
    for code, locale in cfg["population"]["locales"].items():
        fk = Faker(locale)
        fk.seed_instance(cfg["seed"] + 40 + sum(map(ord, code)))
        out[code] = fk
    return out


def _band_for(age: int, bands: dict) -> str | None:
    return next((b for b, (lo, hi) in bands.items() if lo <= age <= hi), None)


def generate(people: list[dict], parts: list[dict], cfg: dict) -> D.SourceOutput:
    rng = random.Random(cfg["seed"] + 4)
    sc = cfg["sources"]["school"]
    rates = cfg["defects"]["school_aggregates"]
    years = cfg["seasons"]["years"]
    bands = sc["grade_bands"]
    fakers = _fakers(cfg)
    by_id = {p["true_person_id"]: p for p in people}

    # ---- registered youth by year and place: who could overlap with a program ----
    latest: dict[tuple, dict] = {}
    for r in sorted(parts, key=lambda r: (r["season_year"], {"SPRING": 1, "ANNUAL": 2, "FALL": 3}[r["season_term"]])):
        latest[(r["true_person_id"], r["season_year"])] = r
    youth: dict[tuple, list[dict]] = {}     # (year, country, region) -> [{pid, age, sex}]
    for (pid, year), r in latest.items():
        age = year - by_id[pid]["dob"].year
        if 5 <= age <= 17:
            youth.setdefault((year, r["country_code"], r["region_code"]), []).append({"pid": pid, "age": age, "sex": by_id[pid]["sex"]})
    places = sorted({(c, g) for (_, c, g) in youth}, key=lambda t: (t[0], t[1] or ""))

    # ---- stable programs, placed where registered youth live ----
    types, weights = zip(*sorted(sc["program_types"].items()))
    programs = []
    for country, region in places:
        n_max = max(len(v) for (y, c, g), v in youth.items() if c == country and g == region)
        n_prog = max(1, round(n_max / 100 * sc["programs_per_100_youth_participants"]))
        fk = fakers["CA_FR" if (country == "CA" and region == "QC") else ("CA_EN" if country == "CA" else country)]
        districts = [f"{fk.city()} {rng.choice(DISTRICT_SUFFIX[country])}" for _ in range(max(1, n_prog // 3))]
        for i in range(n_prog):
            ptype = rng.choices(types, weights=weights)[0]
            band = rng.choice(list(bands))
            district = districts[i % len(districts)]
            name = {"PE_UNIT": f"{fk.last_name()} {SCHOOL_WORD[band]}", "INTRAMURAL": f"{fk.last_name()} {SCHOOL_WORD[band]} Intramurals",
                    "AFTER_SCHOOL": f"{fk.last_name()} Community After-School Program"}[ptype]
            lo, hi = sc["size_range"][ptype]
            programs.append({"country": country, "region": region, "district": district, "name": name, "type": ptype, "band": band,
                             "base": rng.randint(lo, hi)})
    # a program name must identify one program: disambiguate repeats
    seen: dict[tuple, int] = {}
    for p in programs:
        k = (p["district"], p["name"])
        seen[k] = seen.get(k, 0) + 1
        if seen[k] > 1:
            p["name"] += f" {seen[k]}"
    for i, p in enumerate(programs):
        p["key"] = f"{p['district']}|{p['name']}"

    # ---- program-years: sizes, then place the overlapping registered youth ----
    truth_rows, overlap_rows = [], []
    for year in years:
        active = [p for p in programs if rng.random() < sc["program_participation_rate"]]
        size = {p["key"]: max(5, round(p["base"] * rng.uniform(0.85, 1.15))) for p in active}
        assigned: dict[str, list[dict]] = {p["key"]: [] for p in active}
        for country, region in places:
            pool = youth.get((year, country, region), [])
            chosen = rng.sample(pool, round(sc["overlap_share_of_participants"] * len(pool))) if pool else []
            local = [p for p in active if p["country"] == country and p["region"] == region]
            for kid in chosen:
                band = _band_for(kid["age"], bands)
                fits = [p for p in local if p["band"] == band
                        and len(assigned[p["key"]]) < int(sc["max_overlap_share_of_program"] * size[p["key"]])]
                if fits:
                    assigned[rng.choice(fits)["key"]].append(kid)
        for p in active:
            kids = assigned[p["key"]]
            total = size[p["key"]]
            others = total - len(kids)
            girls = sum(1 for k in kids if k["sex"] == "F") + sum(rng.random() < sc["girls_share"][p["type"]] for _ in range(others))
            truth_rows.append({"program_key": p["key"], "year": year, "country": p["country"], "region": p["region"] or "", "district": p["district"],
                               "school_or_program": p["name"], "program_type": p["type"], "grade_band": p["band"],
                               "true_total": total, "true_girls": girls, "true_boys": total - girls, "overlap_count": len(kids)})
            overlap_rows += [{"program_key": p["key"], "year": year, "true_person_id": k["pid"]} for k in kids]

    # ---- reported rows, then defects at exact counts ----
    rows = []
    for t in truth_rows:
        start = dt.date(t["year"], 5, 15)
        rows.append({"t": t, "year": t["year"], "district": t["district"], "name": t["school_or_program"], "country": t["country"],
                     "region": t["region"], "type": t["program_type"], "band": t["grade_band"], "girls": t["true_girls"],
                     "boys": t["true_boys"], "total": t["true_total"], "reporter": rng.choice(REPORTERS),
                     "date": start + dt.timedelta(days=rng.randint(0, 45)), "defects": []})
    n0 = len(rows)
    idx = list(range(n0))
    for i in D.pick(rng, idx, rates["missing_grade_band"], n0):
        rows[i]["band"] = ""
        rows[i]["defects"].append("missing_grade_band")
    mism = D.pick(rng, idx, rates["total_mismatch"], n0)
    for i in mism:
        r = rows[i]
        delta = rng.choice([-1, 1]) * rng.randint(1, max(2, round(0.1 * r["total"])))
        r["total"] = max(1, r["total"] + delta) if r["total"] + delta != r["girls"] + r["boys"] else r["total"] + delta + 1
        r["defects"].append("total_mismatch")
    for i in D.pick(rng, [i for i in idx if i not in set(mism)], rates["round_number"], n0):
        r = rows[i]
        target = min(sc["round_values"], key=lambda v: (abs(v - r["total"]), v))
        share = r["girls"] / max(1, r["girls"] + r["boys"])
        r["girls"] = round(share * target)
        r["boys"], r["total"] = target - r["girls"], target
        r["defects"].append("round_number")
    for i in D.pick(rng, idx, rates["duplicate_report"], n0):
        r = rows[i]
        dup = {**r, "defects": ["duplicate_report"], "reporter": rng.choice([x for x in REPORTERS if x != r["reporter"]]),
               "date": r["date"] + dt.timedelta(days=rng.randint(3, 40))}
        if rng.random() < 0.5:                                  # the second reporter counted slightly differently
            bump = rng.choice([-1, 1]) * rng.randint(1, 3)
            dup["total"], dup["boys"] = max(1, r["total"] + bump), max(0, r["boys"] + bump)
            if "total_mismatch" in r["defects"]:
                dup["total"] += 0
        rows.append(dup)

    out = D.SourceOutput(SOURCE)
    for year in years:
        fname = f"school/headcounts_{year}.csv"
        yrows = sorted((r for r in rows if r["year"] == year), key=lambda r: (r["district"], r["name"], r["date"], r["reporter"]))
        out.files[fname] = [{"district": r["district"], "school_or_program": r["name"], "country": r["country"], "region": r["region"],
                             "program_type": r["type"], "grade_band": r["band"], "girls_count": r["girls"], "boys_count": r["boys"],
                             "total_count": r["total"], "reported_by": r["reporter"], "report_date": r["date"].isoformat()} for r in yrows]
        out.n_records += len(yrows)
        for r in yrows:
            rid = f"{r['district']}|{r['name']}|{year}|{r['reporter']}"
            for d in r["defects"]:
                out.manifest.append({"source_system": SOURCE, "source_file": fname, "source_record_id": rid, "defect_id": d})
    out.extra = {"school_truth": truth_rows, "school_overlap": overlap_rows}
    return out


def write(out: D.SourceOutput, raw: Path) -> None:
    for rel, rows in out.files.items():
        path = raw / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
