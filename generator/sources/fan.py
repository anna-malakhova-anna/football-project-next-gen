"""Source D, revised for the fan-acquisition rework: the fan ecosystem. SYNTHETIC data with a built-in causal structure for evaluation.

Files (data/raw/fan/):
  fan_accounts.csv              one row per account: account_id, email, phone, postal_prefix, country, created_at, acquisition_source, birth_year (holder, adults only)
  fan_consent_events.jsonl      one line per consent change: account_id, channel (email, sms, push), status (opt_in, opt_out), event_ts, capture_point
  events_YYYY_MM.jsonl          engagement events, one file per DELIVERY month: event_id, account_id, event_type, event_ts, value (always null now)
  fan_transactions_YYYY_MM.jsonl  transactions, one file per month: txn_id, account_id, txn_ts, category, amount, is_refund, original_txn_id (refunds only)

Who is in it: accounts held by adults. (a) Participant households (guardians of registered children and adult players): some already had a fan account when they
first registered, some create one afterwards. (b) Non-participant fan households in every market: an opening stock plus new accounts at a baseline rate of the market's
synthetic household population, with the NFL seasonality. Households with no account are invisible, which is why acquisition is measured at market level.

Mechanics (parameters in config `sources.fan`; the answer goes to ground truth, never into the raw files):
  * latent FANDOM per household. Account holders are fandom-heavy; SELECTION: households that enroll a child are drawn with probability sigmoid(a + b * fandom).
  * STAGGERED ROLLOUT: registrations in a market start only after its launch year (see generator/population.py), so markets launch in different years and some never do.
  * ACQUISITION: a participant household with no account creates one within a year of its first registration with probability (organic baseline + true_acquisition_lift);
    the generator records which accounts the programme caused (INCREMENTAL), which would have appeared anyway, and which came through the flag registration prompt.
  * LAPSE and REACTIVATION: accounts lapse at a monthly hazard (higher after the household's last child season ends); a participant account that had lapsed
    reactivates after the first registration with probability (base + reactivation_lift).
  * UPLIFT after the first registration: events and transactions rise by the configured uplift while a child is active and decay after the last active season; ticket
    uplift is stronger in team markets.
  * CONSENT arrives as events: an opt-in (or explicit opt-out) per channel at the capture point, later preference-centre changes, and opt-outs that rise with engagement.
Defects (exact counts, config `defects.fan`): account email differs from the registration email, duplicate accounts, duplicate / late / clock-skewed events, accounts typed
with capitals, a phone shared with a participant household, refunds with no original, consent events out of order.
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
from generator import markets as markets_mod

SOURCE = "FAN_ENGAGEMENT"
ACCOUNT_COLUMNS = ["account_id", "email", "phone", "postal_prefix", "country", "created_at", "acquisition_source", "birth_year"]
TERM_ORDER = {"SPRING": 1, "ANNUAL": 2, "FALL": 3}
DOMAINS = ["example.com", "example.net", "example.org"]
CHANNELS = ["email", "sms", "push"]
CC = {"US": "1", "CA": "1", "MX": "52", "GB": "44", "JP": "81", "DE": "49", "AT": "43", "PA": "507"}


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


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
                     "market_id": lead["home_market_id"], "first_year": year, "enroll_month": enroll_month[term], "first_term": term,
                     "last_active_year": last[h], "n_people": len(members)})
    return rows


def _fmt_phone(rng: random.Random, e164: str, country: str) -> str:
    d = e164[-10:]
    if country in ("US", "CA") and rng.random() < 0.4:
        return rng.choice([f"({d[:3]}) {d[3:6]}-{d[6:]}", f"{d[:3]}.{d[3:6]}.{d[6:]}", d])
    return e164


def _ts(y0: int, m_idx: int, rng: random.Random, day=None) -> dt.datetime:
    year, month = y0 + m_idx // 12, m_idx % 12 + 1
    return dt.datetime(year, month, day or rng.randint(1, 28), rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59))


def generate(people: list[dict], parts: list[dict], cfg: dict) -> D.SourceOutput:
    rng = random.Random(cfg["seed"] + 5)
    fc = cfg["sources"]["fan"]
    ac, aq, lp, tc, cc = fc["account"], fc["acquisition"], fc["lapse"], fc["transactions"], fc["consent"]
    rates = cfg["defects"]["fan"]
    years = cfg["seasons"]["years"]
    y0 = years[0]
    n_months = (len(years)) * 12
    fakers = _fakers(cfg)
    mkts = markets_mod.build_markets(cfg)["markets"]
    hh = _households(people, parts, fc["enroll_month_by_term"])
    n_part = len(hh)
    season = fc["seasonality"]
    season_mean = sum(season.values()) / 12

    def locale(country: str, region: str | None) -> str:
        return "CA_FR" if (country == "CA" and region == "QC") else ("CA_EN" if country == "CA" else country)

    used_emails = {h["email"].lower() for h in hh if h["email"]}
    used_phones = {h["phone"] for h in hh if h["phone"]}

    def new_email(fk: Faker) -> str:
        for _ in range(50):
            e = f"{fk.user_name().lower()}{rng.randint(10, 9999)}@{rng.choice(DOMAINS)}"
            if e not in used_emails:
                used_emails.add(e)
                return e
        raise RuntimeError("could not make a unique email")

    def new_phone(country: str) -> str:
        for _ in range(50):
            ph = f"+{CC[country]}{rng.randint(2_000_000_000, 9_999_999_999)}"
            if ph not in used_phones:
                used_phones.add(ph)
                return ph
        raise RuntimeError("could not make a unique phone")

    def pick_source(prompt_share: float) -> str:
        if rng.random() < prompt_share:
            return "flag_registration_prompt"
        keys, w = zip(*sorted(ac["acquisition_source_mix"].items()))
        return rng.choices(keys, weights=w)[0]

    def market_postal(m: dict) -> str:
        if not m["_prefixes"]:
            return ""
        prefix = rng.choice(m["_prefixes"])
        if m["country_code"] == "US":
            return prefix
        return prefix                                           # an FSA

    # ---- latent fandom and SELECTION: participants are drawn from a candidate pool with probability sigmoid(a + b f) ----
    sel = fc["selection"]
    pool = [rng.gauss(0, 1) for _ in range(4 * n_part)]
    prop = [_sigmoid(sel["intercept"] + sel["slope"] * f) for f in pool]
    keys = sorted(range(len(pool)), key=lambda i: -(rng.random() ** (1 / prop[i])))
    chosen = keys[:n_part]
    rng.shuffle(chosen)
    for h, i in zip(hh, chosen):
        h["fandom"], h["propensity"] = pool[i], prop[i]

    def enroll_idx(h):
        return (h["first_year"] - y0) * 12 + h["enroll_month"] - 1

    def end_idx(h):
        return (h["last_active_year"] - y0) * 12 + 11

    # ---- accounts. Each: dict with household info, created_idx (may be negative: before the data), fandom, source, kind ----
    accounts: list[dict] = []
    lo_n, hi_n = aq["months_to_account"]
    for h in hh:
        ex = rng.random() < _sigmoid(ac["existing_at_registration"]["intercept"] + ac["existing_at_registration"]["slope"] * h["fandom"])
        h["had_account_before"] = ex
        h["acq_type"] = "NONE"
        h["account"] = None
        if ex:
            # an existing account was opened BEFORE THE DATA STARTS, so it never shows up as a "new account" of any market-year: the market-level series then differs between launched and
            # unlaunched markets only by the accounts the programme caused (counterfactually, the would-be participants of an unlaunched market hold accounts opened at the same time)
            created = -rng.randint(1, 12 * ac["stock_created_years_before_window"])
            kind, src = "EXISTING_PARTICIPANT", pick_source(0.0)
        else:
            p_org = min(0.9, aq["organic_account_prob_12m"] * math.exp(ac["account_fandom_tilt"] * h["fandom"]))
            u = rng.random()
            if u < p_org:
                h["acq_type"], kind, src = "ORGANIC_AFTER", "NET_NEW_ORGANIC", pick_source(aq["flag_prompt_share_of_organic"])
            elif u < p_org + aq["true_acquisition_lift"]:
                h["acq_type"], kind, src = "INCREMENTAL", "NET_NEW_INCREMENTAL", pick_source(aq["flag_prompt_share_of_induced"])
            else:
                continue
            created = enroll_idx(h) + rng.randint(lo_n, hi_n)
            if created >= n_months:
                continue                                         # the account would only exist after the data ends
        a = {"hh": h, "participant": True, "country": h["country"], "region": h["region"], "market": h["market_id"], "created_idx": created,
             "fandom": h["fandom"], "source": src, "kind": kind, "email": h["email"], "phone": h["phone"] if rng.random() < ac["phone_present"] else None,
             "postal": h["postal_code"][:3].upper(), "defects": [], "dup_of": None}
        h["account"] = a
        accounts.append(a)
    n_pacc = len(accounts)
    for i in D.pick(rng, list(range(n_pacc)), rates["email_differs_from_registration"], n_pacc):
        a = accounts[i]
        a["email"] = new_email(fakers[locale(a["country"], a["region"])])
        a["defects"].append("email_differs_from_registration")
        if a["phone"] is not None and rng.random() >= ac["phone_matches_when_email_differs"]:
            a["phone"] = new_phone(a["country"])

    # non-participant households: an opening stock, then new accounts every month at a baseline rate of the market's households
    n_np = 0
    non: list[dict] = []
    # A participant household's account that is NOT caused by the programme (one it already had, or an organic one made after registering) is one of the market's
    # ordinary accounts, so it is counted inside the market's baseline rather than added on top. Only INCREMENTAL accounts add to a launched market; this keeps the
    # comparison between markets honest by construction.
    part_counts: dict[tuple, int] = {}
    for a in accounts:
        if a["kind"] in ("EXISTING_PARTICIPANT", "NET_NEW_ORGANIC"):
            key = (a["market"], "STOCK" if a["created_idx"] < 0 else a["created_idx"])
            part_counts[key] = part_counts.get(key, 0) + 1
    for m in mkts:
        n_stock = max(0, round(m["household_population"] * ac["stock_penetration"]) - part_counts.get((m["market_id"], "STOCK"), 0))
        plan = [(-rng.randint(1, 12 * ac["stock_created_years_before_window"]), "STOCK") for _ in range(n_stock)]
        for mi in range(n_months):
            lam = m["household_population"] * ac["organic_new_rate_per_household_year"] / 12 * season[mi % 12 + 1] / season_mean
            k = max(0, _poisson(rng, lam) - part_counts.get((m["market_id"], mi), 0))
            plan += [(mi, "ORGANIC_NEW")] * k
        for created, kind in plan:
            region = m["region_code"] or None
            non.append({"hh": {"household_key": f"NP-{n_np:06d}", "fandom": rng.gauss(ac["account_fandom_tilt"], 1), "propensity": None,
                               "first_year": None, "enroll_month": None, "last_active_year": None, "market_id": m["market_id"], "country": m["country_code"],
                               "region": region},
                        "participant": False, "country": m["country_code"], "region": region, "market": m["market_id"], "created_idx": created,
                        "kind": kind, "source": pick_source(0.0), "postal": market_postal(m), "defects": [], "dup_of": None})
            n_np += 1
    for a in non:
        a["fandom"] = a["hh"]["fandom"]
        fk = fakers[locale(a["country"], a["region"])]
        a["email"] = new_email(fk)
        a["phone"] = new_phone(a["country"]) if rng.random() < ac["phone_present"] else None
    with_phone = [i for i, a in enumerate(non) if a["phone"]]
    shared = D.pick(rng, with_phone, rates["phone_shared_with_participant_household"], len(with_phone))
    donors = [h["phone"] for h in hh if h["account"] and h["phone"]]            # a participant household's REGISTRATION phone: sharing it is what makes a false link possible
    for i in shared:
        non[i]["phone"] = rng.choice(donors)
        non[i]["defects"].append("phone_shared_with_participant_household")
    accounts += non

    # ---- duplicate accounts: the same household opens a second account later ----
    base_n = len(accounts)
    elig = [i for i, a in enumerate(accounts) if a["created_idx"] < n_months - 3]
    dups = []
    for i in D.pick(rng, elig, rates["duplicate_account"], base_n):
        a = accounts[i]
        d = dict(a)
        d["dup_of"], d["defects"] = a, ["duplicate_account"]
        d["created_idx"] = max(a["created_idx"], 0) + rng.randint(1, max(1, min(24, n_months - 2 - max(a["created_idx"], 0))))
        d["kind"] = "DUPLICATE"
        if a["phone"] and rng.random() < 1 / 3:                  # a different email, but the same phone and postal prefix
            d["email"] = new_email(fakers[locale(a["country"], a["region"])])
            d["defects"].append("duplicate_account_by_phone")
        else:
            d["email"] = a["email"]
        dups.append(d)
        a.setdefault("dups", []).append(d)
    accounts += dups

    order = list(range(len(accounts)))
    rng.shuffle(order)
    for n, i in enumerate(order):
        accounts[i]["account_id"] = f"A-{n + 1:06d}"
    accounts.sort(key=lambda a: a["account_id"])
    for i in D.pick(rng, list(range(len(accounts))), rates["email_case_whitespace"], len(accounts)):
        a = accounts[i]
        a["email_raw"] = rng.choice([a["email"].upper(), " " + a["email"], a["email"] + " ", a["email"].capitalize()])
        a["defects"].append("email_case_whitespace")
    blo, bhi = ac["holder_birth_year"]
    for a in accounts:
        if not a["dup_of"]:
            created_year = y0 + a["created_idx"] // 12                  # floor division: months before the data give earlier years
            a["birth_year"] = rng.randint(blo, max(blo, min(bhi, created_year - 19)))        # an adult when the account is opened (guardians only); one year of margin because a pre-data creation date can fall in the year before this estimate
    for a in accounts:
        if a["dup_of"]:
            a["birth_year"] = a["dup_of"]["birth_year"]
        a["created_at"] = (_ts(y0, a["created_idx"], rng) if a["created_idx"] >= 0
                           else dt.datetime(y0, 1, 1) - dt.timedelta(days=-a["created_idx"] * 30 + rng.randint(0, 29), seconds=-rng.randint(0, 86399)))

    # ---- month by month: lapse, engagement, transactions, consent ----
    mix_types, mix_w = zip(*sorted(fc["event_mix"].items()))
    mix_w = list(mix_w)
    fant_idx = mix_types.index("fantasy_activity")
    fant_months = set(fc["fantasy_season_months"])
    half = fc["uplift_decay_half_life_months"]
    team = {m["market_id"]: m["is_team_market"] for m in mkts}
    sigma = fc["fandom_sd"]
    events, txns, consent = [], [], []
    effect_truth: list[dict] = []        # per participant account-month: expected events as observed and with no programme (the oracle behind the fandom estimate)

    def uplift_factor(h, m_idx):
        """0 before the first registration, 1 while a child is active, decaying after the last active season."""
        if h["first_year"] is None or m_idx < enroll_idx(h):
            return 0.0
        e = end_idx(h)
        return 1.0 if m_idx <= e else 0.5 ** ((m_idx - e) / half)

    def decide_consent(a, capture, created_ts, m_idx_for_ts):
        out = {}
        for ch in CHANNELS:
            pin = cc["opt_in"][capture][ch]
            u = rng.random()
            if u < pin:
                out[ch] = "opt_in"
            elif u < pin + (1 - pin) * cc["explicit_opt_out_given_declined"]:
                out[ch] = "opt_out"
        return out

    for a in accounts:
        h = a["hh"]
        part = a["participant"]
        f = a["fandom"]
        m_team = team[a["market"]]
        enroll = enroll_idx(h) if part and h["first_year"] is not None else None
        created = a["created_idx"]
        # lapse state machine from creation (even before the data window)
        active = True
        lapse_idx, react_at, reactivated, react_caused = None, None, False, False
        status = {ch: None for ch in CHANNELS}
        cap = {"ticketing": "checkout", "flag_registration_prompt": "flag_registration"}.get(a["source"], "signup")
        initial = decide_consent(a, cap, None, created)
        for ch, st in initial.items():
            status[ch] = st
            consent.append({"a": a, "channel": ch, "status": st, "ts": a["created_at"] + dt.timedelta(seconds=rng.randint(1, 60)), "capture_point": cap, "intended": True})
        if a["dup_of"] is not None:
            # a duplicate account only receives a share of its household's events and transactions (reassigned below) and has its own signup consent;
            # it runs no engagement of its own, so the household's volume is not doubled
            a["lapse_idx"], a["reactivated"], a["react_caused"], a["final_consent"], a["lapsed_before"] = None, False, False, status, False
            continue
        sub_flag = rng.random() < tc["subscription"]["share_of_accounts"]
        sub_day = rng.randint(1, 28)
        sub_up = rng.random() < tc["subscription"]["uplift_share"]       # becomes a subscriber after registering (a draw, so the stream stays deterministic)
        for m_idx in range(created, n_months):
            # reactivation of a lapsed participant account, decided at the first registration
            if part and enroll is not None and m_idx == enroll and not active:
                u = rng.random()
                if u < lp["reactivation_base"] + lp["reactivation_lift"]:
                    react_caused = u >= lp["reactivation_base"]
                    react_at = enroll + rng.randint(0, 11)
            if not active and react_at is not None and m_idx == react_at:
                active, reactivated = True, True
            season_m = season[m_idx % 12 + 1]
            if active and m_idx > created:
                hz = lp["base_monthly_hazard"] * math.exp(lp["fandom_slope"] * f)
                if part and enroll is not None and m_idx > end_idx(h):
                    hz *= lp["after_child_churn_multiplier"]
                if rng.random() < min(0.5, hz):
                    active = False
                    if lapse_idx is None:
                        lapse_idx = m_idx
            if m_idx < 0:
                continue
            uf = uplift_factor(h, m_idx) if part else 0.0
            if part and enroll is not None:
                core = fc["base_events_per_month"] * math.exp(sigma * f) * season_m
                cf_active = active and not (react_caused and reactivated)       # no programme: a reactivation the programme caused would not have happened
                row = {"account_id": a["account_id"], "month_idx": m_idx, "expected_events_observed": core * (1 + fc["true_uplift"] * uf) if active else 0.0,
                       "expected_events_no_programme": core if cf_active else 0.0}
                # expected NET spend by category (purchases less the refunds that follow), as observed and with no programme: the oracle behind the value-uplift estimate
                spend_mult = math.exp(0.5 * sigma * f) * season_m
                for cat in ("ticket", "merch", "other"):
                    spec = tc[cat]
                    mult = spend_mult
                    up = 0.0
                    if cat == "ticket":
                        mult *= tc["ticket"]["team_multiplier"] if m_team else 1.0
                        up = tc["ticket"]["uplift_team"] if m_team else tc["ticket"]["uplift_non_team"]
                    elif cat == "merch":
                        up = tc["merch"]["uplift"]
                    mean_amount = sum(spec["amount"]) / 2
                    keep = (1 - tc["refund_share"]) if cat in ("ticket", "merch") else 1.0
                    row[f"expected_spend_{cat}_observed"] = spec["rate"] * mult * (1 + up * uf) * mean_amount * keep if active else 0.0
                    row[f"expected_spend_{cat}_no_programme"] = spec["rate"] * mult * mean_amount * keep if cf_active else 0.0
                amt = float(tc["subscription"]["amount"])
                sub_on = active and (sub_flag or (uf > 0 and m_idx >= enroll and sub_up))
                row["expected_spend_subscription_observed"] = amt if sub_on else 0.0
                row["expected_spend_subscription_no_programme"] = amt if (cf_active and sub_flag) else 0.0
                effect_truth.append(row)
            n_ev = 0
            if active:
                lam = fc["base_events_per_month"] * math.exp(sigma * f) * season_m * (1 + fc["true_uplift"] * uf)
                n_ev = _poisson(rng, lam)
                weights = mix_w[:]
                weights[fant_idx] *= 3.0 if (m_idx % 12 + 1) in fant_months else 0.5
                flag_share = fc["flag_content_share_after_registration"] if (part and uf > 0 and enroll is not None and m_idx >= enroll) else fc["flag_content_share_background"]
                for _ in range(n_ev):
                    etype = rng.choices(mix_types, weights=weights)[0]
                    if etype == "content_view" and rng.random() < flag_share:
                        etype = "flag_content_view"
                    events.append({"account": a, "event_type": etype, "ts": _ts(y0, m_idx, rng), "deliver": m_idx, "defects": []})
                # transactions
                for cat in ("ticket", "merch", "other"):
                    spec = tc[cat]
                    mult = math.exp(0.5 * sigma * f) * season_m
                    if cat == "ticket":
                        mult *= tc["ticket"]["team_multiplier"] if m_team else 1.0
                        up = tc["ticket"]["uplift_team"] if m_team else tc["ticket"]["uplift_non_team"]
                    elif cat == "merch":
                        up = tc["merch"]["uplift"]
                    else:
                        up = 0.0
                    for _ in range(_poisson(rng, spec["rate"] * mult * (1 + up * uf))):
                        txns.append({"account": a, "category": cat, "amount": round(rng.uniform(*spec["amount"]), 2), "ts": _ts(y0, m_idx, rng), "month": m_idx,
                                     "is_refund": False, "original": None, "defects": []})
                if sub_flag or (part and uf > 0 and enroll is not None and m_idx >= enroll and sub_up):
                    txns.append({"account": a, "category": "subscription", "amount": float(tc["subscription"]["amount"]), "ts": _ts(y0, m_idx, rng, day=sub_day), "month": m_idx,
                                 "is_refund": False, "original": None, "defects": []})
            # preference-centre consent changes (any month after the one the account was created in: a change cannot precede the signup)
            for ch in CHANNELS:
                if m_idx == created:
                    break
                cur = status[ch]
                if cur != "opt_in":
                    if rng.random() < cc["preference_center_monthly_opt_in"]:
                        status[ch] = "opt_in"
                        consent.append({"a": a, "channel": ch, "status": "opt_in", "ts": _ts(y0, m_idx, rng), "capture_point": "preference_center", "intended": True})
                else:
                    hz = cc["opt_out_base_monthly"] + (cc["opt_out_per_event"] * n_ev if ch == "email" else 0.0)
                    if rng.random() < hz:
                        status[ch] = "opt_out"
                        consent.append({"a": a, "channel": ch, "status": "opt_out", "ts": _ts(y0, m_idx, rng), "capture_point": "preference_center", "intended": True})
        a["lapse_idx"], a["reactivated"], a["react_caused"], a["final_consent"] = lapse_idx, reactivated, react_caused, status
        a["lapsed_before"] = bool(part and enroll is not None and lapse_idx is not None and lapse_idx <= enroll - 6)

    # ---- duplicate accounts share events and transactions with the original: after the duplicate is opened, a coin flip decides which account an event lands on ----
    def pick_account(a, m_idx):
        ds = [d for d in a.get("dups", []) if d["created_idx"] <= m_idx]
        if not ds:
            return a
        pool_ = [a] + ds
        return pool_[rng.randrange(len(pool_))]

    for e in events:
        e["acct"] = pick_account(e["account"], e["deliver"])
    for t in txns:
        t["acct"] = pick_account(t["account"], t["month"])

    events.sort(key=lambda e: (e["ts"], e["acct"]["account_id"], e["event_type"]))
    for n, e in enumerate(events):
        e["event_id"] = f"E{n + 1:09d}"
    n_ev = len(events)
    all_idx = list(range(n_ev))

    # ---- refunds, then orphan refunds ----
    refunds = []
    for t in txns:
        if t["category"] in ("ticket", "merch") and rng.random() < tc["refund_share"]:
            delay = dt.timedelta(days=rng.randint(*tc["refund_delay_days"]), hours=rng.randint(0, 23))
            refunds.append({"acct": t["acct"], "category": t["category"], "amount": t["amount"], "ts": min(t["ts"] + delay, dt.datetime(y0 + len(years) - 1, 12, 31, 23, 59, 59)),
                            "month": t["month"], "is_refund": True, "original_t": t, "original": None, "defects": []})
    txns.sort(key=lambda t: (t["ts"], t["acct"]["account_id"], t["category"]))
    for n, t in enumerate(txns):
        t["txn_id"] = f"T{n + 1:09d}"
    n_orig = len(txns)
    orphans = []
    for k, i in enumerate(D.pick(rng, list(range(n_orig)), rates["refund_without_original"], n_orig)):
        t = txns[i]
        orphans.append({"acct": t["acct"], "category": "other" if t["category"] == "subscription" else t["category"], "amount": t["amount"],
                        "ts": t["ts"] + dt.timedelta(days=rng.randint(1, 10)), "month": t["month"], "is_refund": True, "original": f"T-ORPHAN-{k + 1:05d}",
                        "defects": ["refund_without_original"]})
    for r in refunds:
        r["original"] = r["original_t"]["txn_id"]
    all_txn = sorted(txns + refunds + orphans, key=lambda t: (t["ts"], t["acct"]["account_id"], t["category"], t["is_refund"]))
    for n, t in enumerate(all_txn):
        t["txn_id"] = f"T{n + 1:09d}"
    for r in refunds:
        r["original"] = r["original_t"]["txn_id"]

    # ---- event defects at exact counts ----
    late_pool = [i for i in all_idx if events[i]["deliver"] + 1 < n_months]
    for i in D.pick(rng, late_pool, rates["late_arriving_event"] * n_ev / max(1, len(late_pool)), len(late_pool)):
        e = events[i]
        e["deliver"] = min(n_months - 1, e["deliver"] + rng.randint(1, 3))
        e["defects"].append("late_arriving_event")
    start, end = dt.datetime(y0, 1, 1), dt.datetime(y0 + len(years) - 1, 12, 31, 23, 59, 59)
    for i in D.pick(rng, all_idx, rates["clock_skew"], n_ev):
        e = events[i]
        skewed = e["ts"] + dt.timedelta(minutes=rng.choice([-1, 1]) * rng.randint(60, 2880))
        e["ts_skewed"] = min(max(skewed, start), end)
        e["defects"].append("clock_skew")
    delivered = [dict(e, copy=False) for e in events]
    for i in D.pick(rng, all_idx, rates["duplicate_event"], n_ev):
        events[i]["defects"].append("duplicate_event")
        delivered.append(dict(events[i], copy=True))

    # ---- consent defects: an opt-out timestamped before the opt-in it follows ----
    by_ac: dict[tuple, list[dict]] = {}
    for c in consent:
        by_ac.setdefault((c["a"]["account_id"], c["channel"]), []).append(c)
    pairs = []
    for key, lst in sorted(by_ac.items()):
        lst.sort(key=lambda c: c["ts"])
        for x, y in zip(lst, lst[1:]):
            if x["status"] == "opt_in" and y["status"] == "opt_out":
                pairs.append((x, y))
    for i in D.pick(rng, list(range(len(pairs))), rates["consent_out_of_order"], len(pairs)):
        x, y = pairs[i]
        y["ts"] = x["ts"] - dt.timedelta(hours=rng.randint(1, 48))
        y["defects"] = ["consent_out_of_order"]
    for c in consent:
        c.setdefault("defects", [])
    consent.sort(key=lambda c: (c["ts"], c["a"]["account_id"], c["channel"]))

    # ---- write ----
    out = D.SourceOutput(SOURCE)
    acct_file = "fan/fan_accounts.csv"
    out.files[acct_file] = [{"account_id": a["account_id"], "email": a.get("email_raw", a["email"]),
                             "phone": "" if not a["phone"] else _fmt_phone(rng, a["phone"], a["country"]),
                             "postal_prefix": a["postal"], "country": a["country"], "created_at": a["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                             "acquisition_source": a["source"], "birth_year": a["birth_year"]} for a in accounts]
    for a in accounts:
        for d in a["defects"]:
            out.manifest.append({"source_system": SOURCE, "source_file": acct_file, "source_record_id": a["account_id"], "defect_id": d})
    consent_file = "fan/fan_consent_events.jsonl"
    out.files[consent_file] = [{"account_id": c["a"]["account_id"], "channel": c["channel"], "status": c["status"],
                                "event_ts": c["ts"].strftime("%Y-%m-%dT%H:%M:%SZ"), "capture_point": c["capture_point"]} for c in consent]
    out.n_records += len(consent)
    for n, c in enumerate(consent):
        for d in c["defects"]:
            out.manifest.append({"source_system": SOURCE, "source_file": consent_file, "source_record_id": f"{c['a']['account_id']}|{c['channel']}|{c['ts']:%Y-%m-%dT%H:%M:%SZ}", "defect_id": d})
    by_month: dict[int, list[dict]] = {}
    for e in delivered:
        by_month.setdefault(e["deliver"], []).append(e)
    for m_idx in sorted(by_month):
        fname = f"fan/events_{y0 + m_idx // 12}_{m_idx % 12 + 1:02d}.jsonl"
        rows = sorted(by_month[m_idx], key=lambda e: (e["event_id"], e["copy"]))
        out.files[fname] = [{"event_id": e["event_id"], "account_id": e["acct"]["account_id"], "event_type": e["event_type"],
                             "event_ts": e.get("ts_skewed", e["ts"]).strftime("%Y-%m-%dT%H:%M:%SZ"), "value": None} for e in rows]
        out.n_records += len(rows)
        for e in rows:
            for d in e["defects"]:
                if (d == "duplicate_event") != e["copy"]:
                    continue                                   # a copy carries only `duplicate_event`; the original carries its own defects
                out.manifest.append({"source_system": SOURCE, "source_file": fname, "source_record_id": e["event_id"], "defect_id": d})
    tby: dict[int, list[dict]] = {}
    for t in all_txn:
        tby.setdefault((t["ts"].year - y0) * 12 + t["ts"].month - 1, []).append(t)
    for m_idx in sorted(tby):
        fname = f"fan/fan_transactions_{y0 + m_idx // 12}_{m_idx % 12 + 1:02d}.jsonl"
        out.files[fname] = [{"txn_id": t["txn_id"], "account_id": t["acct"]["account_id"], "txn_ts": t["ts"].strftime("%Y-%m-%dT%H:%M:%SZ"), "category": t["category"],
                             "amount": t["amount"], "is_refund": t["is_refund"], "original_txn_id": t["original"]} for t in tby[m_idx]]
        out.n_records += len(tby[m_idx])
        for t in tby[m_idx]:
            for d in t["defects"]:
                out.manifest.append({"source_system": SOURCE, "source_file": fname, "source_record_id": t["txn_id"], "defect_id": d})

    # ---- ground truth (evaluation only) ----
    canon = {}
    for a in accounts:
        if a["participant"] and a["dup_of"] is None:
            canon[a["hh"]["household_key"]] = a["account_id"]
    def truth_status(h):
        a = h["account"]
        if a is None:
            return "NO_ACCOUNT"
        if not h["had_account_before"]:
            return "NET_NEW"
        e = enroll_idx(h)
        li = a.get("lapse_idx")
        if li is not None and li <= e - 6:
            return "LAPSED_REACTIVATED" if a["reactivated"] else "LAPSED_DORMANT"
        if li is not None and li > e - 6 and li <= e - 3:
            return "BORDERLINE"
        return "EXISTING_ACTIVE"
    truth_hh = []
    for h in hh:
        a = h["account"]
        truth_hh.append({"household_key": h["household_key"], "is_participant_household": True, "account_id": a["account_id"] if a else "",
                         "latent_fandom": h["fandom"], "enrollment_propensity": h["propensity"], "first_registration_year": h["first_year"],
                         "enroll_month": h["enroll_month"], "last_active_year": h["last_active_year"], "true_uplift": fc["true_uplift"],
                         "decay_half_life_months": half, "n_people": h["n_people"], "country": h["country"], "region": h["region"] or "", "market_id": h["market_id"],
                         "had_account_before": h["had_account_before"], "acq_type": h["acq_type"], "truth_status": truth_status(h),
                         "reactivated": bool(a and a["reactivated"]), "reactivation_caused": bool(a and a["react_caused"]),
                         "true_acquisition_lift": aq["true_acquisition_lift"], "true_reactivation_lift": lp["reactivation_lift"],
                         "true_lapse_multiplier_after_child_churn": lp["after_child_churn_multiplier"]})
    for a in accounts:
        if not a["participant"] and a["dup_of"] is None:
            truth_hh.append({"household_key": a["hh"]["household_key"], "is_participant_household": False, "account_id": a["account_id"],
                             "latent_fandom": a["fandom"], "enrollment_propensity": None, "first_registration_year": None, "enroll_month": None, "last_active_year": None,
                             "true_uplift": 0.0, "decay_half_life_months": half, "n_people": 0, "country": a["country"], "region": a["region"] or "", "market_id": a["market"],
                             "had_account_before": None, "acq_type": "NONE", "truth_status": "NON_PARTICIPANT", "reactivated": False, "reactivation_caused": False,
                             "true_acquisition_lift": aq["true_acquisition_lift"], "true_reactivation_lift": lp["reactivation_lift"],
                             "true_lapse_multiplier_after_child_churn": lp["after_child_churn_multiplier"]})
    truth_acct = [{"account_id": a["account_id"], "household_key": a["hh"]["household_key"], "is_participant_household": a["participant"],
                   "email_differs": "email_differs_from_registration" in a["defects"], "phone_shared": "phone_shared_with_participant_household" in a["defects"],
                   "is_duplicate_account": a["dup_of"] is not None, "canonical_account_id": a["dup_of"]["account_id"] if a["dup_of"] else a["account_id"],
                   "duplicate_by_phone": "duplicate_account_by_phone" in a["defects"], "acquisition_source": a["source"], "creation_kind": a["kind"],
                   "market_id": a["market"], "created_year": (a["created_at"].year)} for a in accounts]
    truth_market = []
    for m in mkts:
        for yi, year in enumerate(years):
            rows_ = [a for a in accounts if a["market"] == m["market_id"] and a["dup_of"] is None and a["created_idx"] >= yi * 12 and a["created_idx"] < (yi + 1) * 12]
            truth_market.append({"market_id": m["market_id"], "year": year, "household_population": m["household_population"], "launch_year": m["launch_year"],
                                 "is_team_market": m["is_team_market"], "is_treated": m["launch_year"] is not None and year >= m["launch_year"],
                                 "new_accounts": len(rows_),
                                 "new_accounts_organic": sum(1 for a in rows_ if a["kind"] in ("ORGANIC_NEW", "NET_NEW_ORGANIC")),
                                 "new_accounts_incremental": sum(1 for a in rows_ if a["kind"] == "NET_NEW_INCREMENTAL"),
                                 "new_accounts_existing_participant": sum(1 for a in rows_ if a["kind"] == "EXISTING_PARTICIPANT"),
                                 "true_acquisition_lift": aq["true_acquisition_lift"]})
    truth_consent = [{"account_id": a["account_id"], "channel": ch, "final_status": a["final_consent"][ch] or "none"} for a in accounts for ch in CHANNELS]
    out.extra = {"fan_effect_truth_rows": effect_truth, "fan_truth": truth_hh, "fan_account_truth": truth_acct, "fan_market_truth": truth_market, "fan_consent_truth": truth_consent, "markets": mkts}
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
