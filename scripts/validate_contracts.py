"""Validate every source's RAW table against its data contract (contracts/*.yml).

  uv run python -m scripts.validate_contracts            (make contracts)

For each contract the script measures, against the raw table (strings in, strings stored):
  column_present        every required column / JSON path exists
  undeclared_column     a raw column or key the contract does not declare (it could be new PII)
  consent_values        each consent field holds only the values the contract allows
  max_null_rate         share of blank / missing values
  max_nonmatching_rate  share of non-blank values that do not match a regex
  max_invalid_rate      share of non-blank values outside an allowed list
  max_duplicate_rate    1 - distinct keys / rows
  max_expression_rate   share of rows where a SQL predicate over raw columns is TRUE (a cross-column check, e.g. total != girls + boys)
and writes quality.dq_contract_results (source_system, contract_version, rule, column_name, threshold, observed, status,
severity, detail, run_at).

Status is PASS, WARN or ERROR. A breach is a WARN by default and an ERROR when it concerns PII or consent structure:
a missing consent column, a consent value the contract does not allow, a missing required PII column, an undeclared raw
column, or any rule marked `severity: ERROR`. Violations are logged, never silently fixed. Any ERROR exits non-zero.

DuckDB-specific: regexp_matches, json_extract_string (the contracts validate raw DuckDB tables).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
DB = ROOT / "warehouse" / "flag.duckdb"
REQUIRED = ["source_system", "version", "effective_date", "owner_role", "partner_type", "delivery", "grain", "raw", "primary_key",
            "person_identifier", "minors_present", "consent_fields", "schema", "quality"]
PII = {"direct", "quasi", "none"}
RULES = {"max_null_rate", "max_nonmatching_rate", "max_invalid_rate", "max_duplicate_rate", "max_expression_rate"}
RESULT_COLUMNS = ["source_system", "component", "contract_version", "rule", "column_name", "threshold", "observed", "status", "severity", "detail"]


def q(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def load_contract(path: Path) -> dict:
    c = yaml.safe_load(path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in c]
    if missing:
        raise ValueError(f"{path.name}: missing contract fields {missing}")
    stem, _, component = path.stem.partition("__")      # SOURCE.yml, or SOURCE__component.yml for a source delivered as several tables
    if c["source_system"] != stem:
        raise ValueError(f"{path.name}: source_system {c['source_system']} does not match the file name")
    if component and c.get("component") != component:
        raise ValueError(f"{path.name}: a contract named SOURCE__component.yml must declare `component: {component}`")
    for col in c["schema"]:
        if col.get("pii") not in PII:
            raise ValueError(f"{path.name}: column {col.get('column')} needs pii: direct | quasi | none")
        if "column" not in col or "raw" not in col:
            raise ValueError(f"{path.name}: every schema entry needs `column` and `raw`")
    for rule in c["quality"]:
        if rule.get("rule") not in RULES:
            raise ValueError(f"{path.name}: unknown rule {rule.get('rule')}")
        if rule["rule"] == "max_expression_rate" and not {"name", "expression"} <= set(rule):
            raise ValueError(f"{path.name}: max_expression_rate needs `name` and `expression`")
    return c


def _expr(ref: str) -> str:
    """SQL expression reading a raw column or a JSON path from the raw table."""
    return f"json_extract_string(record_json, {q(ref)})" if ref.startswith("$.") else f'"{ref}"'


class Checker:
    def __init__(self, con: duckdb.DuckDBPyConnection, contract: dict):
        self.con, self.c = con, contract
        self.by_name = {col["column"]: col for col in contract["schema"]}
        self.by_raw = {col["raw"]: col for col in contract["schema"]}
        raw = contract["raw"]
        self.table = raw["table"]
        self.where = f"where {raw['row_filter']}" if raw.get("row_filter") else ""
        self.consent = {self._resolve(f["column"])["column"] for f in contract["consent_fields"]}
        self.is_json = any(col["raw"].startswith("$.") for col in contract["schema"])
        self.rows: list[dict] = []
        self.present: set[str] = set()

    def _resolve(self, name: str) -> dict:
        if name in self.by_name:
            return self.by_name[name]
        if name in self.by_raw:
            return self.by_raw[name]
        raise ValueError(f"{self.c['source_system']}: '{name}' is not a column in the contract schema")

    def _key_present(self, key: str) -> bool:
        raw = self.by_name[key]["raw"] if key in self.by_name else key
        return raw in self.present

    def _key_expr(self, key: str) -> str:
        if key in self.by_name:
            return _expr(self.by_name[key]["raw"])
        return _expr(key)

    def add(self, rule, column, threshold, observed, severity, detail=""):
        breach = observed > threshold if rule not in ("column_present",) else observed < threshold
        status = "PASS" if not breach else severity
        self.rows.append({"source_system": self.c["source_system"], "component": self.c.get("component", ""), "contract_version": str(self.c["version"]), "rule": rule,
                          "column_name": column, "threshold": float(threshold), "observed": float(observed),
                          "status": status, "severity": severity, "detail": detail})

    def scalar(self, sql: str):
        return self.con.execute(sql).fetchone()[0]

    # ---- structure ----
    def table_columns(self) -> set[str]:
        schema, name = self.table.split(".")
        return {r[0] for r in self.con.execute("select column_name from information_schema.columns where table_schema = ? and table_name = ?", [schema, name]).fetchall()}

    def json_paths(self) -> set[str]:
        paths: set[str] = set()
        for (raw,) in self.con.execute(f"select record_json::varchar from {self.table}").fetchall():
            def walk(obj, prefix, depth):
                for k, v in obj.items():
                    p = f"{prefix}.{k}" if prefix else f"$.{k}"
                    if isinstance(v, dict) and depth < 2:
                        paths.add(p)
                        walk(v, p, depth + 1)
                    else:
                        paths.add(p)
            walk(json.loads(raw), "", 1)
        return paths

    def check_structure(self):
        present = self.json_paths() if self.is_json else self.table_columns()
        self.present = present
        for col in self.c["schema"]:
            if col.get("required"):
                ok = col["raw"] in present
                severe = col["pii"] != "none" or col["column"] in self.consent
                self.add("column_present", col["column"], 1, 1.0 if ok else 0.0, "ERROR" if severe else "WARN",
                         "" if ok else "required column missing from the raw table")
        declared = {col["raw"] for col in self.c["schema"]}
        if self.is_json:
            declared |= {p.rsplit(".", 1)[0] for p in declared if p.count(".") >= 2}      # parent objects of declared paths
            extra = sorted(p for p in present if p not in declared)
        else:
            extra = sorted(c for c in present if not c.startswith("_") and c not in declared)
        for e in extra:
            self.add("undeclared_column", e, 0, 1.0, "ERROR", "raw column or key is not in the contract: its PII class is unknown")
        if not extra:
            self.add("undeclared_column", "*", 0, 0.0, "ERROR")

    # ---- consent ----
    def check_consent(self):
        for f in self.c["consent_fields"]:
            col = self._resolve(f["column"])
            if col["raw"] not in self.present:      # a missing consent column is already an ERROR in column_present
                continue
            e = _expr(col["raw"])
            allowed = ", ".join(q(v) for v in f["allowed_values"])
            bad = self.scalar(f"select count(*) filter (where nullif(trim({e}), '') is not null and trim({e}) not in ({allowed})) "
                              f"* 1.0 / nullif(count(*) filter (where nullif(trim({e}), '') is not null), 0) from {self.table} {self.where}") or 0.0
            self.add("consent_values", col["column"], 0, bad, "ERROR", f"allowed: {f['allowed_values']}; permits: {f['permits']}")

    # ---- quality thresholds ----
    def check_quality(self):
        for r in self.c["quality"]:
            sev = r.get("severity", "WARN")
            rule, thr = r["rule"], r["threshold"]
            if rule == "max_duplicate_rate":
                if any(not self._key_present(k) for k in r["key"]):
                    continue
                keys = ", ".join(self._key_expr(k) for k in r["key"])
                obs = self.scalar(f"select 1 - count(distinct concat_ws('|', {keys})) * 1.0 / nullif(count(*), 0) from {self.table} {self.where}") or 0.0
                self.add(rule, ", ".join(r["key"]), thr, obs, sev)
                continue
            if rule == "max_expression_rate":
                obs = self.scalar(f"select count(*) filter (where {r['expression']}) * 1.0 / nullif(count(*), 0) from {self.table} {self.where}") or 0.0
                self.add(rule, r["name"], thr, obs, sev, r["expression"])
                continue
            col = self._resolve(r["column"])
            if col["raw"] not in self.present:      # reported once, by column_present
                continue
            e = _expr(col["raw"])
            nonblank = f"nullif(trim({e}), '') is not null"
            if rule == "max_null_rate":
                obs = self.scalar(f"select count(*) filter (where not ({nonblank})) * 1.0 / nullif(count(*), 0) from {self.table} {self.where}")
            elif rule == "max_nonmatching_rate":
                obs = self.scalar(f"select count(*) filter (where {nonblank} and not regexp_matches(trim({e}), {q(r['pattern'])})) * 1.0 "
                                  f"/ nullif(count(*) filter (where {nonblank}), 0) from {self.table} {self.where}")
            else:   # max_invalid_rate
                allowed = ", ".join(q(v) for v in r["allowed_values"])
                obs = self.scalar(f"select count(*) filter (where {nonblank} and trim({e}) not in ({allowed})) * 1.0 "
                                  f"/ nullif(count(*) filter (where {nonblank}), 0) from {self.table} {self.where}")
            self.add(rule, col["column"], thr, obs or 0.0, sev)

    def run(self) -> list[dict]:
        self.check_structure()
        self.check_consent()
        self.check_quality()
        return self.rows


def evaluate(con: duckdb.DuckDBPyConnection, contract: dict) -> list[dict]:
    schema, name = contract["raw"]["table"].split(".")
    exists = con.execute("select count(*) from information_schema.tables where table_schema = ? and table_name = ?", [schema, name]).fetchone()[0]
    if not exists:
        return [{"source_system": contract["source_system"], "component": contract.get("component", ""), "contract_version": str(contract["version"]), "rule": "raw_table_present",
                 "column_name": contract["raw"]["table"], "threshold": 1.0, "observed": 0.0, "status": "ERROR", "severity": "ERROR",
                 "detail": "the raw table named in the contract does not exist"}]
    return Checker(con, contract).run()


def validate(contracts_dir: Path = CONTRACTS, db_path: Path = DB, write: bool = True) -> list[dict]:
    contracts = [load_contract(p) for p in sorted(contracts_dir.glob("*.yml")) if not p.name.startswith("_")]
    con = duckdb.connect(str(db_path), read_only=not write)
    try:
        results = [row for c in contracts for row in evaluate(con, c)]
        if write:
            run_at = dt.datetime.now().replace(microsecond=0)
            con.execute("create schema if not exists quality")
            con.execute("create or replace table quality.dq_contract_results (source_system varchar, component varchar, contract_version varchar, rule varchar, "
                        "column_name varchar, threshold double, observed double, status varchar, severity varchar, detail varchar, run_at timestamp)")
            for r in results:
                con.execute("insert into quality.dq_contract_results values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [*(r[k] for k in RESULT_COLUMNS), run_at])
    finally:
        con.close()
    return results


def main(argv: list[str]) -> int:
    results = validate()
    by_source: dict[str, dict] = {}
    for r in results:
        by_source.setdefault(r["source_system"], {"PASS": 0, "WARN": 0, "ERROR": 0})[r["status"]] += 1
    for s, n in sorted(by_source.items()):
        print(f"{s:12s} PASS {n['PASS']:3d}   WARN {n['WARN']:2d}   ERROR {n['ERROR']:2d}")
    for r in results:
        if r["status"] != "PASS":
            print(f"  {r['status']:5s} {r['source_system']}{'/' + r['component'] if r['component'] else ''} {r['rule']} [{r['column_name']}] observed {r['observed']:.4f} > threshold {r['threshold']:.4f}"
                  + (f"  ({r['detail']})" if r['detail'] else ""))
    errors = sum(1 for r in results if r["status"] == "ERROR")
    print(f"\ncontract validation: {len(by_source)} contracts, {errors} ERROR, {sum(1 for r in results if r['status'] == 'WARN')} WARN")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
