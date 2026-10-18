"""Product boundary check (Phase 6 addendum, section 1).

  uv run python -m scripts.check_product_boundaries [--list]

A data product is a governed output port on top of internal models, not a layer. Every dbt model has exactly one owner: a product (products/DP*/product.yml, `internal_models`
plus the share models of its audiences) or `shared_reference` (products/shared_reference.yml). A model may read a model of ANOTHER product only through that product's declared port:
  - output_ports and every share_* model it owns (consumers: anyone the audience policy admits),
  - aggregate_ports (organization-level aggregates, no person data; any product may read),
  - restricted_ports (row-level, readable only by the products named in `consumers`).
Also: no consumer-facing port reads `raw` directly, and nothing reads the answer-key models (evaluation).
Known violations of the first rule are recorded as accepted debt in products/boundary_debt.csv (reader, read, reason). A NEW violation fails; a debt row that no longer violates fails too
(so the list only shrinks). Exit code 1 and one line per problem.
"""
from __future__ import annotations

import csv
import fnmatch
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "dbt" / "target" / "manifest.json"
PRODUCTS = ROOT / "products"
DEBT = PRODUCTS / "boundary_debt.csv"
SHARED = "shared_reference"


def load_specs() -> dict[str, dict]:
    return {f.parent.name: yaml.safe_load(f.read_text(encoding="utf-8")) for f in sorted(PRODUCTS.glob("DP*/product.yml"))}


def analyse() -> tuple[list[str], list[tuple[str, str]], dict]:
    specs = load_specs()
    shared = yaml.safe_load((PRODUCTS / "shared_reference.yml").read_text(encoding="utf-8"))
    m = json.loads(MANIFEST.read_text())
    models = {k: v for k, v in m["nodes"].items() if v["resource_type"] == "model"}
    name = {k: v["name"] for k, v in models.items()}
    by_name = {v["name"]: k for k, v in models.items()}
    problems: list[str] = []

    # --- ownership: exactly one
    owners: dict[str, list[str]] = {n: [] for n in by_name}
    patterns = {pid: s.get("internal_models", []) for pid, s in specs.items()}
    patterns[SHARED] = shared["models"]
    for owner, pats in patterns.items():
        for pat in pats:
            hit = [n for n in by_name if fnmatch.fnmatch(n, pat)]
            if not hit:
                problems.append(f"{owner}: pattern '{pat}' matches no model")
            for n in hit:
                owners[n].append(owner)
    for n, o in owners.items():
        path = models[by_name[n]]["original_file_path"]
        if path.startswith("models/shares/"):
            continue  # share models are owned through the claim below
        if len(o) != 1:
            problems.append(f"{n}: owned by {len(o)} products ({', '.join(o) or 'none'}); exactly one is required")
    # share models: a product's output_ports name them explicitly via share_claims
    for pid, s in specs.items():
        for pat in s.get("share_models", []):
            for n in by_name:
                if fnmatch.fnmatch(n, pat) and models[by_name[n]]["original_file_path"].startswith("models/shares/"):
                    owners[n].append(pid)
    for n, o in owners.items():
        if models[by_name[n]]["original_file_path"].startswith("models/shares/") and len(o) != 1:
            problems.append(f"{n}: share model owned by {len(o)} owners ({', '.join(o) or 'none'}); exactly one is required")
    owner = {n: (o[0] if len(o) == 1 else None) for n, o in owners.items()}

    # --- ports
    out_ports = {pid: {p["model"] for p in s["output_ports"]} for pid, s in specs.items()}
    agg = {pid: set(s.get("aggregate_ports", [])) for pid, s in specs.items()}
    restricted = {pid: {r["model"]: set(r["consumers"]) for r in s.get("restricted_ports", [])} for pid, s in specs.items()}
    for pid in specs:
        for n in out_ports[pid] | agg[pid] | set(restricted[pid]):
            if n not in by_name:
                problems.append(f"{pid}: port '{n}' is not a model")
            elif owner.get(n) != pid:
                problems.append(f"{pid}: port '{n}' is owned by {owner.get(n)}, not {pid}")

    def readable(reader: str, read: str) -> bool:
        a, b = owner[reader], owner[read]
        if b == SHARED or a == b:
            return True
        if b not in specs:
            return False
        if read in agg[b] or read in out_ports[b]:
            return True
        if models[by_name[read]]["original_file_path"].startswith("models/shares/"):
            return True  # share_* schemas are the ports; audience rules are check_share_policy's job
        return a in restricted[b].get(read, set())

    violations: list[tuple[str, str]] = []
    for k, v in models.items():
        r = v["name"]
        for d in v["depends_on"]["nodes"]:
            if d in models:
                if models[d]["original_file_path"].startswith("models/evaluation/") and not v["original_file_path"].startswith("models/evaluation/"):
                    problems.append(f"{r} reads answer-key model {models[d]['name']}")
                elif v["original_file_path"].startswith("models/evaluation/"):
                    continue  # the answer-key harness reads every product by design; isolation is check_eval_isolation's job
                elif owner[r] and owner[models[d]["name"]] and not readable(r, models[d]["name"]):
                    violations.append((r, models[d]["name"]))
            elif d.startswith("source.") and d.split(".")[-2] in ("raw", "raw_p5") and (v["original_file_path"].startswith("models/shares/") or r in {p for s in out_ports.values() for p in s}):
                problems.append(f"{r}: a consumer-facing port reads {d.split('.')[-2]} directly")
    info = dict(owner=owner, n_models=len(models), specs=specs)
    return problems, sorted(set(violations)), info


def read_debt() -> dict[tuple[str, str], str]:
    if not DEBT.exists():
        return {}
    with DEBT.open(encoding="utf-8") as f:
        return {(r["reader"], r["read"]): r["reason"] for r in csv.DictReader(f)}


def main() -> int:
    problems, violations, info = analyse()
    debt = read_debt()
    if "--list" in sys.argv:
        for r, d in violations:
            print(f"{info['owner'][r]},{r},{info['owner'][d]},{d}")
        return 0
    found = set(violations)
    for r, d in sorted(found - set(debt)):
        problems.append(f"NEW boundary violation: {r} ({info['owner'][r]}) reads {d} ({info['owner'][d]}), which is not a declared port")
    for r, d in sorted(set(debt) - found):
        problems.append(f"stale debt row: {r} -> {d} no longer violates; remove it from products/boundary_debt.csv")
    for p in problems:
        print(p)
    if problems:
        return 1
    print(f"product boundaries OK: {info['n_models']} models each owned once; {len(found)} accepted debt rows (products/boundary_debt.csv) are the only cross-product reads of non-ports")
    return 0


if __name__ == "__main__":
    sys.exit(main())
