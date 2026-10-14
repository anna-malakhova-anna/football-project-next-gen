"""Export the Phase 5 scorecard parameters from config/generation.yaml to dbt/seeds/p5_params.csv, so dbt never hard-codes a threshold or a season start."""
from __future__ import annotations

import csv
from pathlib import Path

from generator.population import load_config


def build_rows(cfg: dict) -> list[dict]:
    c5 = cfg["phase5"]
    rows = [{"param": f"season_start_{term.lower()}", "value": md, "description": f"Month-day the {term.title()} season starts (an assumption for the demonstration)."}
            for term, md in c5["season_start"].items()]
    rows += [{"param": k, "value": v, "description": f"phase5.dq.{k} in config/generation.yaml"} for k, v in c5["dq"].items()]
    return [{k: str(v) for k, v in r.items()} for r in rows]


def main(cfg: dict | None = None, out: str = "dbt/seeds/p5_params.csv") -> int:
    rows = build_rows(cfg or load_config())
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["param", "value", "description"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return len(rows)




CLUB_PLACES = ["North Ridge", "Harbor Point", "Cedar Valley", "Stone Creek", "Lakeshore", "Red Mesa", "Pine Hollow", "Blue Bay", "Iron Hill", "Sunfield", "Maple Crossing",
               "Westgate", "Riverbend", "Copper Run", "Eagle Pass", "Fox Meadow", "Granite Falls", "Highland", "Juniper", "Kestrel Ridge"]


def _read(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def territory_rows(cfg: dict, markets: list[dict]) -> tuple[list[dict], list[dict]]:
    """Synthetic club territories over the US markets: -> (club_territory rows, club rows). Shared metros and uncovered markets come from phase5.club_design."""
    d = cfg["phase5"]["club_design"]
    by_state: dict[str, list[dict]] = {}
    for m in markets:
        if m["country_code"] == "US":
            by_state.setdefault(m["region_code"], []).append(m)
    names = iter(CLUB_PLACES)
    clubs, rows = [], []
    for st in sorted(by_state):
        ms = sorted(by_state[st], key=lambda m: m["market_id"])
        n_clubs = d["clubs_per_state"].get(st, 1)
        st_clubs = [{"club_id": f"CLUB-{st}-{i + 1}", "club_name": f"{next(names)} Flag Club (synthetic)", "state": st} for i in range(n_clubs)]
        clubs += st_clubs
        n_unc = d["uncovered_markets"].get(st, 0)
        covered = ms[:len(ms) - n_unc] if n_unc else ms
        for i, m in enumerate(covered):
            if st in d["shared_states"] and i == 0 and len(st_clubs) > 1:
                for c in st_clubs:
                    rows.append({"club_id": c["club_id"], "market_id": m["market_id"], "role": "SHARED"})
            else:
                rows.append({"club_id": st_clubs[i % len(st_clubs)]["club_id"], "market_id": m["market_id"], "role": "PRIMARY"})
    return rows, clubs


def census_rows(cfg: dict, markets: list[dict], geo: list[dict]) -> list[dict]:
    """SYNTHETIC youth population (5 to 17) per ZIP3: the market's invented household population spread over its prefixes, times a youth-per-household ratio, with noise."""
    import random
    c = cfg["phase5"]["census_stub"]
    rng = random.Random(cfg["seed"] + cfg["phase5"]["seed_offset"] + 2)
    hh = {m["market_id"]: int(m["household_population"]) for m in markets if m["household_population"]}
    prefixes: dict[str, list[str]] = {}
    for g in geo:
        if g["country_code"] == "US":
            prefixes.setdefault(g["market_id"], []).append(g["prefix"])
    out = []
    for mid in sorted(prefixes):
        for pre in sorted(prefixes[mid]):
            pop = hh[mid] / len(prefixes[mid]) * c["youth_per_household"] * (1 + rng.uniform(-c["noise"], c["noise"]))
            out.append({"zip3": pre, "market_id": mid, "youth_population_5_17": round(pop), "source": "SYNTHETIC STUB: not US Census / ACS data"})
    return out


def _write(path: str, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main_market_seeds(cfg: dict | None = None, seeds: str = "dbt/seeds") -> None:
    cfg = cfg or load_config()
    markets, geo = _read(f"{seeds}/market_map.csv"), _read(f"{seeds}/market_geo_map.csv")
    terr, clubs = territory_rows(cfg, markets)
    _write(f"{seeds}/p5_club_territory.csv", ["club_id", "market_id", "role"], terr)
    _write(f"{seeds}/p5_club.csv", ["club_id", "club_name", "state"], clubs)
    _write(f"{seeds}/p5_youth_population_zip3.csv", ["zip3", "market_id", "youth_population_5_17", "source"], census_rows(cfg, markets, geo))


if __name__ == "__main__":
    print(f"{main()} Phase 5 parameters written")
    main_market_seeds()
