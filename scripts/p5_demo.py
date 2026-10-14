"""Phase 5 demo: one club market through the seven steps of the two-audience path (spec section 13). SYNTHETIC data; the market is a project approximation of ZIP3 groups, not any club's territory.

  uv run python -m scripts.p5_demo [--market CM-GA-02] [--interactive] [--no-answer-key]

Prerequisites: a built warehouse (`make all-phases`, or `make dq nuance markets minimize` on top of `make all`). Everything printed is a count, a grade or a rate; no child, parent or record is shown.
Counts under the club minimum cell size are printed as "<k". --interactive waits for Enter at each pause; --no-answer-key drops the lines that use the synthetic ground truth.
The talking points are Anna's to write (docs/demo_script.md); this prints the numbers each step stands on.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "warehouse" / "flag.duckdb"
INTERACTIVE = False
ANSWER_KEY = True


def q(con, sql, params=None):
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def table(rows: list[dict], cols: list[str] | None = None, hidden: tuple = ()) -> None:
    """A None in a count column named in `hidden` was suppressed (printed "<k"); a None anywhere else is just empty."""
    if not rows:
        print("  (none)")
        return
    cols = cols or list(rows[0])

    def fmt(v, c=None):
        if v is None:
            return "<k" if c in hidden else "-"
        if isinstance(v, float):
            return f"{v:,.3f}".rstrip("0").rstrip(".")
        return str(v)
    cells = [[fmt(r[c], c) for c in cols] for r in rows]
    widths = [max(len(c), *(len(row[i]) for row in cells)) for i, c in enumerate(cols)]
    print("  " + "  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for row in cells:
        print("  " + "  ".join(v.ljust(w) for v, w in zip(row, widths)))


def heading(n: int, title: str) -> None:
    print(f"\n{'=' * 100}\n{n}. {title}\n{'=' * 100}")


def pause(who: str, line: str) -> None:
    print(f"\n  >>> PAUSE for the {who}: \"{line}\"")
    if INTERACTIVE:
        try:
            input("      (press Enter to continue) ")
        except EOFError:
            pass


def key(text: str) -> None:
    if ANSWER_KEY:
        print(text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market")
    ap.add_argument("--interactive", action="store_true", help="wait for Enter at each pause, for presenting")
    ap.add_argument("--no-answer-key", action="store_true", help="omit the lines that use the synthetic answer key")
    args = ap.parse_args()
    global INTERACTIVE, ANSWER_KEY
    INTERACTIVE, ANSWER_KEY = args.interactive, not args.no_answer_key
    con = duckdb.connect(str(DB), read_only=True)
    year = q(con, "select max(participation_year) as y from share_club.share_club__market_year")[0]["y"]
    published = [r["club_market_id"] for r in q(con, "select club_market_id from share_club.share_club__market_year where participation_year = ? and regexp_matches(club_market_id, '^CM-') and suppressed = 'NONE' order by participants_allocated desc, club_market_id", [year])]
    m = args.market or published[0]
    if m not in published:
        sys.exit(f"Market {m} is not published in {year} (unknown, or below the small-cell size). Markets that work: {', '.join(published)}")
    mk = q(con, "select * from share_club.share_club__market_year where club_market_id = ? and participation_year = ?", [m, year])[0]
    print(f"PHASE 5 DEMO: {mk['market_name']} ({m}), {year}. All data synthetic; the market is a project approximation (ADR-016).")

    heading(1, "The mess: what the registration data looks like in this market")
    print("  The rules that fail most often here (pass rate across the market's records; 1 = clean). Each rule belongs to one or more purposes.")
    table(q(con, """select r.rule_id, r.dimension, r.purpose, round(r.observed_value, 3) as pass_rate, round(r.n_evaluated - r.n_pass, 1) as records_failing
                    from quality.dq_market_rule_results r where r.club_market_id = ? and r.season_year = ? and not r.pass and r.severity in ('ERROR', 'WARN')
                    order by r.observed_value, r.rule_id limit 8""", [m, year]))

    heading(2, "The scorecard: the same data, graded per purpose")
    table([{k: mk[k] for k in ("grade_count", "grade_segment", "grade_geo", "grade_retain", "grade_activate")}])
    lim = q(con, "select purpose, grade, limiting_dimension, array_to_string(top_failing_rules[1:2], ', ') as top_rules from quality.dq_scorecard_market where club_market_id = ? and season_year = ? and dimension = 'PURPOSE_SCORE' order by purpose", [m, year])
    table(lim)
    pause("clubs lead", "here is what you can trust: counts, segments and geography at these grades. Reaching families is a different grade.")

    heading(3, "The uncertainty decomposition: three separate bars, never added")
    print(f"  This market: {mk['participants_allocated']} participants allocated; the coverage band allows {mk['participants_allocated_interval_low']} to {mk['participants_allocated_interval_high']} "
          f"({mk['orgs_dark']:.0f} of {mk['orgs_known']:.0f} known organizations sent no file).")
    print("  Nationally:")
    table(q(con, "select component, reported_point as counted, interval_low, interval_high, contribution as width from quality.mart_uncertainty_decomposition where participation_year = ? order by component", [year]))
    if ANSWER_KEY:
        t = q(con, "select true_participants_in_data, identity_low, identity_high, identity_interval_contains_truth, true_participants_missing_from_data, coverage_low, coverage_high, coverage_interval_contains_truth from evaluation.eval_uncertainty_decomposition where participation_year = ?", [year])[0]
        key(f"  (answer key) true participants in the data {t['true_participants_in_data']} (identity interval {t['identity_low']:.0f} to {t['identity_high']:.0f}, contains: {t['identity_interval_contains_truth']}); "
            f"true participants missing {t['true_participants_missing_from_data']} (coverage interval {t['coverage_low']:.0f} to {t['coverage_high']:.0f}, contains: {t['coverage_interval_contains_truth']}). The coverage interval misses in some years: reported, not tuned.")

    heading(4, "Missingness bias: is the girls' share real?")
    g = q(con, "select youth_participants_in_cell as youth, unknown_gender_participants as unknown, girls_share_known_only, girls_share_bound_low, girls_share_bound_high, missingness_verdict from share_club.share_club__market_missingness where club_market_id = ? and participation_year = ?", [m, year])
    table(g)
    print("  Where gender is blank (all markets), and whether it looks random:")
    table(q(con, "select value_known_only, bound_low, bound_high, top_orgs, top_divisions, missingness_verdict, associated_factors from quality.mart_missingness_bias where kpi = 'girls_share_of_youth' and club_market_id = 'ALL' and segment_value = 'ALL' and participation_year = ?", [year]))

    heading(5, "The activation funnel: where families are lost, and why")
    table(q(con, "select step_no, step, unit, funnel_count, funnel_lost_dq as lost_to_data_quality, funnel_lost_privacy as lost_to_privacy from share_club.share_club__activation_funnel where club_market_id = ? and participation_year = ? order by step_no", [m, year]),
          hidden=("funnel_count", "lost_to_data_quality", "lost_to_privacy"))
    print("  A privacy loss is a family's answer (declined, revoked, or a form that never named the purpose), not a defect. A data-quality loss is a missing or unusable record.")
    pause("privacy lead", "here is what never leaves the league: the child's name, date of birth and the parent's contact. The funnel is counts only, by household.")

    heading(6, "The minimization frontier: what each field buys and what it costs")
    table(q(con, """select variant_id, pct_unique, pct_rows_below_k_min as pct_below_k_min, round(precision, 4) as precision, round(recall, 4) as recall, sibling_or_twin_false_merges as sibling_merges, fit_for_activate
                    from evaluation.eval_minimization_tradeoff where is_headline_matcher and precision is not null order by variant_id"""))
    print("  Chosen point for the data standard: pending (ADR-018).")

    heading(7, "The fix-list payoff (SIMULATED)")
    table(q(con, "select org_group, purpose, orgs_scored, round(score_before, 1) as before, round(score_after, 1) as after from demo_fix_list.scores order by org_group, purpose"))
    table(q(con, "select measure, round(value_before, 4) as before, round(value_after, 4) as after from demo_fix_list.nuance"))
    print("\nDone. Open questions for the stakeholders: docs/questions-for-stakeholders.md")


if __name__ == "__main__":
    main()
