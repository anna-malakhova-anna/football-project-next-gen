"""Phase 7 step 8: the Italy onboarding experiment, run on a COPY of the warehouse (ADR-030). SYNTHETIC.

  uv run python -m scripts.p7_italy_experiment        (make p7-italy-experiment)

Italy is dark in the published build. Here a synthetic first minimum return (generator/phase7/italy_return.py) lands in a copy of the warehouse, is
checked against the minimum-return template contract with the same validator as every contract, and the global-outlook models are rebuilt on the
copy. The report compares Italy before (the published warehouse, read only) and after (the copy): status, direction, scenario, board gate and
priority. It also sets the return's total against the planning scenario Italy had and, from the answer key, the truth. The published warehouse is
never written; the script checks that its file is unchanged. Writes docs/reports/p7_italy_experiment.md and docs/eval/p7_italy_experiment.csv.
"""
from __future__ import annotations

import csv
import datetime as dt
import shutil
import subprocess
import tempfile
from pathlib import Path

import duckdb

from generator.phase7 import italy_return
from generator.population import load_config
from loader.load_phase7 import land_minimum_returns
from scripts import validate_contracts
from scripts.common import DB, ROOT

REPORT = ROOT / "docs" / "reports" / "p7_italy_experiment.md"
CSV_OUT = ROOT / "docs" / "eval" / "p7_italy_experiment.csv"
TEMPLATE = ROOT / "contracts" / "templates" / "GMP_MINIMUM_RETURN.yml"
COUNTRY = "IT"
GATE = {"MIN_RETURN_SEASONS": "a first season of counts", "PROXY_RETURN": "clubs file an activity return", "COUNTING_GRADE_AT_LEAST": "a counting grade of C or better"}
STATE = {"MET": "met", "NOT_YET": "not yet met", "PENDING": "waiting for data"}


def snapshot(db: Path) -> dict:
    con = duckdb.connect(str(db), read_only=True)
    try:
        q = lambda sql: con.execute(sql, [COUNTRY]).fetchone()          # noqa: E731
        st = q("select status, status_reason, participation_source from phase7.mart_gmp_market_status where country_code = ?")
        di = q("select participation_direction, proxy_direction from phase7.mart_gmp_direction where country_code = ?")
        sc = q("select scenario_low, scenario_high, scenario_direction, comparable_markets from phase7.mart_gmp_scenario where country_code = ?")
        bo = q("select lane, gate_kind, gate_status from phase7.mart_gmp_board where country_code = ?")
        pr = q("select feasibility_today, data_readiness, priority_score, priority_rank from phase7.mart_gmp_priority where country_code = ?")
        counts = dict(con.execute("select status, count(*) from phase7.mart_gmp_market_status group by 1").fetchall())
        return {"status": st[0], "status_reason": st[1], "participation_source": st[2], "participation_direction": di[0], "proxy_direction": di[1],
                "scenario_low": sc[0] if sc else None, "scenario_high": sc[1] if sc else None, "scenario_direction": sc[2] if sc else None, "scenario_comparables": sc[3] if sc else None,
                "board_lane": bo[0], "board_gate": bo[1], "board_gate_status": bo[2], "feasibility_today": pr[0], "data_readiness": pr[1],
                "priority_score": pr[2], "priority_rank": pr[3], "markets_measured": counts.get("MEASURED", 0), "markets_partial": counts.get("PARTIAL", 0),
                "markets_proxy_only": counts.get("PROXY_ONLY", 0), "markets_dark": counts.get("DARK", 0)}
    finally:
        con.close()


def main() -> int:
    cfg = load_config()
    stamp = (DB.stat().st_size, DB.stat().st_mtime_ns)
    before = snapshot(DB)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        copy_db = tmp / "flag.duckdb"
        shutil.copyfile(DB, copy_db)
        season, rows = italy_return.build(cfg, COUNTRY)
        italy_return.write(rows, season, tmp / "raw", COUNTRY)
        con = duckdb.connect(str(copy_db))
        try:
            land_minimum_returns(con, tmp / "raw", dt.datetime.now().replace(microsecond=0))
            results = validate_contracts.evaluate(con, validate_contracts.load_contract(TEMPLATE))
            truth = con.execute("select true_participants from eval.gmp_market_truth where country_code = ? and season_year = ?", [COUNTRY, season]).fetchone()[0]
        finally:
            con.close()
        (tmp / "profiles.yml").write_text(f"counting_flag_football:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n      path: {copy_db}\n      threads: 4\n", encoding="utf-8")
        subprocess.run(["uv", "run", "dbt", "run", "--profiles-dir", str(tmp), "--target-path", str(tmp / "target"), "--select", "stg_gmp_minimum_return+"],
                       cwd=ROOT / "dbt", check=True, capture_output=True)
        after = snapshot(copy_db)
    if (DB.stat().st_size, DB.stat().st_mtime_ns) != stamp:
        raise RuntimeError("the published warehouse changed during the experiment")
    reported = sum(int(r["players"]) for r in rows)
    checks = [r for r in results if r["rule"] not in ("column_present", "raw_table_present")]
    failed = [r for r in checks if r["status"] != "PASS"]

    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["measure", "before_published", "after_on_copy"])
        for k in before:
            w.writerow([k, before[k], after[k]])
        w.writerow(["players_reported_in_return", "", reported])
        w.writerow(["true_participants_answer_key", truth, truth])
        w.writerow(["template_checks_passed", "", f"{len(checks) - len(failed)} of {len(checks)}"])

    low, high = before["scenario_low"], before["scenario_high"]
    names = {r[0]: r[1] for r in csv.reader(open(ROOT / "dbt" / "seeds" / "gmp_markets.csv", encoding="utf-8"))}
    comparables = [names.get(c, c) for c in (before["scenario_comparables"] or "").split("|") if c]
    comparables_text = ", ".join(comparables[:-1]) + " and " + comparables[-1] if len(comparables) > 1 else "".join(comparables)
    lines = [
        "# Italy onboarding experiment (Phase 7, step 8)", "",
        "> **Generated** by `scripts/p7_italy_experiment.py` (`make p7-italy-experiment`). SYNTHETIC. Run on a **copy** of the warehouse; the published",
        "> warehouse and the published tab keep Italy dark ([ADR-030](../decisions/ADR-030-minimum-return-path-and-walkthroughs.md)).", "",
        f"A synthetic first minimum return for Italy's {season} season ({len(rows)} rows: region x age band) landed in a copy of the warehouse. It was checked against the",
        "minimum-return template with the same validator as every contract, and the global-outlook models were rebuilt on the copy.", "",
        f"**Template checks:** {len(checks) - len(failed)} of {len(checks)} passed" + ("." if not failed else f"; failing: {', '.join(r['column_name'] or r['rule'] for r in failed)}."), "",
        "| | Before (published) | After (copy) |", "|---|---|---|",
        f"| Status | {before['status']} | {after['status']} |",
        f"| Why | {before['status_reason']} | {after['status_reason']} |",
        f"| Participation source | {before['participation_source'] or 'none'} | {after['participation_source'] or 'none'} |",
        f"| Participation direction | {before['participation_direction']} | {after['participation_direction']} |",
        f"| Planning scenario | {low} to {high} players, {before['scenario_direction']} | {'none (the market now has data)' if after['scenario_low'] is None else str(after['scenario_low']) + ' to ' + str(after['scenario_high'])} |",
        f"| Board | {before['board_lane'].title()}, {GATE.get(before['board_gate'], before['board_gate'])}: {STATE.get(before['board_gate_status'], before['board_gate_status'])} | "
        f"{after['board_lane'].title()}, {GATE.get(after['board_gate'], after['board_gate'])}: {STATE.get(after['board_gate_status'], after['board_gate_status'])} |",
        f"| Priority (feasibility, readiness, score, rank) | {before['feasibility_today']}, {before['data_readiness']}, {before['priority_score']}, {before['priority_rank']} | {after['feasibility_today']}, {after['data_readiness']}, {after['priority_score']}, {after['priority_rank']} |",
        f"| Markets measured / partial / proxy-only / dark | {before['markets_measured']} / {before['markets_partial']} / {before['markets_proxy_only']} / {before['markets_dark']} | {after['markets_measured']} / {after['markets_partial']} / {after['markets_proxy_only']} / {after['markets_dark']} |", "",
        "## What the first return says against the planning scenario", "",
        f"The return reports **{reported} players**. The planning scenario Italy had was **{low} to {high}** (from the per-club rates of {comparables_text}",
        f"times Italy's clubs with rights). The answer key's true count is **{truth}**: the return " + ("matches it" if reported == truth else f"differs from it by {reported - truth}") + ", and the scenario",
        f"{'contained it' if low is not None and low <= truth <= high else 'missed it'}" + (f" by a factor of about {truth / high:.0f}" if high and truth > high else "") + ".",
        "One season of counts is enough to leave the scenario behind. It is not enough for a counting grade or a direction: those need a second season and",
        "organization-level filings (ADR-025).", "",
        "## What the experiment does not show", "",
        "- A real federation's return would carry its own errors. This one is built to pass every check, so the walkthrough shows the path, not the friction.",
        f"- Italy's board milestone is {GATE.get(before['board_gate'], before['board_gate'])}: {STATE.get(before['board_gate_status'], before['board_gate_status'])} in the published build, "
        f"{STATE.get(after['board_gate_status'], after['board_gate_status'])} on the copy.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Italy: {before['status']} -> {after['status']}; return {reported} players; scenario {low} to {high}; truth {truth}; wrote {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
