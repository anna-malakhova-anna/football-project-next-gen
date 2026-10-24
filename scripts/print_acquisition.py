"""Print acquisition incrementality the way rework step 7 asks to see it: the naive count, the market-level incremental estimate with its range, and the truth, then the event study with its
pre-period. Ground truth is read only through the evaluation models. Counts only.

  uv run python -m scripts.print_acquisition
"""
from __future__ import annotations


import duckdb
from scripts.common import DB



def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    q = lambda sql: con.execute(sql).fetchall()  # noqa: E731
    first, last = q("select min(launch_cohort), max(launch_cohort) from fan.mart_acquisition_incrementality")[0]      # the launch cohorts the estimate covers
    print(f"SYNTHETIC DATA. How many new fan accounts did the programme ADD? (launch cohorts {first} to {last}, years 0 to +3 since launch, inside the data)\n")
    print(f"   {'measure':38s} {'estimate':>9s} {'range':>17s} {'truth':>7s} {'x truth':>8s}")
    for m, e, lo, hi, t, ratio, inside in q("select measure, estimate, ci_low, ci_high, truth, estimate_over_truth, truth_in_range from evaluation.eval_acquisition "
                                           "where measure in ('incremental_accounts', 'naive_net_new_observed', 'naive_net_new_scaled_by_link_rate')"):
        rng = "" if lo is None else f"{lo:,.0f} to {hi:,.0f}"
        print(f"   {m:38s} {e:>9,.0f} {rng:>17s} {t:>7,.0f} {ratio:>7.2f}x" + ("" if inside is None else f"   truth inside range: {inside}"))
    print("\n   incremental = market-level difference-in-differences against not-yet-treated and never-treated markets (stacked by launch cohort, no pooled two-way fixed effects).")
    print("   naive observed = linked households whose account was created after registration (sees only linked households, and counts accounts that would have appeared anyway).")
    print("   naive scaled = that count divided by the link rate: the generous version of 'every account created after a registration'.")
    print("\nEvent study (new accounts per 1,000 households, years since launch; pre-period years should be near zero)")
    print(f"   {'year':>4s} {'estimate':>9s} {'95% interval':>18s} {'truth':>8s}  truth inside interval")
    for k, e, lo, hi, t, ok in q("select years_since_launch, estimate, ci_low, ci_high, truth, truth_in_ci from evaluation.eval_acquisition_event_study order by 1"):
        print(f"   {k:>+4d} {e:>9.3f} {lo:>8.3f} to {hi:>6.3f} {t:>8.3f}  {ok}")
    t = q("select truth from evaluation.eval_acquisition where measure in ('truth_net_new_households', 'truth_incremental_households') order by measure")
    print(f"\n   Households (cohorts {first} to {last}): {int(t[0][0]):,} caused by the programme out of {int(t[1][0]):,} that opened an account after registering.")


if __name__ == "__main__":
    main()
