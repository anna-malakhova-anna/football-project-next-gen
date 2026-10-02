"""Synthetic markets (ALL SYNTHETIC: no real metro boundaries, no real population figures).

A market is a group of US ZIP3 prefixes, Canadian forward sortation areas (FSAs) or a whole international country. Markets carry a synthetic household population (the
denominator for "per 1,000 households"), a team-market flag, and a programme LAUNCH YEAR: flag football registrations in a market start only after its launch year, and
some markets never launch. The staggered launches are what make acquisition incrementality measurable (rework spec, section 5.2).

Everything here is derived from config (`markets:`) with its own seeded random stream, so the market table does not depend on the order of any other draw. The same
function builds the dbt seeds (`market_map.csv`, `market_geo_map.csv`), so the generator and the analysis can never disagree about which prefix is which market.
"""
from __future__ import annotations

import random

CA_FSA_LETTERS = "ABCEGHJKLMNPRSTVXY"


def _split(items: list, n: int) -> list[list]:
    """n contiguous, near-equal chunks."""
    base, extra = divmod(len(items), n)
    out, i = [], 0
    for k in range(n):
        size = base + (1 if k < extra else 0)
        out.append(items[i:i + size])
        i += size
    return out


def build_markets(cfg: dict) -> dict:
    """-> {"markets": [dict], "geo": [dict]}. Deterministic for a given config."""
    from generator.population import CA_POSTAL_LETTERS, US_REGIONS   # imported here: population imports this module

    mc = cfg["markets"]
    rng = random.Random(cfg["seed"] + mc.get("seed_offset", 7))
    markets: list[dict] = []
    geo: list[dict] = []

    def add(country, region, prefixes, prefix_kind):
        mid = f"MKT-{len(markets) + 1:02d}"
        markets.append({"market_id": mid, "country_code": country, "region_code": region or "", "_prefixes": prefixes, "_kind": prefix_kind})
        for p in prefixes:
            geo.append({"country_code": country, "prefix": p, "market_id": mid})
        return mid

    for state, (lo, hi), _w in US_REGIONS:
        n = mc["us_markets_per_state"].get(state, 0)
        if n:
            for chunk in _split([f"{z:03d}" for z in range(lo, hi + 1)], n):
                add("US", state, chunk, "zip3")
    for prov, n in mc["ca_markets_per_province"].items():
        fsas = [f"{first}{d}{letter}" for first in CA_POSTAL_LETTERS[prov] for d in range(10) for letter in CA_FSA_LETTERS]
        rng2 = random.Random(cfg["seed"] + 11 + sum(map(ord, prov)))
        rng2.shuffle(fsas)                                      # FSAs of one province are spread over its markets, not contiguous
        for chunk in _split(fsas, n):
            add("CA", prov, sorted(chunk), "fsa")
    for country, n in mc["intl_markets"].items():
        for _ in range(n):
            add(country, "", [], "country")                      # no postal code on international returns: the country is the market

    # ---- launch years: counts among US and CA markets; INTL launch years are listed in config ----
    usca = [m for m in markets if m["country_code"] in ("US", "CA")]
    order = usca[:]
    rng.shuffle(order)
    launches = mc["launches"]
    plan = [y for y in sorted(k for k in launches if k != "never") for _ in range(launches[y])] + ["never"] * launches["never"]
    if len(plan) != len(order):
        raise ValueError(f"markets.launches adds up to {len(plan)} but there are {len(order)} US and CA markets")
    for m, y in zip(order, plan):
        m["launch_year"] = None if y == "never" else int(y)
    for m in markets:
        if m["country_code"] not in ("US", "CA"):
            m["launch_year"] = int(mc["intl_launch_years"][m["country_code"]])

    # ---- synthetic households, team markets, names ----
    lo, hi = mc["household_population_range"]
    n_team = round(mc["team_market_share"] * len(markets))
    team = set(rng.sample([m["market_id"] for m in markets], n_team))
    for i, m in enumerate(markets, start=1):
        m["household_population"] = int(round(rng.uniform(lo, hi), -2))
        m["is_team_market"] = m["market_id"] in team
        where = m["region_code"] or m["country_code"]
        m["market_name"] = f"Market {i:02d} ({where})"
        m["notes"] = "synthetic market: not a real metro area; household_population is invented"
    for m in markets:
        m["n_prefixes"] = len(m["_prefixes"])
    return {"markets": markets, "geo": geo}


def last_year(cfg: dict) -> int:
    return int(cfg["seasons"]["years"][-1])


def launched(markets: list[dict], country: str, by_year: int) -> list[dict]:
    """Markets in a country whose launch year is on or before `by_year` (never-launched markets are excluded)."""
    return [m for m in markets if m["country_code"] == country and m["launch_year"] is not None and m["launch_year"] <= by_year]
