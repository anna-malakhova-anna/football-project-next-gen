"""Fetch US youth population (ages 5 to 17) by ZIP3 from the Census ACS and write dbt/seeds/population_denominators.csv. RUN THIS YOURSELF; it is never part of the build.

  uv run python scripts/fetch_acs_youth_population.py [--year 2023]

Why a script and not data: Phase 3 rule, population figures are never invented. The seed stays EMPTY until you run this, and while it is empty every participation rate in the project reads
"denominator not loaded". Every row written carries the source name, the ACS table id, the URL and the retrieval date, so a rate computed from it can cite its denominator.

What it does: calls the Census API for the 5-year ACS table B01001 (sex by age) for every ZIP Code Tabulation Area, sums the male and female counts of ages 5 to 9, 10 to 14 and 15 to 17,
and aggregates ZCTA to ZIP3 by the first three digits. A ZCTA is an approximation of a ZIP code, and ZIP3 is an aggregation of them: the rates are ILLUSTRATIVE ("synthetic participant counts over
real population denominators"). NOT TESTED against the live API from the build environment: check the output before relying on it.
Variables (B01001): male 5-9 _004E, 10-14 _005E, 15-17 _006E; female 5-9 _028E, 10-14 _029E, 15-17 _030E.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "dbt" / "seeds" / "population_denominators.csv"
FIELDS = ["country_code", "region_code", "zip3", "age_band", "year", "population", "source_name", "source_table_id", "source_url", "retrieved_date"]
VARS = [f"B01001_{n:03d}E" for n in (4, 5, 6, 28, 29, 30)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2023, help="ACS 5-year vintage")
    args = ap.parse_args()
    url = f"https://api.census.gov/data/{args.year}/acs/acs5?get={','.join(VARS)}&for=zip%20code%20tabulation%20area:*"
    with urllib.request.urlopen(url, timeout=60) as resp:
        rows = json.load(resp)
    header, data = rows[0], rows[1:]
    idx = {name: i for i, name in enumerate(header)}
    by_zip3: dict[str, int] = defaultdict(int)
    for r in data:
        z = r[idx["zip code tabulation area"]]
        by_zip3[z[:3]] += sum(int(r[idx[v]] or 0) for v in VARS)
    today = dt.date.today().isoformat()
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for z3, pop in sorted(by_zip3.items()):
            w.writerow({"country_code": "US", "region_code": "", "zip3": z3, "age_band": "5-17", "year": args.year, "population": pop,
                        "source_name": f"US Census Bureau, American Community Survey 5-year estimates {args.year}", "source_table_id": "B01001",
                        "source_url": url, "retrieved_date": today})
    print(f"{len(by_zip3)} ZIP3 rows written to {OUT}. Illustrative only: synthetic participant counts over real population denominators.")


if __name__ == "__main__":
    main()
