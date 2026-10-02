"""Print the retention results the way the Phase 4 spec asks to see them: Kaplan-Meier against the generator's true churn parameters, then the naive
age-out-as-churn version beside the correct one. Also writes CSVs to docs/eval/. Ground truth is read only through the evaluation model.

  uv run python -m scripts.print_retention
"""
from __future__ import annotations

import csv
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "warehouse" / "flag.duckdb"
OUT = ROOT / "docs" / "eval"


def pct(v) -> str:
    return "" if v is None else f"{v * 100:5.1f}%"


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    q = lambda sql: con.execute(sql).fetchall()  # noqa: E731
    print("SYNTHETIC DATA. Truth below is the generator's churn parameters, used only to grade the estimates.\n")

    print("1. Kaplan-Meier vs truth, all entrants (entry cohorts 2022 onwards; 2021 is the left-censored first year)")
    print(f"{'k':>2} {'at risk':>8} {'KM':>8} {'95% CI':>17} {'truth':>8} {'error':>8} {'inside CI':>10}")
    for k, n, km, lo, hi, tr, err, ok in q("select years_since_entry, at_risk, km_survival, km_ci_low, km_ci_high, true_survival, km_error, truth_in_ci "
                                           "from evaluation.eval_retention where segment_type = 'ALL' order by 1"):
        print(f"{k:>2} {n:>8} {pct(km):>8} {pct(lo) + ' to' + pct(hi):>17} {pct(tr):>8} {err * 100:+7.1f}p {str(ok):>10}")

    cov = q("select count(*), avg(truth_in_ci::int), avg(abs(km_error)), avg(abs(naive_error)) from evaluation.eval_retention where reliable")[0]
    print(f"\n   Across all {cov[0]} reliable segment cells (>= k_min at risk): truth inside the 95% interval in {cov[1]:.1%}; "
          f"mean absolute error KM {cov[2] * 100:.1f} pts vs naive {cov[3] * 100:.1f} pts")

    print("\n2. Naive (age-out counted as churn) vs censored (correct), by entry age band, one and two years after entry")
    print(f"{'entry age':>9} {'k':>2} {'at risk':>8} {'truth':>8} {'KM':>8} {'naive':>8} {'naive understates by':>22}")
    for seg, k, n, tr, km, nv, gap in q("select segment_value, years_since_entry, at_risk, true_survival, km_survival, naive_survival, naive_understates_by "
                                        "from evaluation.eval_retention where segment_type = 'entry_age_band' and years_since_entry <= 2 order by 1, 2"):
        flag = "  <== age-outs counted as churn" if gap > 0.05 else ""
        print(f"{seg:>9} {k:>2} {n:>8} {pct(tr):>8} {pct(km):>8} {pct(nv):>8} {gap * 100:>20.1f}p{flag}")

    OUT.mkdir(parents=True, exist_ok=True)
    for name, sql in (("retention_km_vs_truth.csv", "select * from evaluation.eval_retention order by segment_type, segment_value, years_since_entry"),
                      ("retention_survival.csv", "select * exclude (methodology_version) from retention.mart_retention_survival order by 1, 2, 4")):
        cur = con.execute(sql)
        with open(OUT / name, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([d[0] for d in cur.description])
            w.writerows(cur.fetchall())
    print("\nwrote docs/eval/retention_km_vs_truth.csv, docs/eval/retention_survival.csv")


if __name__ == "__main__":
    main()
