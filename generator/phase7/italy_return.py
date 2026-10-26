"""Phase 7 step 8: Italy's first minimum return, for the onboarding experiment on a COPY of the warehouse (ADR-030). SYNTHETIC data.

The Italian federation (synthetic) reports the latest season in the minimum-return template (contracts/templates/GMP_MINIMUM_RETURN.yml): counts of
teams and players by region and age band, girls, boys and sex not recorded. Its total is the answer key's true participants for Italy that season,
so the experiment can show what a first real return would have said against the planning scenario. Own random stream (seed + phase7.seed_offset + 1);
never written to the published raw folder.
"""
from __future__ import annotations

import csv
import math
import random
from pathlib import Path

import pyarrow.parquet as pq

COLUMNS = ["season", "region", "age_band", "teams", "girls", "boys", "sex_not_recorded", "players"]
REGIONS = ["Nord", "Centro", "Sud e Isole"]
AGE_BANDS = ["U10", "U12", "U14", "U17", "ADULT"]
GIRLS_SHARE = 0.35          # an assumption for the demonstration
PLAYERS_PER_TEAM = 8        # roster size the federation reports teams from (at least the template's minimum of 5)


def build(cfg: dict, country: str = "IT", truth_dir: str | None = None) -> tuple[int, list[dict]]:
    truth = pq.read_table(Path(truth_dir or cfg["paths"]["ground_truth_dir"]) / "gmp_market_truth.parquet").to_pylist()
    season = max(r["season_year"] for r in truth)
    total = next(r["true_participants"] for r in truth if r["country_code"] == country and r["season_year"] == season)
    rng = random.Random(cfg["seed"] + cfg["phase7"]["seed_offset"] + 1)
    cells = [(g, a) for g in REGIONS for a in AGE_BANDS]
    weights = [rng.random() + 0.2 for _ in cells]
    raw = [total * w / sum(weights) for w in weights]
    counts = [math.floor(x) for x in raw]
    for i in sorted(range(len(cells)), key=lambda i: raw[i] - counts[i], reverse=True)[: total - sum(counts)]:   # largest remainders: the cells sum to the total
        counts[i] += 1
    for i, n in enumerate(counts):                                     # a round total would fail the template's estimate check: move one player on
        if n >= 50 and n % 50 == 0:
            counts[i] -= 1
            counts[(i + 1) % len(counts)] += 1
    rows = []
    for (region, band), n in zip(cells, counts):
        if n < 5:                                                      # too few for one team: the federation folds them into the next cell's count
            continue
        unknown = 1 if rng.random() < 0.3 else 0
        girls = min(n - unknown, round(n * GIRLS_SHARE + rng.uniform(-2, 2)))
        rows.append({"season": str(season), "region": region, "age_band": band, "teams": str(max(1, n // PLAYERS_PER_TEAM)), "girls": str(girls),
                     "boys": str(n - unknown - girls), "sex_not_recorded": str(unknown), "players": str(n)})
    dropped = total - sum(int(r["players"]) for r in rows)
    if dropped:                                                        # keep the return's total equal to the season's players
        top = max(rows, key=lambda r: int(r["players"]))
        top["players"] = str(int(top["players"]) + dropped)
        top["boys"] = str(int(top["boys"]) + dropped)
    return season, rows


def write(rows: list[dict], season: int, raw_dir: Path, country: str = "IT") -> Path:
    out = raw_dir / "gmp_minimum_return" / f"minimum_return_{country}_{season}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return out
