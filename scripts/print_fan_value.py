"""Print the fan value analyses (rework step 8): value uplift among existing and lapsed fans (naive vs matched vs truth), fan survival, lifetime value, activeness and the RFM mix.
Ground truth is read only through the evaluation models. Aggregates only (restricted `linkage` schema); spend is SYNTHETIC CURRENCY.

  uv run python -m scripts.print_fan_value
"""
from __future__ import annotations


import duckdb
from scripts.common import DB



def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    q = lambda sql: con.execute(sql).fetchall()  # noqa: E731
    print("SYNTHETIC DATA, SYNTHETIC CURRENCY. Value of fans the programme reaches.\n")
    print("1. Value uplift among fans who already had an account (matched DiD, per account-month; truth = what the generator gave them)")
    print(f"   {'group':9s} {'outcome':26s} {'households':>10s} {'estimate':>9s} {'95% interval':>17s} {'truth':>8s}  inside")
    for r in q("select status_group, outcome, treated_households, did_per_month, did_ci_low_per_month, did_ci_high_per_month, truth_per_month, truth_in_ci_per_month "
               "from evaluation.eval_fan_value_uplift where outcome in ('events', 'net_spend_total', 'net_spend_ticket', 'net_spend_merch', 'net_spend_subscription') and status_group <> 'ALL' "
               "order by status_group, outcome"):
        print(f"   {r[0]:9s} {r[1]:26s} {r[2]:>10,} {r[3]:>9.3f} {r[4]:>8.3f} to {r[5]:>6.3f} {('' if r[6] is None else f'{r[6]:8.3f}')}  {'' if r[7] is None else r[7]}")
    print("   (EXISTING events: the estimate sits a little above its truth with the truth just outside the interval; reported, not tuned.)")
    print("\n2. Fan survival (share of fans still active, months since origin) and 36-month value")
    print(f"   {'fan group':30s} {'12m':>6s} {'24m':>6s} {'36m':>6s} | {'spend/active mo':>15s} {'LTV 36m':>9s} {'range':>17s}")
    for g, s12, s24, s36, spend, ltv, lo, hi in q("""
        select s.fan_group, max(s.survival) filter (where months_since_origin = 12), max(s.survival) filter (where months_since_origin = 24), max(s.survival) filter (where months_since_origin = 36),
               any_value(l.net_spend_per_active_month), any_value(l.ltv), any_value(l.ltv_low), any_value(l.ltv_high)
        from linkage.mart_fan_survival s join linkage.mart_fan_ltv l on l.fan_group = s.fan_group and l.market_type = s.market_type
        where s.market_type = 'ALL' group by 1 order by 1"""):
        print(f"   {g:30s} {s12:>6.1%} {s24:>6.1%} {s36:>6.1%} | {spend:>15.2f} {ltv:>9.0f} {lo:>8.0f} to {hi:>5.0f}")
    r = q("select measured_rate_ratio, true_hazard_multiplier from evaluation.eval_fan_lapse_after_child_churn")[0]
    print(f"\n3. Do fans lapse faster once the child stops playing? Association only: lapse rate x{r[0]:.2f} after (the generator built in a hazard multiplier of {r[1]:.1f}).")
    print("\n4. RFM segment mix at the end of the last year")
    print(f"   {'fan group':30s} " + " ".join(f"{s:>12s}" for s in ["Champions", "Loyal", "Promising", "At risk", "Hibernating"]))
    for g in [r[0] for r in q("select distinct fan_group from linkage.mart_fan_rfm order by 1")]:
        shares = dict(q(f"select segment, share_of_group from linkage.mart_fan_rfm where fan_group = '{g}' and year = (select max(year) from linkage.mart_fan_rfm)"))
        print(f"   {g:30s} " + " ".join(f"{shares.get(s, 0):>11.0%} " for s in ["Champions", "Loyal", "Promising", "At risk", "Hibernating"]))


if __name__ == "__main__":
    main()
