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
    show(con, "Fix list sample (top issue for the five largest leagues)", """
        select f.league_name, f.rule_id, f.fix from phase5.dq_fix_list f join phase5.dq_score_league s using (league_group)
        where f.fix_rank = 1 order by s.n_records desc limit 5""")


if __name__ == "__main__":
    main()
