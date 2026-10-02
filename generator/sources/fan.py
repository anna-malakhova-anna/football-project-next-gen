"""Source D: fan app / ticketing accounts and an event stream. SYNTHETIC data, with a built-in causal structure for evaluation.

Holders are adults: the guardian (or the adult player) of a participant household, and a larger population of non-participant fan households in the
same regions. Files: `fan/fan_accounts.csv` (a snapshot) and `fan/events_YYYY_MM.jsonl` (one file per month the events were DELIVERED).

Causal structure (parameters in config `sources.fan`; the answer goes to ground truth, never into the raw files):
  * every household has a latent FANDOM score; baseline engagement is exp(fandom_sd * fandom)
  * SELECTION: the households that enroll a child are drawn with probability sigmoid(intercept + slope * fandom), so participant households are
    fandom-heavy and a naive participant vs non-participant comparison overstates any effect
  * TRUE EFFECT: from a household's first registration, events per month are multiplied by (1 + true_uplift) while a child is active, and the uplift
    halves every `uplift_decay_half_life_months` after the last active season ends
  * SEASONALITY: an autumn-into-winter peak applied to every household
Defects (exact counts, config `defects.fan`): account email differs from the registration guardian email, duplicate events, late-arriving events,
clock skew, account emails typed with capitals / spaces, and a phone number shared with a participant household (a false-link hazard).
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import random
from pathlib import Path

from faker import Faker

from generator import defects as D

SOURCE = "FAN_ENGAGEMENT"
ACCOUNT_COLUMNS = ["account_id", "email", "phone", "postal_prefix", "country", "created_at", "marketing_opt_in"]
TERM_ORDER = {"SPRING": 1, "ANNUAL": 2, "FALL": 3}
DOMAINS = ["example.com", "example.net", "example.org"]


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _fakers(cfg: dict) -> dict[str, Faker]:
    out = {}
    for code, locale in cfg["population"]["locales"].items():
        fk = Faker(locale)
        fk.seed_instance(cfg["seed"] + 60 + sum(map(ord, code)))
        out[code] = fk
    return out


def _month_index(year: int, month: int, first_year: int) -> int:
    return (year - first_year) * 12 + (month - 1)


def _households(people: list[dict], parts: list[dict], enroll_month: dict) -> list[dict]:
    """One row per participant household: minors share their household; an adult player is a household of one."""
    by_hh: dict[str, list[dict]] = {}
    for p in people:
        by_hh.setdefault(p["household_id"] or p["true_person_id"], []).append(p)
    first: dict[str, tuple] = {}
    last: dict[str, int] = {}
    owner = {p["true_person_id"]: (p["household_id"] or p["true_person_id"]) for p in people}
    for r in parts:
        h = owner[r["true_person_id"]]
        key = (r["season_year"], TERM_ORDER[r["season_term"]], r["season_term"])
        if h not in first or key < first[h]:
            first[h] = key
        last[h] = max(last.get(h, 0), r["season_year"])
    rows = []
    for h in sorted(by_hh):
        members = sorted(by_hh[h], key=lambda p: p["true_person_id"])
        lead = members[0]
        if h not in first:
            continue                                    # a household with no registration is not a participant household
        year, _, term = first[h]
        rows.append({"household_key": h, "email": lead["guardian_email"] or lead["own_email"], "phone": lead["guardian_phone"] or lead["own_phone"],
                     "country": lead["home_country"], "region": lead["home_region"], "postal_code": lead["postal_code"] or "",
                     "language": lead["language"], "first_year": year, "enroll_month": enroll_month[term], "first_term": term,
                     "last_active_year": last[h], "n_people": len(members)})
    return rows


def _fmt_phone(rng: random.Random, e164: str, country: str) -> str:
    d = e164[-10:]
    if country in ("US", "CA") and rng.random() < 0.4:
        return rng.choice([f"({d[:3]}) {d[3:6]}-{d[6:]}", f"{d[:3]}.{d[3:6]}.{d[6:]}", d])
    return e164


def generate(people: list[dict], parts: list[dict], cfg: dict) -> D.SourceOutput:
    rng = random.Random(cfg["seed"] + 5)
    fc = cfg["sources"]["fan"]
    rates = cfg["defects"]["fan"]
    years = cfg["seasons"]["years"]
    y0, y1 = years[0], years[-1]
    n_months = (y1 - y0 + 1) * 12
    fakers = _fakers(cfg)
    hh = _households(people, parts, fc["enroll_month_by_term"])
    n_part = len(hh)
    n_non = round(fc["non_participant_household_multiple"] * n_part)

    # ---- latent fandom and SELECTION: participants are drawn from the candidate pool with probability sigmoid(a + b f) ----
    sel = fc["selection"]
    pool = [rng.gauss(0, 1) for _ in range(n_part + n_non)]
    propensity = [1 / (1 + math.exp(-(sel["intercept"] + sel["slope"] * f))) for f in pool]
    keys = sorted(range(len(pool)), key=lambda i: -(rng.random() ** (1 / propensity[i])))   # weighted sampling without replacement
    chosen = keys[:n_part]
    rest = keys[n_part:]
    rng.shuffle(chosen)
    for h, i in zip(hh, chosen):
        h["fandom"], h["propensity"] = pool[i], propensity[i]

    # ---- accounts: some participant households, and every non-participant fan household ----
    used_emails = {h["email"].lower() for h in hh if h["email"]}
    used_phones = {h["phone"] for h in hh if h["phone"]}

    def new_email(fk: Faker) -> str:
        for _ in range(50):
            e = f"{fk.user_name().lower()}{rng.randint(10, 9999)}@{rng.choice(DOMAINS)}"
            if e not in used_emails:
                used_emails.add(e)
                return e
        raise RuntimeError("could not make a unique email")

    def locale(country: str, region: str | None) -> str:
        return "CA_FR" if (country == "CA" and region == "QC") else ("CA_EN" if country == "CA" else country)

    def new_phone(country: str) -> str:
        cc = {"US": "1", "CA": "1", "MX": "52", "GB": "44", "JP": "81", "DE": "49", "AT": "43", "PA": "507"}[country]
        for _ in range(50):
            ph = f"+{cc}{rng.randint(2_000_000_000, 9_999_999_999)}"
            if ph not in used_phones:
                used_phones.add(ph)
                return ph
        raise RuntimeError("could not make a unique phone")

    with_account = sorted(rng.sample(range(n_part), round(fc["participant_account_share"] * n_part)))
    accounts = []                                               # internal rows
    for i in with_account:
        h = hh[i]
        accounts.append({"hh": h, "participant": True, "country": h["country"], "region": h["region"], "postal": h["postal_code"][:3],
                         "email": h["email"], "phone": h["phone"] if rng.random() < fc["phone_present"] else None, "defects": []})
    n_pacc = len(accounts)
    for i in D.pick(rng, list(range(n_pacc)), rates["email_differs_from_registration"], n_pacc):
        a = accounts[i]
        a["email"] = new_email(fakers[locale(a["country"], a["region"])])
        a["defects"].append("email_differs_from_registration")
        if a["phone"] is not None and rng.random() >= fc["phone_matches_when_email_differs"]:
            a["phone"] = new_phone(a["country"])
    non = []
    for j, idx in enumerate(rest):
        base = hh[rng.randrange(n_part)]                         # same regions as participant households
        non.append({"hh": {"household_key": f"NP-{j:06d}", "fandom": pool[idx], "propensity": propensity[idx], "country": base["country"],
                           "region": base["region"], "first_year": None, "enroll_month": None, "first_term": None, "last_active_year": None},
                    "participant": False, "country": base["country"], "region": base["region"], "postal": base["postal_code"][:3],
                    "email": new_email(fakers[locale(base["country"], base["region"])]),
                    "phone": new_phone(base["country"]) if rng.random() < fc["phone_present"] else None, "defects": []})
    with_phone = [i for i, a in enumerate(non) if a["phone"]]
    shared = D.pick(rng, with_phone, rates["phone_shared_with_participant_household"], len(with_phone))
    donors = [hh[i]["phone"] for i in with_account if hh[i]["phone"]]
    for i in shared:
        non[i]["phone"] = rng.choice(donors)
        non[i]["defects"].append("phone_shared_with_participant_household")
    accounts += non
    order = list(range(len(accounts)))
    rng.shuffle(order)
    for n, i in enumerate(order):
        accounts[i]["account_id"] = f"A-{n + 1:06d}"
    accounts.sort(key=lambda a: a["account_id"])
    for i in D.pick(rng, list(range(len(accounts))), rates["email_case_whitespace"], len(accounts)):
        a = accounts[i]
        a["email_raw"] = rng.choice([a["email"].upper(), " " + a["email"], a["email"] + " ", a["email"].capitalize()])
        a["defects"].append("email_case_whitespace")

    # ---- account creation dates, then events month by month ----
    def enroll_idx(h):
        return _month_index(h["first_year"], h["enroll_month"], y0)

    lo_m, hi_m = fc["pre_enrollment_signup_months"]
    for a in accounts:
        h = a["hh"]
        created = rng.randint(0, min(23, n_months - 1))
        if a["participant"]:
            created = max(0, min(created, enroll_idx(h) - rng.randint(lo_m, hi_m)))
        a["created_idx"] = created
        a["created_at"] = dt.datetime(y0 + created // 12, created % 12 + 1, rng.randint(1, 28), rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59))
        a["marketing_opt_in"] = "true" if rng.random() < 0.4 else "false"

    for i in D.pick(rng, list(range(len(accounts))), rates["marketing_opt_in_blank"], len(accounts)):
        accounts[i]["marketing_opt_in"] = ""
        accounts[i]["defects"].append("marketing_opt_in_blank")

    mix_types, mix_w = zip(*sorted(fc["event_mix"].items()))
    half = fc["uplift_decay_half_life_months"]

    def multiplier(h, m_idx: int) -> float:
        if h["first_year"] is None or m_idx < enroll_idx(h):
            return 1.0
        end_idx = _month_index(h["last_active_year"], 12, y0)
        factor = 1.0 if m_idx <= end_idx else 0.5 ** ((m_idx - end_idx) / half)
        return 1 + fc["true_uplift"] * factor

    events = []
    for a in accounts:
        h = a["hh"]
        scale = fc["base_events_per_month"] * math.exp(fc["fandom_sd"] * h["fandom"])
        for m_idx in range(a["created_idx"], n_months):
            year, month = y0 + m_idx // 12, m_idx % 12 + 1
            lam = scale * fc["seasonality"][month] * multiplier(h, m_idx)
            for _ in range(_poisson(rng, lam)):
                etype = rng.choices(mix_types, weights=mix_w)[0]
                value = round(rng.uniform(*fc["purchase_value"][etype]), 2) if etype in fc["purchase_value"] else None
                ts = dt.datetime(year, month, rng.randint(1, 28), rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59))
                events.append({"account_id": a["account_id"], "event_type": etype, "ts": ts, "value": value, "deliver": m_idx, "defects": []})
    events.sort(key=lambda e: (e["ts"], e["account_id"], e["event_type"]))
    for n, e in enumerate(events):
        e["event_id"] = f"E{n + 1:09d}"
    n_ev = len(events)
    all_idx = list(range(n_ev))

    # ---- event defects at exact counts ----
    late_pool = [i for i in all_idx if events[i]["deliver"] + 1 < n_months]
    for i in D.pick(rng, late_pool, rates["late_arriving_event"] * n_ev / max(1, len(late_pool)), len(late_pool)):
        e = events[i]
        e["deliver"] = min(n_months - 1, e["deliver"] + rng.randint(1, 3))
        e["defects"].append("late_arriving_event")
    start, end = dt.datetime(y0, 1, 1), dt.datetime(y1, 12, 31, 23, 59, 59)
    for i in D.pick(rng, all_idx, rates["clock_skew"], n_ev):
        e = events[i]
        skewed = e["ts"] + dt.timedelta(minutes=rng.choice([-1, 1]) * rng.randint(60, 2880))
        e["ts_skewed"] = min(max(skewed, start), end)
        e["defects"].append("clock_skew")
    delivered = [dict(e, copy=False) for e in events]
    for i in D.pick(rng, all_idx, rates["duplicate_event"], n_ev):
        events[i]["defects"].append("duplicate_event")
        delivered.append(dict(events[i], copy=True))

    out = D.SourceOutput(SOURCE)
    acct_file = "fan/fan_accounts.csv"
    out.files[acct_file] = [{"account_id": a["account_id"], "email": a.get("email_raw", a["email"]),
                             "phone": "" if not a["phone"] else _fmt_phone(rng, a["phone"], a["country"]),
                             "postal_prefix": a["postal"], "country": a["country"], "created_at": a["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                             "marketing_opt_in": a["marketing_opt_in"]} for a in accounts]
    for a in accounts:
        for d in a["defects"]:
            out.manifest.append({"source_system": SOURCE, "source_file": acct_file, "source_record_id": a["account_id"], "defect_id": d})
    by_month: dict[int, list[dict]] = {}
    for e in delivered:
        by_month.setdefault(e["deliver"], []).append(e)
    for m_idx in sorted(by_month):
        fname = f"fan/events_{y0 + m_idx // 12}_{m_idx % 12 + 1:02d}.jsonl"
        rows = sorted(by_month[m_idx], key=lambda e: (e["event_id"], e["copy"]))
        out.files[fname] = [{"event_id": e["event_id"], "account_id": e["account_id"], "event_type": e["event_type"],
                             "event_ts": e.get("ts_skewed", e["ts"]).strftime("%Y-%m-%dT%H:%M:%SZ"), "value": e["value"]} for e in rows]
        out.n_records += len(rows)
        for e in rows:
            for d in e["defects"]:
                if (d == "duplicate_event") != e["copy"]:
                    continue                                   # a copy carries only `duplicate_event`; the original carries its own defects
                out.manifest.append({"source_system": SOURCE, "source_file": fname, "source_record_id": e["event_id"], "defect_id": d})

    # ---- ground truth (evaluation only) ----
    acct_of = {a["hh"]["household_key"]: a["account_id"] for a in accounts}
    truth_hh = [{"household_key": h["household_key"], "is_participant_household": True, "account_id": acct_of.get(h["household_key"], ""),
                 "latent_fandom": h["fandom"], "enrollment_propensity": h["propensity"], "first_registration_year": h["first_year"],
                 "enroll_month": h["enroll_month"], "last_active_year": h["last_active_year"], "true_uplift": fc["true_uplift"],
                 "decay_half_life_months": half, "n_people": h["n_people"], "country": h["country"], "region": h["region"] or ""} for h in hh]
    truth_hh += [{"household_key": a["hh"]["household_key"], "is_participant_household": False, "account_id": a["account_id"],
                  "latent_fandom": a["hh"]["fandom"], "enrollment_propensity": a["hh"]["propensity"], "first_registration_year": None,
                  "enroll_month": None, "last_active_year": None, "true_uplift": 0.0, "decay_half_life_months": half, "n_people": 0,
                  "country": a["country"], "region": a["region"] or ""} for a in accounts if not a["participant"]]
    truth_acct = [{"account_id": a["account_id"], "household_key": a["hh"]["household_key"], "is_participant_household": a["participant"],
                   "email_differs": "email_differs_from_registration" in a["defects"],
                   "phone_shared": "phone_shared_with_participant_household" in a["defects"]} for a in accounts]
    out.extra = {"fan_truth": truth_hh, "fan_account_truth": truth_acct}
    return out


def write(out: D.SourceOutput, raw: Path) -> None:
    for rel, rows in out.files.items():
        path = raw / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".jsonl"):
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                for r in rows:
                    f.write(json.dumps(r, separators=(",", ":")) + "\n")
        else:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=ACCOUNT_COLUMNS, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
