"""SIMULATED data steward. A stand-in for a human, for demonstrating the review feedback loop only.

*** This uses the GROUND TRUTH to decide, so it is NOT matcher performance. ***
Evaluation reports metrics before (stage PRE_REVIEW) and after (stage POST_REVIEW) steward decisions as separate
rows; never present post-review numbers as the matcher's own accuracy.

Resolves the top N items of identity.idr_review_queue:
  PROBABLE_PAIR     true same person -> MATCH, otherwise NO_MATCH
  CLUSTER_CONFLICT  a member pair of different true people -> NO_MATCH; a cluster that is really one person is
                    confirmed with MATCH for its member pairs
and writes the decisions to dbt/seeds/review_decisions.csv (the only file it writes; `make steward-reset` restores the
header-only seed).

  uv run python -m scripts.simulate_steward --n 20
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from itertools import combinations
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "warehouse" / "flag.duckdb"
OUT = ROOT / "dbt" / "seeds" / "review_decisions.csv"
HEADER = ["record_a", "record_b", "decision", "decided_by", "decided_at", "note"]
DECIDED_BY = "SIMULATED_STEWARD"
DECIDED_AT = "2026-01-01 00:00:00"


def decisions(db_path: Path, n: int) -> list[dict]:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        truth = dict(con.execute("""
            select i.match_record_id, t.true_person_id
            from identity.idr_input_records i
            join eval.registration_truth t on t.source_system = i.source_system and t.source_record_id = i.source_record_id
        """).fetchall())
        items = con.execute(
            "select item_type, record_a, record_b, members from identity.idr_review_queue order by priority limit ?", [n]
        ).fetchall()
    finally:
        con.close()
    out, seen = [], set()

    def add(a: str, b: str, decision: str, note: str) -> None:
        a, b = sorted((a, b))
        if (a, b) not in seen:
            seen.add((a, b))
            out.append({"record_a": a, "record_b": b, "decision": decision, "decided_by": DECIDED_BY,
                        "decided_at": DECIDED_AT, "note": note})

    for item_type, a, b, members in items:
        if item_type == "PROBABLE_PAIR":
            same = truth[a] == truth[b]
            add(a, b, "MATCH" if same else "NO_MATCH", "simulated steward (ground truth)")
        else:
            ids = [m["record"] for m in json.loads(members)]
            for x, y in combinations(ids, 2):
                add(x, y, "MATCH" if truth[x] == truth[y] else "NO_MATCH", "simulated steward (ground truth)")
    return out


def write(rows: list[dict], out_path: Path = OUT) -> None:
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--n", type=int, default=20, help="resolve the top N review-queue items")
    ap.add_argument("--reset", action="store_true", help="restore the header-only seed and exit")
    args = ap.parse_args(argv)
    if args.reset:
        write([])
        print(f"reset {OUT.relative_to(ROOT)} to header only")
        return 0
    rows = decisions(DB, args.n)
    write(rows)
    print(f"SIMULATED steward wrote {len(rows)} decisions ({sum(r['decision'] == 'MATCH' for r in rows)} MATCH, "
          f"{sum(r['decision'] == 'NO_MATCH' for r in rows)} NO_MATCH) to {OUT.relative_to(ROOT)}")
    print("These use the ground truth: report them as POST_REVIEW, never as matcher performance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
