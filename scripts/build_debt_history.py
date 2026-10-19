"""Boundary debt history (Phase 6 addendum): ONE series, from the first count to now, in products/boundary_debt_history.csv.

  uv run python -m scripts.build_debt_history

Every commit that touched products/boundary_debt.csv gives one row (its number of data rows at that commit, read from git), oldest first; a last row `current` is the working file.
`change` is the difference from the row before. check_product_boundaries fails when the last row does not match the current file. Without a git history (a zip), the committed file is kept
and only the `current` row is refreshed.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEBT = ROOT / "products" / "boundary_debt.csv"
HISTORY = ROOT / "products" / "boundary_debt_history.csv"
FIELDS = ["step", "commit", "date", "debt_rows", "change", "what"]


def count(text: str) -> int:
    return len(list(csv.DictReader(text.splitlines())))


def from_git() -> list[dict]:
    try:
        log = subprocess.run(["git", "log", "--reverse", "--format=%h|%ad|%s", "--date=short", "--", "products/boundary_debt.csv"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    rows = []
    for line in log.splitlines():
        h, d, s = line.split("|", 2)
        text = subprocess.run(["git", "show", f"{h}:products/boundary_debt.csv"], cwd=ROOT, capture_output=True, text=True).stdout
        rows.append(dict(commit=h, date=d, debt_rows=count(text), what=s[:110]))
    return rows


def current_count() -> int:
    return count(DEBT.read_text(encoding="utf-8"))


def build() -> list[dict]:
    rows = from_git()
    if not rows and HISTORY.exists():
        rows = [r for r in csv.DictReader(HISTORY.open(encoding="utf-8")) if r["commit"] != "current"]
        for r in rows:
            r["debt_rows"] = int(r["debt_rows"])
    # a commit that did not change the count (a reason edit) is not a step
    series, prev = [], None
    for r in rows:
        if r["debt_rows"] != prev:
            series.append(r)
        prev = r["debt_rows"]
    now = current_count()
    if not series or series[-1]["debt_rows"] != now:
        series.append(dict(commit="current", date="", debt_rows=now, what="working file, not yet committed"))
    out, prev = [], None
    for i, r in enumerate(series):
        out.append(dict(step=i, commit=r["commit"], date=r["date"], debt_rows=r["debt_rows"], change="" if prev is None else r["debt_rows"] - prev, what=r["what"]))
        prev = r["debt_rows"]
    return out


def main() -> int:
    rows = build()
    with HISTORY.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("boundary debt: " + " -> ".join(str(r["debt_rows"]) for r in rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
