"""Print the Phase 5 channel-feed summary: resolution against the answer key, duplicates, consent provenance, activation status and the retention job's latest run.

  uv run python -m scripts.print_p5_scorecard

Reads warehouse/flag.duckdb (run `make p5-score` first). The resolution line is graded against the synthetic answer key (evaluation only); everything else is label-free.
The scorecards, fix lists and market views of the spec are printed by `make dq` and `make markets`; the six channel feeds are scored there as sources.
"""
from __future__ import annotations


import duckdb
from scripts.common import DB



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
    show(con, "Channel feeds: purpose scores, latest season", """
        select source_system as feed, purpose, grade, score
        from quality.dq_scorecard_source
        where season_year = (select max(season_year) from quality.dq_scorecard_source) and dimension = 'PURPOSE_SCORE'
          and source_system in ('matrix_export', 'vendor_reg_a', 'vendor_reg_b', 'pop_warner_feed', 'pal_chapter_csv', 'school_program')
        order by 1, 2""")
    show(con, "Consent provenance funnel (counts only)", "select stage, stage_name, unit, n, share_of_previous from phase5.p5_consent_funnel order by stage")
    show(con, "Why households drop out of club activation", "select activation_status, count(*) as households from phase5_restricted.p5_household_activation group by 1 order by 2 desc")
    show(con, "Purpose limitation: households a careless reading would have admitted", "select * from phase5.p5_purpose_limitation")
    show(con, "Consent provenance by feed", "select source_feed, event_kind, events, share_what_known, share_when_known, share_which_known, share_fully_known from phase5.p5_consent_provenance_by_feed order by 1, 2")
    show(con, "Households and activation, graded against the answer key (evaluation only)", "select * from evaluation.eval_p5_households_and_consent")
    try:
        show(con, "Retention job, latest run (counts only; run `make p5-retention`)", """
            select rule, table_name, rows_deleted_or_changed as rows, children_affected as children, households_affected as households, as_of
            from pii_store.retention_log where run_id = (select max(run_id) from pii_store.retention_log) order by rule, table_name""")
    except duckdb.CatalogException:
        print("\nRetention job: not run yet (make p5-retention)")


if __name__ == "__main__":
    main()
