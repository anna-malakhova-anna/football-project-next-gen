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
    rows.append({"param": "retention_survival_tolerance", "value": c5["retention"]["survival_tolerance"],
                 "description": "phase5.retention.survival_tolerance: a retention figure survives the zone deletion when it moves by no more than this share"})
    return [{k: str(v) for k, v in r.items()} for r in rows]


def main(cfg: dict | None = None, out: str = "dbt/seeds/p5_params.csv") -> int:
    rows = build_rows(cfg or load_config())
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["param", "value", "description"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return len(rows)




def _read(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


STATE_NAMES = {"AZ": "Arizona", "CA": "California", "CO": "Colorado", "CT": "Connecticut", "FL": "Florida", "GA": "Georgia", "IL": "Illinois", "MA": "Massachusetts", "NJ": "New Jersey",
               "NY": "New York", "OH": "Ohio", "PA": "Pennsylvania", "TX": "Texas", "WA": "Washington"}


def plain_market_name(market_id: str) -> str:
    """"Georgia market 2" from CM-GA-02. A default the program owner may replace with approximate metro names ("Atlanta area"); never a team name."""
    if market_id == "NO_CLUB_MARKET":
        return "Outside any club market"
    return f"{STATE_NAMES.get(market_id[3:5], market_id[3:5])} market {int(market_id[-2:])}"


NOTE = "PROJECT APPROXIMATION: contiguous ZIP3 groups; not any club's actual territory definition. Shared markets split equally (default, labelled)."


def club_market_rows(cfg: dict, geo: list[dict]) -> list[dict]:
    """ZIP3 -> club market, with allocation weights that sum to 1 per ZIP3. 32 markets plus NO_CLUB_MARKET. Deterministic from the ZIP3 universe and phase5.club_markets."""
    c = cfg["phase5"]["club_markets"]
    by_state: dict[str, list[str]] = {}
    state_of_market = {}
    import csv as _csv
    with open("dbt/seeds/market_map.csv", newline="", encoding="utf-8") as fh:
        for m in _csv.DictReader(fh):
            state_of_market[m["market_id"]] = m["region_code"]
    for g in geo:
        if g["country_code"] == "US":
            by_state.setdefault(state_of_market[g["market_id"]], []).append(g["prefix"])
    assign: dict[str, list[tuple[str, float, str]]] = {}                 # zip3 -> [(club_market_id, weight, method)]
    groups: dict[tuple[str, int], list[str]] = {}
    for st, prefixes in sorted(by_state.items()):
        prefixes = sorted(prefixes)
        k = c["per_state"][st]
        for i in range(k):
            lo, hi = round(i * len(prefixes) / k), round((i + 1) * len(prefixes) / k)
            groups[(st, i + 1)] = prefixes[lo:hi]
            for z in prefixes[lo:hi]:
                assign[z] = [(f"CM-{st}-{i + 1:02d}", 1.0, "CONTIGUOUS_ZIP3_GROUP")]
    for st in c["shared_within_state"]["states"]:
        g1 = groups[(st, 1)]
        n = max(1, round(c["shared_within_state"]["zip3_share"] * len(g1)))
        for z in g1[-n:]:
            assign[z] = [(f"CM-{st}-01", 0.5, "SHARED_EQUAL_SPLIT"), (f"CM-{st}-02", 0.5, "SHARED_EQUAL_SPLIT")]
    x = c["shared_cross_state"]
    g1 = groups[(x["from_state"], 1)]
    for z in g1[:max(1, round(x["zip3_share"] * len(g1)))]:
        assign[z] = [(f"CM-{x['from_state']}-01", 0.5, "SHARED_EQUAL_SPLIT"), (f"CM-{x['with_state']}-01", 0.5, "SHARED_EQUAL_SPLIT")]
    uncovered = max(1, round(c["uncovered_zip3_share"] * sum(len(v) for v in by_state.values())))
    candidates = [z for st in sorted(by_state) for z in sorted(by_state[st])[-1:] if len(assign[z]) == 1]            # the last ZIP3 of each state's last market
    for z in candidates[:uncovered]:
        assign[z] = [("NO_CLUB_MARKET", 1.0, "NO_CLUB_MARKET")]
    state_of_zip = {z: st for st, ps in by_state.items() for z in ps}
    out = []
    for z in sorted(assign):
        w = assign[z]
        assert abs(sum(x[1] for x in w) - 1.0) < 1e-9
        for cm, weight, method in w:
            name = "No club market" if cm == "NO_CLUB_MARKET" else f"{cm[3:5]} club market {cm[-2:]}"          # named from its id, so a market shared across two states has one name
            out.append({"zip3": z, "club_market_id": cm, "market_name": name, "plain_name": plain_market_name(cm), "state": state_of_zip[z], "allocation_weight": weight, "mapping_method": method, "approximation_note": NOTE})
    return out


def _write(path: str, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main_market_seeds(cfg: dict | None = None, seeds: str = "dbt/seeds") -> None:
    cfg = cfg or load_config()
    geo = _read(f"{seeds}/market_geo_map.csv")
    _write(f"{seeds}/club_market_map.csv", ["zip3", "club_market_id", "market_name", "plain_name", "state", "allocation_weight", "mapping_method", "approximation_note"], club_market_rows(cfg, geo))
    # population denominators are NEVER invented (Phase 3 rule): a header-only seed that Anna fills from the Census ACS (scripts/fetch_acs_youth_population.py), or leaves empty
    pd = Path(f"{seeds}/population_denominators.csv")
    if not pd.exists():
        _write(str(pd), ["country_code", "region_code", "zip3", "age_band", "year", "population", "source_name", "source_table_id", "source_url", "retrieved_date"], [])


if __name__ == "__main__":
    print(f"{main()} Phase 5 parameters written")
    main_market_seeds()
