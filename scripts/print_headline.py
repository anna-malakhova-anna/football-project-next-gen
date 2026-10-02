"""Print the headline evaluation table and export the evaluation tables the docs and Phase 4 use.

  uv run python -m scripts.print_headline

Reads the evaluation models from warehouse/flag.duckdb, prints the headline table (all matchers, both review stages,
both scopes) and writes CSVs to docs/eval/ (threshold sweep for the Phase 4 chart, headline, segments).
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "warehouse" / "flag.duckdb"
OUT = ROOT / "docs" / "eval"

HEADLINE_SQL = """
select
    p.matcher                                                               as "Matcher",
    p.stage                                                                 as "Stage",
    p.scope                                                                 as "Scope",
    p.precision                                                             as "Precision",
    p.recall                                                                as "Recall",
    p.f1                                                                    as "F1",
    c.sibling_or_twin_false_merges                                          as "Sibling/twin merges",
    c.predicted_participants || ' vs ' || c.true_participants               as "Predicted vs true participants"
from evaluation.eval_pairwise p
join evaluation.eval_clusters c using (matcher, stage, scope)
order by p.matcher desc, p.stage, p.scope
"""


def _table(rows: list[tuple], header: list[str]) -> str:
    cells = [header] + [[("" if v is None else (f"{v:.5f}" if isinstance(v, float) else str(v))) for v in r] for r in rows]
    widths = [max(len(r[i]) for r in cells) for i in range(len(header))]
    line = lambda r: "| " + " | ".join(v.ljust(widths[i]) for i, v in enumerate(r)) + " |"  # noqa: E731
    return "\n".join([line(cells[0]), "|" + "|".join("-" * (w + 2) for w in widths) + "|"] + [line(r) for r in cells[1:]])


def main() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    cur = con.execute(HEADLINE_SQL)
    header = [d[0] for d in cur.description]
    rows = cur.fetchall()
    print(_table(rows, header))
    OUT.mkdir(parents=True, exist_ok=True)
    con.execute(f"copy ({HEADLINE_SQL}) to '{(OUT / 'headline.csv').as_posix()}' (header, delimiter ',')")
    con.execute(f"copy (select * from evaluation.eval_threshold_sweep order by matcher, threshold) to '{(OUT / 'threshold_sweep.csv').as_posix()}' (header, delimiter ',')")
    con.execute(f"copy (select * from evaluation.eval_segments order by matcher, stage, scope, segment_type, segment) to '{(OUT / 'segments.csv').as_posix()}' (header, delimiter ',')")
    print(f"\nwrote {', '.join(sorted(p.name for p in OUT.glob('*.csv')))} to docs/eval/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
