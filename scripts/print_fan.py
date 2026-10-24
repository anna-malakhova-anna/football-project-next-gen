"""Print the fandom outcomes the way the Phase 4 spec asks to see them: naive vs matched difference-in-differences vs the true uplift, then the
event study and the diagnostics. Ground truth is read only through the evaluation models. Counts and shares only (restricted `linkage` schema).

  uv run python -m scripts.print_fan
"""
from __future__ import annotations


import duckdb
from scripts.common import DB



def pct(v) -> str:
    return "      " if v is None else f"{v * 100:+6.1f}%"


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    q = lambda sql: con.execute(sql).fetchall()  # noqa: E731
    print("SYNTHETIC DATA. Does registering a child raise a household's fan engagement? Estimates describe LINKED households only (ADR-009).\n")
    print("1. Naive vs matched difference-in-differences vs truth (effect on events per household-month)")
    print(f"   {'estimator':14s} {'estimate':>8s} {'95% interval':>17s} {'truth':>8s} {'error':>8s} {'x truth':>8s}  truth inside interval")
    for est, e, lo, hi, tr, err, ratio, inside in q("select estimator, estimate_pct, ci_low_pct, ci_high_pct, true_effect_pct, error_pct_points, estimate_over_truth, truth_in_ci "
                                                  "from evaluation.eval_fan_effect"):
        ci = "" if lo is None else f"{pct(lo).strip()} to {pct(hi).strip()}"
        print(f"   {est:14s} {pct(e)} {ci:>17s} {pct(tr)} {pct(err)} {ratio:>7.2f}x  {'' if inside is None else inside}")
    tp = q("select true_uplift_parameter from evaluation.eval_fan_effect limit 1")[0][0]
    print(f"   (the configured uplift while a child is active is {tp:+.0%}; the truth column is what the matched households actually got over the months averaged, after decay)")
    s = q("select treated_matched, comparison_pairs, comparison_units, eligible_treated, match_rate from linkage.mart_fan_outcomes_summary where estimator = 'DID_ADDITIVE'")[0]
    print(f"\n2. Matching: {s[0]:,} of {s[3]:,} eligible participant households matched ({s[4]:.0%}); {s[1]:,} comparison pairs from {s[2]:,} accounts")

    print("\n3. Event study (effect = participants / matched comparisons - 1; a flat pre period supports the design)")
    for k, t, c, e, se in q("select months_since_event, treated_mean_events, comparison_mean_events, effect_pct, diff_se from linkage.mart_fan_did where months_since_event in (-12, -9, -6, -3, -1, 0, 3, 6, 9, 12, 15, 18) order by 1"):
        print(f"   month {k:+3d}   participants {t:5.2f}   comparisons {c:5.2f}   effect {pct(e)}")
    print("\n4. Diagnostics (ground truth)")
    for m, v in q("select measure, value from evaluation.eval_fan_matching_diagnostics"):
        print(f"   {m:30s} {v:8.3f}")


if __name__ == "__main__":
    main()
