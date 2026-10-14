"""Print the minimization frontier (Phase 5 spec 7): what each variant costs in identity accuracy and data fitness, and what it buys in privacy.

  uv run python -m scripts.print_minimize
"""
from __future__ import annotations

from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "warehouse" / "flag.duckdb"


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    try:
        rows = con.execute("""select variant_id, label, matcher, precision, recall, f1, sibling_or_twin_false_merges, participant_count_error_pct, pct_unique, pct_rows_below_k_min, smallest_class,
                                     fit_for_count, fit_for_segment, fit_for_geo, fit_for_retain, fit_for_activate, rules_no_longer_evaluable, contact_fields_held
                              from evaluation.eval_minimization_tradeoff where matcher is not null order by sort_order, matcher""").fetchall()
    finally:
        con.close()
    if not rows:
        raise SystemExit("no runs yet: run `make minimize`")
    print("MINIMIZATION FRONTIER (synthetic data; accuracy is graded against the answer key, risk and fitness are label-free)\n")
    print("headline matcher: Fellegi-Sunter, before review, automatic links only. The rules matcher is shown beneath it.\n")
    print(f"  {'variant':18} {'matcher':7} {'precision':>9} {'recall':>7} {'sib/twin':>8} {'count err%':>10} | {'% unique':>8} {'% k<k_min':>9} {'min class':>9} {'contact':>7} | "
          f"{'count':>5} {'segm.':>5} {'geo':>5} {'retain':>6} {'activ.':>6}")
    for r in rows:
        v, _, m, p, rec, _f1, sib, err, uniq, below, smallest, fc, fs, fg, fr, fa, _dropped, contact = r
        print(f"  {v:18} {m:7} {p:9.4f} {rec:7.4f} {sib:8d} {err:10.2f} | {uniq:8.2f} {below:9.2f} {smallest:9d} {contact:7d} | {fc:5.3f} {fs:5.3f} {fg:5.3f} {fr:6.3f} {fa:6.3f}")
    print("\n  sib/twin = predicted people holding two true people of one household (a privacy incident). count err% = predicted vs true participants.")
    print("  % unique = participant-years alone in their (year, DOB, postal, sex, country) class; % k<k_min = in a class smaller than k_min. contact = guardian contact fields held.")
    print("  Fitness can only rise when a variant removes a check (lost detection, not gained quality); a hashed email reaches no guardian, so ACTIVATE is zero.")


if __name__ == "__main__":
    main()
