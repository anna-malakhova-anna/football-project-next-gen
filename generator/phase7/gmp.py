"""Phase 7: the Global outlook's answer key for the dark markets, and the GMP_PROXY source. SYNTHETIC data.

Rules fixed in ADR-025 (and its addendum) before this file first ran. Isolated scope: its own random stream (seed + phase7.seed_offset), and it only READS
the existing truth (participation plan), so no Phase 1-6 file or number changes.

  Answer key (truth_dir/gmp_market_truth.parquet, evaluation only): the 15 program markets with no participation source. True participants per season,
  sized around the median latest-season true size of the INTL_FED markets, only weakly related to clubs with rights. In a configured share of them the
  latest true direction is set AGAINST the true direction of their comparables (markets with data, same region and regime, else region, else all):
  an ASSUMPTION representing the risk that a market moves against its neighbours, not a fact about any real market.
  GMP_PROXY (raw_dir/gmp_proxy/proxy_returns_<year>.csv): club-filed returns per market and season: club fan events, games in the market, whether a
  national flag federation exists. Aggregate-only. Weakly related to true participation. Clubs file for every market with data and for a configured
  share of the dark markets (never for the forced-dark walkthrough market). Some returns are filed twice by two clubs; some leave the events blank.
"""
from __future__ import annotations

import csv
import datetime as dt
import math
import random
import shutil
import statistics
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from generator import population

SEEDS = Path("dbt/seeds")
COLUMNS = ["market", "season", "club_events", "games_in_market", "federation_exists", "reported_by", "report_date"]
DUPLICATE_SHARE = 0.03          # returns filed twice by two clubs (staging keeps one; the contract warns above 1%)
BLANK_EVENTS_SHARE = 0.05       # returns that leave club_events blank


def _csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _poisson(rng: random.Random, lam: float) -> int:
    if lam > 30:                                    # normal approximation keeps big means fast
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    k, p, limit = 0, 1.0, math.exp(-lam)
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _direction(g: float | None, band: float) -> str | None:
    if g is None:
        return None
    return "GROWING" if g > band else "SHRINKING" if g < -band else "FLAT"


def build(cfg: dict) -> tuple[list[dict], list[dict]]:
    p7, years = cfg["phase7"], cfg["seasons"]["years"]
    rng = random.Random(cfg["seed"] + p7["seed_offset"])
    markets = {m["country_code"]: m for m in _csv(SEEDS / "gmp_markets.csv")}
    clubs: dict[str, list[str]] = defaultdict(list)
    for r in _csv(SEEDS / "gmp_club_rights.csv"):
        clubs[r["country_code"]].append(r["club_id"])

    # existing truth: true participants per country and season (read only)
    plan = pq.read_table(Path(cfg["paths"]["ground_truth_dir"]) / "participation_plan.parquet").to_pylist()
    persons: dict[tuple, set] = defaultdict(set)
    source_of: dict[str, str] = {}
    for r in plan:
        if r["country_code"] in markets:
            persons[(r["country_code"], r["season_year"])].add(r["true_person_id"])
            source_of[r["country_code"]] = r["source_system"]
    true_n = {k: len(v) for k, v in persons.items()}
    data_markets = sorted(source_of)
    dark = sorted(c for c in markets if c not in source_of)
    last, prev = years[-1], years[-2]
    median = statistics.median(true_n.get((c, last), 0) for c in data_markets if source_of[c] == "INTL_FED")

    t = p7["truth"]
    band = t["flat_band"]

    def comparables(c: str) -> tuple[str, list[str]]:
        m = markets[c]
        same = [d for d in data_markets if markets[d]["region"] == m["region"] and markets[d]["legal_regime_id"] == m["legal_regime_id"]]
        if same:
            return "REGION_AND_REGIME", same
        region = [d for d in data_markets if markets[d]["region"] == m["region"]]
        return ("REGION", region) if region else ("ALL", list(data_markets))

    def group_growth(group: list[str]) -> float | None:
        both = [d for d in group if true_n.get((d, prev)) and true_n.get((d, last))]       # like for like: markets present in both seasons
        a, b = sum(true_n[(d, prev)] for d in both), sum(true_n[(d, last)] for d in both)
        return (b - a) / a if a else None

    # latest true level: lognormal around the data-markets' median, weakly correlated with (standardized log) clubs with rights
    logc = {c: math.log(len(clubs[c])) for c in dark}
    mu, sd = statistics.mean(logc.values()), statistics.pstdev(logc.values()) or 1.0
    rho = t["level_club_correlation"]
    against = set(rng.sample(dark, round(t["share_against_comparables"] * len(dark))))
    truth = []
    for c in dark:
        z = (logc[c] - mu) / sd
        level = median * math.exp(t["base_participants_sigma"] * (rho * z + math.sqrt(1 - rho * rho) * rng.gauss(0, 1)))
        basis, comp = comparables(c)
        comp_dir = _direction(group_growth(comp), band)
        size = band + abs(rng.gauss(0, t["growth_sd"]))
        if c in against:
            sign = {"GROWING": -1, "SHRINKING": 1}.get(comp_dir) or rng.choice([-1, 1])
            g_last = sign * size
        else:
            g_last = {"GROWING": size, "SHRINKING": -size}.get(comp_dir) if comp_dir in ("GROWING", "SHRINKING") else rng.uniform(-band, band) * 0.9
        growth = {last: g_last}
        for y in years[-2:0:-1]:                                                          # earlier pairs: free draws
            growth[y] = max(-0.6, rng.gauss(t["growth_mean"], t["growth_sd"]))
        level_by_year = {last: level}
        for y in reversed(years[:-1]):
            level_by_year[y] = level_by_year[years[years.index(y) + 1]] / (1 + growth[years[years.index(y) + 1]])
        for y in years:
            n = max(1, round(level_by_year[y]))
            g = growth.get(y) if y != years[0] else None
            truth.append({"country_code": c, "season_year": y, "true_participants": n, "true_growth": round(g, 6) if g is not None else None,
                          "true_direction": _direction(g, band), "set_against_comparables": c in against, "comparable_basis": basis,
                          "comparable_markets": "|".join(comp), "comparables_true_direction": comp_dir, "data_market_median": median})
    truth_level = {(r["country_code"], r["season_year"]): r["true_participants"] for r in truth}
    truth_level.update(true_n)

    # GMP_PROXY: which markets get club returns
    pr = p7["proxy"]
    forced = set(pr["force_dark"])
    eligible = [c for c in dark if c not in forced]
    reporting = set(data_markets) | set(rng.sample(eligible, round(pr["reporting_share_dark"] * len(dark))))
    federation = {c: (c in source_of) or rng.random() < pr["federation_exists_share"] for c in sorted(markets)}
    rows = []
    for y in years:
        for c in sorted(reporting):
            ratio = max(truth_level.get((c, y), 0), 0.25 * median) / median
            lam = pr["events_per_club_mean"] * len(clubs[c]) * ratio ** pr["events_truth_weight"]
            reporter = rng.choice(sorted(clubs[c]))
            row = {"market": markets[c]["country_name"], "season": str(y), "club_events": str(_poisson(rng, lam)),
                   "games_in_market": str(int(rng.random() < pr["games_market_share"])), "federation_exists": "Y" if federation[c] else "N",
                   "reported_by": reporter, "report_date": (dt.date(y, 12, 1) + dt.timedelta(days=rng.randint(0, 60))).isoformat()}
            rows.append(row)
    # defects at exact counts, round(rate * rows), as in the other sources
    for i in rng.sample(range(len(rows)), round(BLANK_EVENTS_SHARE * len(rows))):
        rows[i]["club_events"] = ""
    dups = []
    code = {m["country_name"]: k for k, m in markets.items()}
    shared = [i for i, r in enumerate(rows) if len(clubs[code[r["market"]]]) > 1]           # only a market with two clubs can be filed twice
    for i in sorted(rng.sample(shared, round(DUPLICATE_SHARE * len(rows)))):
        row = rows[i]
        c = code[row["market"]]
        others = [f for f in sorted(clubs[c]) if f != row["reported_by"]]
        lam = pr["events_per_club_mean"] * len(clubs[c])
        dups.append(dict(row, reported_by=rng.choice(others), club_events=str(_poisson(rng, lam)),   # a second club files the same market-season, its own numbers
                         report_date=(dt.date.fromisoformat(row["report_date"]) + dt.timedelta(days=rng.randint(1, 20))).isoformat()))
    rows.extend(dups)
    return truth, rows


def run(cfg: dict | None = None, raw_dir: str | None = None, truth_dir: str | None = None) -> dict:
    cfg = cfg or population.load_config()
    raw = Path(raw_dir or cfg["paths"]["raw_dir"]) / "gmp_proxy"
    truth_out = Path(truth_dir or cfg["paths"]["ground_truth_dir"])
    truth, rows = build(cfg)
    shutil.rmtree(raw, ignore_errors=True)
    raw.mkdir(parents=True)
    for y in cfg["seasons"]["years"]:
        with open(raw / f"proxy_returns_{y}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(r for r in rows if r["season"] == str(y))
    pq.write_table(pa.Table.from_pylist(truth), truth_out / "gmp_market_truth.parquet")
    return {"gmp_proxy_rows": len(rows), "gmp_market_truth_rows": len(truth), "dark_markets": len({r["country_code"] for r in truth})}


if __name__ == "__main__":
    print(run())
