"""Usage logging for the data products (Phase 6, section 6.2): a STUB that shows how a consumer's use of a share would be recorded.

  uv run python -m scripts.log_usage --product DP4 --port club_market_view --role "Club youth and community manager" --event ACTIVATE
  uv run python -m scripts.log_usage --simulate        # refused unless approved (see below)

There are no real users, so nothing here is ever run by the build: phase6_ops.ops_product_usage_log stays empty and every adoption figure reads "instrumented, awaiting real users".
In a real deployment the delivery layer (a query gateway or the catalog) would call log_usage() on each query or download. The simulation flag exists only for a demonstration, and only
after the program owner approves it: it needs PRODUCT_USAGE_SIMULATION_APPROVED=1, and every row it writes carries is_simulated = true, which the site must badge ("Simulated usage, no real users").
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

import duckdb

from scripts.build_product_health import DB, USAGE_DDL

EVENTS = {"FIND", "ACTIVATE", "RETAIN", "REFER", "DECISION"}


def log_usage(con, product_id: str, port: str, role: str, event: str, note: str = "", simulated: bool = False) -> str:
    if event not in EVENTS:
        raise ValueError(f"event must be one of {sorted(EVENTS)}")
    con.execute("create schema if not exists phase6_ops")
    con.execute(USAGE_DDL)
    eid = str(uuid.uuid4())
    con.execute("insert into phase6_ops.ops_product_usage_log values (?, current_timestamp::timestamp, ?, ?, ?, ?, ?, ?)", [eid, product_id, port, role, event, simulated, note])
    return eid


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product"), ap.add_argument("--port"), ap.add_argument("--role"), ap.add_argument("--event")
    ap.add_argument("--simulate", action="store_true")
    a = ap.parse_args()
    if a.simulate:
        if os.environ.get("PRODUCT_USAGE_SIMULATION_APPROVED") != "1":
            print("refused: simulated usage needs the program owner's approval (set PRODUCT_USAGE_SIMULATION_APPROVED=1). Nothing was written.", file=sys.stderr)
            return 2
        print("simulation is approved but not implemented in the stub; nothing was written.", file=sys.stderr)
        return 2
    if not (a.product and a.port and a.role and a.event):
        ap.error("--product, --port, --role and --event are required")
    con = duckdb.connect(str(Path(DB)))
    try:
        print(log_usage(con, a.product, a.port, a.role, a.event))
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
