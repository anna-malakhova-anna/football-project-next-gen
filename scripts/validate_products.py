"""Validate the data product specs (Phase 6, section 5 and 8 of the handover) and resolve their live quality indicators.

  uv run python -m scripts.validate_products

Checks: every required field; semver; allowed type, status and value proposition; goals G1 to G3 (every goal has a driver product, every product serves a goal); input products exist and the graph has no cycle;
every output port is a model in the dbt manifest, in the share schema of its audience (the ops audience for DP2); every claimed metric is in metric_catalog.csv; every prohibited use names enforcing tests
or checks that exist; the terms, decommission plan and lineage files exist; the quality indicator resolves against the scorecards. Nothing is typed by hand: the grade shown on the site comes from here.
Exit code 1 and one line per problem.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ROOT / "products"
MANIFEST = ROOT / "dbt" / "target" / "manifest.json"
DB = ROOT / "warehouse" / "flag.duckdb"
CATALOG = ROOT / "dbt" / "seeds" / "metric_catalog.csv"
GOALS = {"G1", "G2", "G3"}
REQUIRED = ["id", "name", "version", "type", "status", "description", "goals", "value_proposition", "consumers", "owner_role", "steward_role", "support_contact", "output_ports", "input_products",
            "sources_lineage", "quality_indicator", "metrics", "classification", "privacy", "terms_of_use", "geographic_coverage", "tags", "recommended_products", "feedback", "shelf_life",
            "decommission_plan", "pricing", "health_metrics"]
TYPES = {"source-based", "master", "insights"}
STATUS = {"proposed", "mvp", "active", "deprecated", "retired"}
VALUE = {"utility", "enabler", "driver"}
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
GRADE_ORDER = "ABCD"


def load() -> dict[str, dict]:
    out = {}
    for f in sorted(PRODUCTS.glob("DP*/product.yml")):
        out[f.parent.name] = yaml.safe_load(f.read_text(encoding="utf-8"))
    return out


def _tests_available() -> tuple[set[str], set[str], set[str]]:
    dbt = {p.stem for p in (ROOT / "dbt" / "tests").glob("*.sql")}
    if MANIFEST.exists():
        m = json.loads(MANIFEST.read_text())
        dbt |= {n["name"] for n in m["nodes"].values() if n["resource_type"] == "test"} | set(m.get("unit_tests", {}) and {u["name"] for u in m["unit_tests"].values()})
    py = {m for p in (ROOT / "tests").glob("test_*.py") for m in re.findall(r"^def (test_\w+)", p.read_text(encoding="utf-8"), flags=re.M)}
    scripts = {p.stem for p in (ROOT / "scripts").glob("*.py")}
    return dbt, py, scripts


def resolve_quality(spec: dict, con) -> dict:
    """The live indicator of a product, from the scorecards (latest season). Returns {'kind', 'value', 'detail'}."""
    model, agg = spec["from_model"], spec["aggregate"]
    if agg == "identity_range_pct":
        r = con.execute("select reported_point, interval_low, interval_high from quality.mart_uncertainty_decomposition where component = ? and participation_year = (select max(participation_year) from quality.mart_uncertainty_decomposition)", [spec["component"]]).fetchone()
        return {"kind": "identity_range_pct", "value": round(100.0 * (r[2] - r[1]) / r[0], 2), "detail": f"{r[1]:,.0f} to {r[2]:,.0f} around {r[0]:,.0f}"}
    flt = spec.get("filter", {})
    where, args = ["purpose = ?", "dimension = 'PURPOSE_SCORE'", f"season_year = (select max(season_year) from quality.{model})"], [spec["purpose"]]
    for col, val in flt.items():
        vals = val if isinstance(val, list) else [val]
        where.append(f"{col} in ({', '.join('?' for _ in vals)})")
        args += vals
    rows = con.execute(f"select grade, score from quality.{model} where {' and '.join(where)} and score is not null", args).fetchall()
    if not rows:
        raise LookupError(f"{model}: no rows for {spec}")
    if agg == "grade":
        return {"kind": "grade", "value": rows[0][0], "detail": f"score {Decimal(str(rows[0][1])).quantize(Decimal('0.1'), ROUND_HALF_UP)}"}
    if agg == "worst_grade":
        worst = max(rows, key=lambda r: GRADE_ORDER.index(r[0]))
        return {"kind": "worst_grade", "value": worst[0], "detail": f"worst of {len(rows)} sources"}
    if agg == "grade_distribution":
        dist = {g: sum(1 for r in rows if r[0] == g) for g in GRADE_ORDER}
        return {"kind": "grade_distribution", "value": dist, "detail": f"{len(rows)} markets graded"}
    raise ValueError(f"unknown aggregate {agg}")


def validate(products: dict[str, dict], con=None) -> list[str]:
    bad: list[str] = []
    if not products:
        return ["no products/DP*/product.yml found"]
    catalog = {r["metric_id"] for r in csv.DictReader(open(CATALOG, newline="", encoding="utf-8"))}
    dbt_tests, py_tests, scripts = _tests_available()
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else None
    models = {n["name"]: n for n in manifest["nodes"].values() if n["resource_type"] == "model"} if manifest else {}
    for pid, p in products.items():
        w = lambda msg: bad.append(f"{pid}: {msg}")  # noqa: E731
        for f in REQUIRED:
            if f not in p or p[f] in (None, ""):
                if not (f in ("input_products", "metrics", "recommended_products") and p.get(f) == []):
                    w(f"missing field {f}")
        if p.get("id") != pid:
            w(f"id {p.get('id')} does not match its folder")
        if not SEMVER.match(str(p.get("version", ""))):
            w(f"version {p.get('version')!r} is not semver")
        if p.get("type") not in TYPES: w(f"type {p.get('type')!r}")
        if p.get("status") not in STATUS: w(f"status {p.get('status')!r}")
        if p.get("value_proposition") not in VALUE: w(f"value_proposition {p.get('value_proposition')!r}")
        if not p.get("goals") or not set(p["goals"]) <= GOALS: w(f"goals {p.get('goals')}")
        for src in p.get("input_sources") or []:
            if not list((ROOT / "contracts").glob(f"{src}*.yml")): w(f"input source {src} has no contract")
        for i in p.get("input_products") or []:
            if i not in products: w(f"input product {i} does not exist")
        for fld in ("terms_of_use", "decommission_plan"):
            if p.get(fld) and not (ROOT / p[fld]).exists(): w(f"{fld} file {p[fld]} does not exist")
        if p.get("privacy", {}).get("age_rules") and not (ROOT / p["privacy"]["age_rules"]).exists(): w("privacy.age_rules file missing")
        for m, path in (p.get("sources_lineage") or {}).items():
            if not (ROOT / path).exists(): w(f"lineage file for {m} missing: {path}")
        if not (p.get("output_ports") or []) and not (p.get("aggregate_ports") or []): w("no output ports and no aggregate ports")
        for port in p.get("output_ports") or []:
            node = models.get(port["model"])
            if manifest and node is None:
                w(f"output port {port['name']}: model {port['model']} is not in the dbt manifest")
            elif node is not None:
                if not node["schema"].startswith("share_"): w(f"output port {port['name']}: {port['model']} is in schema {node['schema']}, not a share schema")
                if node["schema"] != f"share_{port['audience']}": w(f"output port {port['name']}: audience {port['audience']} does not match schema {node['schema']}")
                if port["model"] not in (p.get("sources_lineage") or {}): w(f"output port {port['name']}: no lineage entry")
        for mtr in p.get("metrics") or []:
            if mtr not in catalog: w(f"metric {mtr} is not in metric_catalog.csv")
        for pu in (p.get("privacy") or {}).get("prohibited_uses") or []:
            if not pu.get("enforced_by"): w(f"prohibited use {pu.get('use')!r} names no enforcing test")
            for e in pu.get("enforced_by") or []:
                pool = {"dbt_test": dbt_tests, "pytest": py_tests, "script": scripts}.get(e["kind"])
                if pool is None or e["name"] not in pool: w(f"prohibited use {pu['use']!r}: {e['kind']} {e['name']} does not exist")
        if con is not None:
            try:
                resolve_quality(p["quality_indicator"], con)
            except Exception as ex:  # noqa: BLE001
                w(f"quality_indicator does not resolve: {ex}")
    # goals and the dependency graph
    for g in sorted(GOALS):
        if not any(g in p.get("goals", []) and p.get("value_proposition") == "driver" for p in products.values()): bad.append(f"goal {g} has no driver product")
    for pid, p in products.items():
        if not p.get("goals"): bad.append(f"{pid}: serves no goal")
    seen: set[str] = set()

    def visit(n: str, stack: tuple) -> None:
        if n in stack: bad.append("dependency cycle: " + " > ".join(stack + (n,))); return
        if n in seen: return
        for i in products.get(n, {}).get("input_products") or []: visit(i, stack + (n,))
        seen.add(n)
    for pid in products: visit(pid, ())
    return bad


def main() -> int:
    products = load()
    con = duckdb.connect(str(DB), read_only=True) if DB.exists() else None
    try:
        bad = validate(products, con)
        if not bad and con is not None:
            for pid, p in products.items():
                q = resolve_quality(p["quality_indicator"], con)
                print(f"  {pid} {p['name']} v{p['version']} ({p['status']}): quality {q['value']} ({q['detail']})")
    finally:
        if con is not None:
            con.close()
    if bad:
        print(f"PRODUCT VALIDATION FAILED ({len(bad)}):")
        for b in bad: print("  " + b)
        return 1
    print(f"products OK: {len(products)} specs, every output port is a share model, every metric is in the catalog, every prohibited use has an enforcer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
