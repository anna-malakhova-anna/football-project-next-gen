"""Build the product health (inside) and adoption (outside) tables (Phase 6, section 6 of the handover).

  uv run python -m scripts.build_product_health

Reads, never invents: the product specs (products/*/product.yml), the scorecards, the contract results, the share suppression flags, the dbt run history stored by the on-run-end hook
(phase6_ops.ops_dbt_run_results) and the dbt manifest. Writes phase6.mart_product_health (the latest build, one row per product x measure), appends the same rows to
phase6_ops.ops_product_health_history (product x build run), and writes phase6.mart_product_adoption from phase6_ops.ops_product_usage_log (schema only: there are no real users, so every
count is zero and every status says so). Run it after `dbt test` so the pipeline measures describe the build that just finished.
Why a script and not a dbt model: the pipeline pass rate and the run time exist only in the run history, and a model cannot read the run it is part of.
"""
from __future__ import annotations

import csv
import json
import sys

import duckdb
import yaml

from scripts import check_product_boundaries as cb
from scripts import validate_products as vp
from scripts.common import ROOT

DB = vp.DB
GUARDRAIL_IDENTITY_PCT = "Y"      # product_targets.gate_id of the identity guardrail (read from the seed)

USAGE_DDL = """create table if not exists phase6_ops.ops_product_usage_log (
    event_id varchar, event_ts timestamp, product_id varchar, output_port varchar, consumer_role varchar,
    event_type varchar,          -- FIND | ACTIVATE | RETAIN | REFER | DECISION
    is_simulated boolean default false, note varchar)"""
STAGES = [("FIND", "Find", "Listed in the catalog; spec page views"), ("ACTIVATE", "Activate", "First successful query or download by a consumer role"),
          ("RETAIN", "Retain", "Consumer roles using it in two or more consecutive refresh cycles"), ("REFER", "Refer", "New consumer roles added through another consumer"),
          ("DECISION", "Financial impact", "Decisions or spend it informed (cost to run is under cost)")]


def lineage(manifest: dict, models: list[str]) -> tuple[set[str], set[str]]:
    """(upstream model/seed/source ids incl. the models themselves, ids of tests attached to any of them)."""
    by_name = {n["name"]: uid for uid, n in manifest["nodes"].items() if n["resource_type"] == "model"}
    seen: set[str] = set()
    stack = [by_name[m] for m in models if m in by_name]
    while stack:
        u = stack.pop()
        if u in seen:
            continue
        seen.add(u)
        stack += [p for p in manifest["parent_map"].get(u, []) if p in manifest["nodes"] or p in manifest.get("sources", {})]
    tests = {uid for uid, n in manifest["nodes"].items() if n["resource_type"] == "test" and set(n["depends_on"]["nodes"]) & seen}
    return seen, tests


def pipeline(con, manifest, models) -> tuple[dict, list[str]]:
    seen, tests = lineage(manifest, models)
    rows = con.execute("""select unique_id, resource_type, status, execution_time from (
                              select *, row_number() over (partition by unique_id order by run_at desc) as rn from phase6_ops.ops_dbt_run_results) where rn = 1""").fetchall()
    last = {r[0]: r for r in rows}
    res = [last[t][2] for t in tests if t in last]
    ran = sum(1 for s in res)
    ok = sum(1 for s in res if s in ("pass", "warn"))
    secs = sum(last[u][3] or 0 for u in seen if u in last and last[u][1] == "model")
    return {"tests_in_lineage": len(tests), "tests_recorded": ran, "tests_ok": ok, "failed": sum(1 for s in res if s in ("fail", "error")), "warn": sum(1 for s in res if s == "warn"),
            "model_seconds": round(secs, 1), "models_in_lineage": sum(1 for u in seen if u.startswith("model."))}, sorted(seen)


def contract_info(src: str) -> dict:
    out = {"cadence": None, "table": None}
    for f in sorted((ROOT / "contracts").glob(f"{src}*.yml")):
        y = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        if y.get("source_system") == src:
            out["cadence"] = out["cadence"] or (y.get("delivery") or {}).get("cadence")
            out["table"] = out["table"] or (y.get("raw") or {}).get("table")
    return out


def build(con) -> list[tuple]:
    products = vp.load()
    manifest = json.loads(vp.MANIFEST.read_text())
    inv = con.execute("select invocation_id from phase6_ops.ops_dbt_run_results order by run_at desc limit 1").fetchone()
    build_id = inv[0] if inv else "no-run-recorded"
    unverified = con.execute("select count(*) from reference.age_consent_rules where verified <> 'Y'").fetchone()[0]
    guard = con.execute("select threshold_value from reference.product_targets where gate_id = ?", [GUARDRAIL_IDENTITY_PCT]).fetchone()
    policy = con.execute("select coalesce(sum(violations), 0) from share_privacy.share_privacy__policy_checks").fetchone()[0]
    review = con.execute("select count(*) from share_ops.share_ops__review_queue").fetchone()[0]
    restate = con.execute("select count(*) from measurement.mart_restatement_log").fetchone()[0]
    link = con.execute("select household_link_rate from share_exec.share_exec__household_link_rate where country_code is null").fetchone()
    prov = con.execute("select count(*) filter (where has_known_full), count(*) from linkage.int_household_year_consent where participation_year = (select max(participation_year) from linkage.int_household_year_consent)").fetchone()
    owner = cb.analyse()[2]["owner"]
    debt = cb.read_debt()
    series = [int(r["debt_rows"]) for r in csv.DictReader((ROOT / "products" / "boundary_debt_history.csv").open(encoding="utf-8"))]
    trend = " to ".join(str(n) for n in series)
    out: list[tuple] = []
    for pid, p in products.items():
        def add(area, measure, text, num=None, status="INFO", note=""):
            out.append((pid, build_id, area, measure, str(text), None if num is None else float(num), status, note))
        # quality
        q = vp.resolve_quality(p["quality_indicator"], con)
        v = q["value"]
        if q["kind"] == "grade_distribution":
            add("quality", "Grade distribution across markets (GEO)", ", ".join(f"{g}: {n}" for g, n in v.items()), None, "WATCH" if v.get("C", 0) + v.get("D", 0) else "OK", q["detail"])
        elif q["kind"] == "identity_range_pct":
            breach = guard is not None and v > guard[0]
            add("quality", "Identity range, % of the count", f"{v}%", v, "ALERT" if breach else "OK", f"{q['detail']}; guardrail {guard[0] if guard else 'unset'}% (alert on breach)")
        else:
            add("quality", f"Purpose grade ({p['quality_indicator']['purpose']}, {q['kind'].replace('_', ' ')})", v, None, "OK" if v in "AB" else "WATCH", q["detail"])
        # freshness and contracts
        srcs = p.get("input_sources") or []
        ages, cadences, errs, warns = [], set(), 0, 0
        for s in srcs:
            ci = contract_info(s)
            if ci["cadence"]:
                cadences.add(ci["cadence"])
            if ci["table"]:
                try:
                    t = con.execute(f"select max(_loaded_at) from {ci['table']}").fetchone()[0]
                    if t is not None:
                        ages.append(con.execute("select date_diff('hour', ?::timestamp, current_timestamp::timestamp) / 24.0", [t]).fetchone()[0])
                except duckdb.Error:
                    pass
            r = con.execute("select count(*) filter (where severity = 'ERROR'), count(*) filter (where severity = 'WARN') from quality.dq_contract_results where source_system = ?", [s]).fetchone()
            errs, warns = errs + r[0], warns + r[1]
        if srcs:
            add("freshness", "Age of the oldest input load, in days", f"{max(ages):.1f}" if ages else "unknown", max(ages) if ages else None, "INFO",
                "Synthetic data is loaded once per build, so this is the build's age, not a late delivery. Expected cadence: " + ("; ".join(sorted(cadences)) if cadences else "not stated in the contract"))
            add("contract_status", "Contract results on the input sources", f"{errs} errors, {warns} warnings", errs, "INFO", "Errors are violations accepted in the onboarding logs (docs/playbook), not new breaks; listed, not hidden")
        # pipeline and cost
        models = [pt["model"] for pt in p["output_ports"]]
        try:
            pl, _ = pipeline(con, manifest, models)
            rate = (100.0 * pl["tests_ok"] / pl["tests_recorded"]) if pl["tests_recorded"] else None
            add("pipeline", "dbt tests on the product's lineage passing", f"{pl['tests_ok']} of {pl['tests_recorded']} ({pl['warn']} warnings)" if rate is not None else "no run recorded", rate,
                "ALERT" if pl["failed"] else ("OK" if rate is not None else "INFO"), f"{pl['tests_in_lineage']} tests attach to {pl['models_in_lineage']} models in the lineage; latest recorded result of each")
            add("cost", "Warehouse compute proxy: seconds to build the lineage's models", pl["model_seconds"], pl["model_seconds"], "INFO",
                "A proxy: the latest recorded run time of each model, summed. Not a cost in money.")
        except duckdb.Error:
            add("pipeline", "dbt tests on the product's lineage passing", "no run recorded", None, "INFO", "run `dbt test` first")
        # trust
        if pid in ("DP2", "DP3"):
            idr = vp.resolve_quality({"from_model": "mart_uncertainty_decomposition", "component": "IDENTITY", "aggregate": "identity_range_pct"}, con)
            add("trust", "Identity range, % of the count", f"{idr['value']}%", idr["value"], "OK" if not guard or idr["value"] <= guard[0] else "ALERT", idr["detail"])
        if pid == "DP2":
            add("trust", "Open identity review items", review, review, "INFO", "uncertain pairs and conflicts waiting for a steward")
        if pid in ("DP3", "DP4"):
            add("trust", "Published numbers restated in this cycle", restate, restate, "INFO" if restate == 0 else "WATCH", "from the restatement log; empty is the good case")
        if pid == "DP4":
            d = con.execute("select sum(orgs_dark), sum(orgs_known) from quality.mart_market_coverage where regexp_matches(club_market_id, '^CM-') and participation_year = (select max(participation_year) from quality.mart_market_coverage)").fetchone()
            add("trust", "Known leagues that sent no file", f"{int(d[0])} of {int(d[1])}", d[0], "WATCH" if d[0] else "OK", "their players are in no count; the range allows for them")
        if pid == "DP5":
            add("trust", "Participant households linked to a fan account", f"{100 * link[0]:.1f}%", 100 * link[0], "INFO", "linking is uneven by country (the bias); the metrics describe linked households only")
            add("trust", "Households with fully known consent provenance", f"{100.0 * prov[0] / prov[1]:.1f}%", 100.0 * prov[0] / prov[1], "INFO", "gate Z_ANALYTICS for DP5 v0 (80%)")
        # privacy
        add("privacy", "Share-policy check violations", int(policy), policy, "OK" if policy == 0 else "ALERT", "from share_privacy__policy_checks; zero is expected")
        supp_cells = supp_total = 0
        for pt in p["output_ports"]:
            try:
                r = con.execute(f"select count(*) filter (where suppressed <> 'NONE'), count(*) from {vp_schema(manifest, pt['model'])}.{pt['model']}").fetchone()
                supp_cells, supp_total = supp_cells + r[0], supp_total + r[1]
            except duckdb.Error:
                pass
        if supp_total:
            add("privacy", "Rows with a hidden count (suppression rate)", f"{100.0 * supp_cells / supp_total:.1f}% of {supp_total}", 100.0 * supp_cells / supp_total, "INFO", "ports that carry a suppressed flag; a hidden count is the rule working")
        mine = sum(1 for (reader, _) in debt if owner.get(reader) == pid)
        add("boundaries", "Reads of another product's internals", mine, mine, "WATCH" if mine else "OK",
            f"accepted boundary debt; the whole project went {trend} (products/boundary_debt_history.csv), now {len(debt)}")
        add("privacy", "Age-rule rows still unverified", int(unverified), unverified, "WATCH" if unverified else "OK", "docs/product/age-consent-rules.md lists them; the program owner verifies")
    return out


def vp_schema(manifest: dict, model: str) -> str:
    return next(n["schema"] for n in manifest["nodes"].values() if n["resource_type"] == "model" and n["name"] == model)


def adoption(con) -> list[tuple]:
    rows = []
    for pid in vp.load():
        for code, label, definition in STAGES:
            n = con.execute("select count(*) from phase6_ops.ops_product_usage_log where product_id = ? and event_type = ? and not coalesce(is_simulated, false)", [pid, code]).fetchone()[0]
            sim = con.execute("select count(*) from phase6_ops.ops_product_usage_log where product_id = ? and event_type = ? and coalesce(is_simulated, false)", [pid, code]).fetchone()[0]
            rows.append((pid, label, definition, n, sim, "AWAITING_REAL_USERS" if n == 0 else "OBSERVED", "Instrumented, awaiting real users" if n == 0 else ""))
    return rows


def main() -> int:
    con = duckdb.connect(str(DB))
    try:
        con.execute("create schema if not exists phase6_ops")
        con.execute("create schema if not exists phase6")
        con.execute(USAGE_DDL)
        con.execute("create table if not exists phase6_ops.ops_product_health_history (recorded_at timestamp, product_id varchar, build_id varchar, area varchar, measure varchar, value_text varchar, value_num double, status varchar, note varchar)")
        rows = build(con)
        con.execute("create or replace table phase6.mart_product_health (product_id varchar, build_id varchar, area varchar, measure varchar, value_text varchar, value_num double, status varchar, note varchar)")
        con.executemany("insert into phase6.mart_product_health values (?, ?, ?, ?, ?, ?, ?, ?)", rows)
        con.execute("delete from phase6_ops.ops_product_health_history where build_id = ?", [rows[0][1]])
        con.executemany("insert into phase6_ops.ops_product_health_history select current_timestamp::timestamp, ?, ?, ?, ?, ?, ?, ?, ?", rows)
        con.execute("create or replace table phase6.mart_product_adoption (product_id varchar, stage varchar, definition varchar, real_events bigint, simulated_events bigint, status varchar, note varchar)")
        con.executemany("insert into phase6.mart_product_adoption values (?, ?, ?, ?, ?, ?, ?)", adoption(con))
        n = len(rows)
        alerts = [r for r in rows if r[6] == "ALERT"]
    finally:
        con.close()
    print(f"product health: {n} measures for {len(vp.load())} products (build {rows[0][1][:8]}); {len(alerts)} alerts; adoption instrumented, awaiting real users")
    for a in alerts:
        print(f"  ALERT {a[0]} {a[3]}: {a[4]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
