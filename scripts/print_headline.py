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


def _md_table(rows: list[tuple], header: list[str]) -> str:
    fmt = lambda v: "" if v is None else (f"{v:.5f}" if isinstance(v, float) else str(v))  # noqa: E731
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
                     + ["| " + " | ".join(fmt(v) for v in r) + " |" for r in rows])


def write_phase2_results(con) -> Path:
    """docs/phase2_results.md: the Phase 2 numbers the Phase 3 methodology memo cites. Generated, never hand-edited."""
    q = lambda sql: con.execute(sql).fetchall()  # noqa: E731
    cur = con.execute(HEADLINE_SQL.replace("order by p.matcher desc, p.stage, p.scope", "where p.stage = 'PRE_REVIEW' order by p.matcher desc, p.scope"))
    head_cols, head_rows = [d[0] for d in cur.description], cur.fetchall()
    blocking = dict((n, v) for n, v in q("select name, value from evaluation.eval_blocking where section = 'overall'"))
    thr = q("select matcher_version, t_auto, t_review, prior_odds from reference.match_thresholds order by 1")
    errors = q("select matcher, error_type, likely_cause, count(*) from evaluation.eval_errors where stage = 'PRE_REVIEW' group by all order by 1, 2, 3")
    queue = q("select item_type, suggested_action, count(*) from identity.idr_review_queue group by all order by 1, 2")
    integrity = q("select count(*) from identity.idr_cluster_integrity")[0][0]
    decided = q("select count(*) from reference.review_decisions")[0][0]
    participants = q("select count(*), count(*) filter (where is_minor_current) from marts.dim_participant")[0]
    regs = q("select count(*) from marts.bridge_registration_participant")[0][0]
    text = f"""# Phase 2 results: identity resolution

> **Generated** by `scripts/print_headline.py` (run `make eval`); do not edit by hand. All data is synthetic.
> Cited by the Phase 3 methodology memo. Method and caveats: [ADR-003](decisions/ADR-003-identity-resolution.md) and
> [identity_resolution.md](identity_resolution.md).

## Headline: matcher quality before any steward review

Pairwise precision, recall and F1 are measured on **final clusters** against the generator's answer key. "AUTO" merges
only automatic matches; "AUTO_PLUS_PROBABLE" also merges every probable pair.

{_md_table(head_rows, head_cols)}

The committed `review_decisions` seed holds {decided} decisions, so POST_REVIEW rows equal PRE_REVIEW rows. A simulated
steward (`make steward-demo`) uses the answer key; its rows are never matcher performance.

## Scale

- {regs:,} registrations resolve to {participants[0]:,} participants ({participants[1]:,} are minors at the latest season).
- Blocking: {blocking['candidate_pairs']:,.0f} candidate pairs of {blocking['possible_pairs']:,.0f} possible
  (reduction ratio {blocking['reduction_ratio']:.5f}); pair completeness **{blocking['pair_completeness']:.3f}**
  ({blocking['true_pairs']:,.0f} true pairs, {blocking['true_pairs_deterministic']:,.0f} linked by a source id,
  {blocking['true_pairs_missed_by_blocking']:,.0f} missed by blocking).

## Thresholds in use

{_md_table(thr, ['matcher_version', 't_auto', 't_review', 'prior_odds'])}

## Errors at the AUTO scope (before review)

{_md_table(errors, ['matcher', 'error_type', 'likely_cause', 'pairs'])}

`fs_naive` false positives are capped at the first 200 pairs per kind.

## Review queue and cluster integrity

{_md_table(queue, ['item_type', 'suggested_action', 'items'])}

{integrity} clusters carry an open integrity issue (`idr_cluster_integrity`).

## What this means for counting

- The final matcher (`fs`) counts participants almost exactly (see the Predicted vs true column), but that is partly two
  wrong merges and two wrong splits cancelling out; Phase 3 reports an identity range instead of a single number.
- At AUTO + PROBABLE the matcher merges some siblings (see Sibling/twin merges); the point estimate uses AUTO only.
- This is a synthetic population: phone numbers never change, one nickname list covers every generated nickname, and
  blocking completeness of 1.000 is a property of this data.
"""
    path = ROOT / "docs" / "phase2_results.md"
    path.write_text(text, encoding="utf-8")
    return path


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
    print(f"wrote {write_phase2_results(con).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
