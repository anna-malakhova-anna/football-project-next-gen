"""Phase 5 minimization frontier: run the Phase 2 identity chain once per variant and grade each run against the answer key (evaluation only).

  uv run python -m scripts.p5_minimization_runs [--variants V0_FULL V2_BIRTH_YEAR V4_HASHED_CONTACT]

For each row of the seed minimization_variants the dbt var `minimization_variant` coarsens the matcher's input (macros/minimization.sql); the identity models and their evaluations are rebuilt
(about half a minute each), and one row per matcher is written to eval.minimization_runs. The default build (V0_FULL) is restored at the end, also if a run fails, because the marts downstream of
identity must never be left on a coarsened input. Nothing is tuned to a variant. The reduced set for CI is `--variants V0_FULL V2_BIRTH_YEAR V4_HASHED_CONTACT`.
"""
from __future__ import annotations

import argparse
import json
import subprocess

import duckdb
from scripts.common import DB, ROOT

SELECT = ["path:models/identity", "eval_truth_pairs", "eval_record_truth", "eval_pairwise", "eval_clusters"]
MATCHERS = ("fs", "rules")
COLUMNS = ("variant_id varchar, matcher varchar, records integer, precision double, recall double, f1 double, sibling_or_twin_false_merges integer, twin_false_merges integer, "
           "true_participants integer, predicted_participants integer, participant_count_error integer, participant_count_error_pct double, split_rate_pct double, merge_rate_pct double")


def dbt(*args: str, variant: str | None = None) -> None:
    cmd = ["uv", "run", "dbt", *args, "--profiles-dir", "."]
    if variant:
        cmd += ["--vars", json.dumps({"minimization_variant": variant})]
    subprocess.run(cmd, cwd=ROOT / "dbt", check=True, capture_output=True)


def measure(variant: str) -> list[tuple]:
    con = duckdb.connect(str(DB), read_only=True)
    try:
        return con.execute(f"""
            select '{variant}', p.matcher, (select count(*) from identity.idr_input_records), p.precision, p.recall, p.f1,
                   c.sibling_or_twin_false_merges, c.twin_false_merges, c.true_participants, c.predicted_participants,
                   c.participant_count_error, c.participant_count_error_pct, c.split_rate_pct, c.merge_rate_pct
            from evaluation.eval_pairwise p
            join evaluation.eval_clusters c on c.matcher = p.matcher and c.stage = p.stage and c.scope = p.scope
            where p.stage = 'PRE_REVIEW' and p.scope = 'AUTO' and p.matcher in {MATCHERS}
            order by p.matcher""").fetchall()
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="*", help="default: every row of the seed")
    args = ap.parse_args()
    con = duckdb.connect(str(DB), read_only=True)
    try:
        all_variants = [r[0] for r in con.execute("select variant_id from reference.minimization_variants order by sort_order").fetchall()]
    finally:
        con.close()
    variants = args.variants or all_variants
    unknown = set(variants) - set(all_variants)
    if unknown:
        raise SystemExit(f"unknown variants: {sorted(unknown)}")
    # V0_FULL last: the default build is V0_FULL, so the run that ends on it leaves the warehouse restored and the extra rebuild is skipped (about 35 seconds saved)
    variants = [v for v in variants if v != "V0_FULL"] + [v for v in variants if v == "V0_FULL"]
    rows: list[tuple] = []
    default_in_place = False
    try:
        for v in variants:
            default_in_place = False
            dbt("run", "--select", *SELECT, variant=v)
            rows += measure(v)
            default_in_place = v == "V0_FULL"
            print(f"  {v}: done", flush=True)
    finally:
        if not default_in_place:                           # restore the default build, always (skipped only when the run that just finished was the default itself)
            dbt("run", "--select", *SELECT)
    con = duckdb.connect(str(DB))
    try:
        con.execute("create schema if not exists eval")
        con.execute(f"create or replace table eval.minimization_runs ({COLUMNS})")
        con.executemany("insert into eval.minimization_runs values (" + ",".join("?" * 14) + ")", rows)
    finally:
        con.close()
    print(f"wrote {len(rows)} rows to eval.minimization_runs")


if __name__ == "__main__":
    main()
