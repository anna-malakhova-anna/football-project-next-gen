"""Print the Phase 5 scorecard summary: resolution before/after, grades and fitness by feed, the weakest rules, and a sample fix list.

  uv run python -m scripts.print_p5_scorecard

Reads warehouse/flag.duckdb (run `make p5-score` first). The resolution line is graded against the synthetic answer key (evaluation only); everything else is label-free.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "warehouse" / "flag.duckdb"


def show(con, title: str, sql: str) -> None:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    print(f"\n{title}")
    widths = [max(len(str(c)), *(len(str(r[i])) for r in rows)) if rows else len(str(c)) for i, c in enumerate(cols)]
    print("  " + "  ".join(str(c).ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  " + "  ".join(str(v).ljust(w) for v, w in zip(r, widths)))


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    show(con, "Resolution (graded against the synthetic answer key)", """
        select records, predicted_people, true_people, precision, recall, sibling_or_twin_false_merge_pairs as sibling_merges
        from evaluation.eval_p5_resolution""")
    show(con, "Duplicates before and after resolution (label-free)", """
        select count(*) as records,
               round(100.0 * count(*) filter (where is_exact_duplicate_row) / count(*), 1) as pct_exact_duplicate_rows,
               round(100.0 * count(*) filter (where not is_first_of_child_season) / count(*), 1) as pct_duplicates_after_resolution
        from phase5.p5_record_quality""")
    show(con, "Leagues by feed: grade and fitness", """
        select feed, count(*) as leagues, count(*) filter (where grade = 'A') as a, count(*) filter (where grade = 'B') as b,
               count(*) filter (where grade = 'C') as c, count(*) filter (where grade = 'D') as d,
               count(*) filter (where fit_for_participation_reporting) as fit_reporting, count(*) filter (where fit_for_club_activation) as fit_activation
        from phase5.dq_score_league group by 1 order by 1""")
    show(con, "Weakest rules overall (pass rate across all records evaluated)", """
        select rule_id, dimension, round(sum(n_pass) / sum(n_evaluated), 3) as pass_rate, sum(n_evaluated) as evaluated
        from phase5.dq_rule_results_league group by 1, 2 order by pass_rate limit 6""")
    show(con, "Markets: grades", "select grade, count(*) as markets, sum(n_records) as records from phase5.dq_score_market group by 1 order by 1")
    show(con, "Consent provenance funnel (counts only)", """
        select stage, stage_name, unit, n, share_of_previous from phase5.p5_consent_funnel order by stage""")
    show(con, "Why households drop out of club activation", """
        select activation_status, count(*) as households from phase5_restricted.p5_household_activation group by 1 order by 2 desc""")
    show(con, "Purpose limitation: households a careless reading would have admitted", "select * from phase5.p5_purpose_limitation")
    show(con, "Consent provenance by feed", "select source_feed, event_kind, events, share_what_known, share_when_known, share_which_known, share_fully_known from phase5.p5_consent_provenance_by_feed order by 1, 2")
    show(con, "Households and activation, graded against the answer key (evaluation only)", "select * from evaluation.eval_p5_households_and_consent")
    show(con, "Club-facing market view (aggregate only; small cells suppressed)", """
        select club_name, market_id, club_market_role as role, status, participation_estimate as estimate, estimate_low as low, estimate_high as high,
               round(100 * participation_rate, 2) as rate_pct, confidence, data_quality_grade as dq
        from phase5_club.p5_club_market_view order by status, club_name, market_id limit 12""")
    show(con, "Estimate vs naive count vs truth (evaluation only)", """
        select count(*) as markets, count(*) filter (where band_contains_truth) as band_contains_truth,
               round(100 * avg(estimate_error), 1) as mean_estimate_error_pct, round(100 * avg(naive_error), 1) as mean_naive_error_pct
        from evaluation.eval_p5_market_estimate""")
    try:
        show(con, "Retention job, latest run (counts only; run `make p5-retention`)", """
            select rule, table_name, rows_deleted_or_changed as rows, children_affected as children, households_affected as households, as_of
            from pii_store.retention_log where run_id = (select max(run_id) from pii_store.retention_log) order by rule, table_name""")
    except duckdb.CatalogException:
        print("\nRetention job: not run yet (make p5-retention)")
    show(con, "Fix list sample (the top organization-specific issue, ranked by impact, for the five largest channel-feed organizations)", """
        select f.org_name, f.rule_id, f.records_affected as records, f.impact_estimate as impact, f.fix_guidance as fix
        from quality.dq_fix_list f join quality.dq_org_season_base o using (source_system, org_id, season_year)
        where f.season_year = (select max(season_year) from quality.dq_fix_list) and not f.is_systemic and f.rank_in_scope = 1
          and f.source_system in ('matrix_export', 'vendor_reg_a', 'vendor_reg_b', 'pop_warner_feed', 'pal_chapter_csv', 'school_program')
        order by o.n_records desc limit 5""")


if __name__ == "__main__":
    main()
