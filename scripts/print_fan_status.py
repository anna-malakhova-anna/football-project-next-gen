"""Print the fan status of participant households the way rework step 5 asks to see it: the distribution, then the observed status against the status the generator knows.
Ground truth is read only through the evaluation model. Counts only (restricted `linkage` schema).

  uv run python -m scripts.print_fan_status
"""
from __future__ import annotations

from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "warehouse" / "flag.duckdb"


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    q = lambda sql: con.execute(sql).fetchall()  # noqa: E731
    print("SYNTHETIC DATA. Fan status of participant households as of the month of their first registration (UNLINKED is unknown, not non-fan).\n")
    print("1. Observed status, all participant households")
    print(f"   {'status':22s} {'households':>10s} {'share':>7s} {'not left-censored':>18s}")
    for s, n, pct, nc in q("select fan_status, count(*), round(100.0 * count(*) / sum(count(*)) over (), 1), count(*) filter (where not is_left_censored) "
                           "from linkage.fct_household_fan_status group by 1 order by 2 desc"):
        print(f"   {s:22s} {n:>10,} {pct:>6.1f}% {nc:>18,}")
    v = q("select count(*) filter (where net_new_via_flag_prompt), count(*) filter (where fan_status = 'NET_NEW') from linkage.fct_household_fan_status")[0]
    print(f"\n   Net-new households whose account came through the flag registration prompt: {v[0]:,} of {v[1]:,}")
    print("\n2. Observed status against the generator's truth (households not left-censored)")
    print(f"   {'observed':22s} {'truth':22s} {'households':>10s}")
    for o, t, n in q("select fan_status, truth_status, households_not_left_censored from evaluation.eval_fan_status where households_not_left_censored > 0 order by 1, 3 desc"):
        print(f"   {o:22s} {t:22s} {n:>10,}")
    u = q("select count(*) filter (where truth_status <> 'NO_ACCOUNT'), count(*) from evaluation.eval_fan_status where fan_status = 'UNLINKED' and false")
    row = q("select sum(households_not_left_censored) filter (where truth_status <> 'NO_ACCOUNT'), sum(households_not_left_censored) from evaluation.eval_fan_status where fan_status = 'UNLINKED'")[0]
    print(f"\n   Of {int(row[1]):,} UNLINKED households, {int(row[0]):,} ({row[0] / row[1]:.0%}) DO have a fan account under a different email: unlinked is not non-fan.")


if __name__ == "__main__":
    main()
