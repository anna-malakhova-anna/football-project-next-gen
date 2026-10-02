"""participant_id must be stable: rebuilding identity resolution on the same data gives the same ids.

Snapshots the current set of participant_ids and the registration -> participant mapping, re-runs the identity and
marts models from scratch, and compares. Exits non-zero on any difference.

  uv run python -m scripts.check_id_stability
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "warehouse" / "flag.duckdb"
SNAPSHOT = "select registration_key, participant_id from marts.bridge_registration_participant order by 1"


def snapshot() -> list[tuple]:
    con = duckdb.connect(str(DB), read_only=True)
    try:
        return con.execute(SNAPSHOT).fetchall()
    finally:
        con.close()


def main() -> int:
    before = snapshot()
    subprocess.run(["uv", "run", "dbt", "run", "--profiles-dir", ".", "--select", "identity", "marts", "--full-refresh"],
                   cwd=ROOT / "dbt", check=True, capture_output=True)
    after = snapshot()
    ids_before, ids_after = {p for _, p in before}, {p for _, p in after}
    if before != after:
        changed = sum(1 for a, b in zip(before, after) if a != b)
        print(f"participant_id NOT stable: {len(ids_before ^ ids_after)} ids differ, {changed} registrations remap", file=sys.stderr)
        return 1
    print(f"participant_id stable: {len(ids_after)} participants and {len(after)} registration mappings identical across a rebuild")
    return 0


if __name__ == "__main__":
    sys.exit(main())
