"""Phase 5 minimization experiment: what does identity resolution lose when the feeds carry only what the data standard asks for?

  uv run python -m scripts.p5_minimization

Runs the Phase 5 resolution twice: with the full DOB and ZIP5 (as received), and with birth year and ZIP3 only (var p5_standard_shape = true).
Both runs are graded against the synthetic answer key (evaluation only). The default build is restored at the end. Writes docs/eval/p5_minimization.csv.
The point is a measured price for minimization, so the standard can ask for less and say what that costs. Nothing is tuned to the answer key.
"""
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "warehouse" / "flag.duckdb"
SELECT = ["p5_idr_input_records+", "eval_p5_resolution"]


def build(standard_shape: bool) -> None:
    cmd = ["uv", "run", "dbt", "run", "--profiles-dir", ".", "--select", *SELECT, "--vars", json.dumps({"p5_standard_shape": standard_shape})]
    subprocess.run(cmd, cwd=ROOT / "dbt", check=True, capture_output=True)


def measure(label: str) -> dict:
    con = duckdb.connect(str(DB), read_only=True)
    try:
        r = con.execute("""select records, predicted_people, true_people, precision, recall, sibling_or_twin_false_merge_pairs
                           from evaluation.eval_p5_resolution""").fetchone()
        auto = con.execute("select count(*) from phase5.p5_pair_scores where tier = 'AUTO_MATCH'").fetchone()[0]
    finally:
        con.close()
    return {"shape": label, "records": r[0], "predicted_people": r[1], "true_people": r[2], "precision": r[3], "recall": r[4],
            "sibling_or_twin_false_merge_pairs": r[5], "automatic_links": auto}


def main() -> None:
    rows = []
    for label, shape in (("full DOB and ZIP5 (as received)", False), ("birth year and ZIP3 only (the standard)", True)):
        build(shape)
        rows.append(measure(label))
    build(False)                                   # restore the default build
    out = ROOT / "docs" / "eval" / "p5_minimization.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
