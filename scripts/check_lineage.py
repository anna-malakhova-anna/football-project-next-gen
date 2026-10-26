"""Fail if an aggregate-only source leaks into the participant counts, or the other way round.

Source E (school headcounts) is a count of children in programs, not people. Its models must never feed anything that counts or identifies
participants, and must never read from it. Only the explicitly listed REPORTING models may see both sides, and they report ranges.

Parses dbt/target/manifest.json (same approach as check_eval_isolation).

  uv run python -m scripts.check_lineage [path/to/manifest.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from scripts.common import ROOT

MANIFEST = ROOT / "dbt" / "target" / "manifest.json"

# models built from aggregate-only sources
AGGREGATE_ONLY = {"stg_school_headcounts", "fct_reported_headcount", "stg_gmp_proxy", "stg_gmp_minimum_return"}
# models that may depend on both: they combine as bounded ranges and are reviewed as such
REPORTING = {"mart_reported_headcount", "mart_kpi_scorecard", "mart_restatement_log", "eval_headcount_overlap"}
# directories whose models count or identify people
PARTICIPANT_DIRS = ("models/identity/", "models/marts/", "models/facts/", "models/staging/", "models/intermediate/")
PARTICIPANT_NAMES = {"mart_participation_global", "mart_participation_by_country", "mart_participation_segments", "mart_participation_by_org", "mart_identity_uncertainty"}


def _is_participant_side(name: str, path: str) -> bool:
    if name in AGGREGATE_ONLY or name in REPORTING:
        return False
    return name in PARTICIPANT_NAMES or path.startswith(PARTICIPANT_DIRS)


def _upstream(node_id: str, nodes: dict, seen: set | None = None) -> set[str]:
    seen = set() if seen is None else seen
    for parent in nodes.get(node_id, {}).get("depends_on", {}).get("nodes", []):
        if parent not in seen:
            seen.add(parent)
            _upstream(parent, nodes, seen)
    return seen


def find_violations(manifest: dict) -> list[str]:
    nodes = {**manifest["nodes"], **manifest["sources"]}
    models = {k: v for k, v in manifest["nodes"].items() if v["resource_type"] == "model"}
    by_name = {v["name"]: k for k, v in models.items()}
    problems = []
    for name in sorted(AGGREGATE_ONLY | REPORTING):
        if name not in by_name:
            problems.append(f"{name}: listed in check_lineage.py but not a model in the project")
    for node_id, node in models.items():
        name, path = node["name"], node["original_file_path"].replace("dbt/", "", 1)
        up = {nodes[u]["name"] for u in _upstream(node_id, nodes) if u in nodes}
        if _is_participant_side(name, path):
            leaked = up & AGGREGATE_ONLY
            if leaked:
                problems.append(f"{name} (participant side) depends on aggregate-only {sorted(leaked)}")
        if name in AGGREGATE_ONLY:
            leaked = {n for n in up if n in models_participant(models)}
            if leaked:
                problems.append(f"{name} (aggregate-only) depends on participant models {sorted(leaked)}")
    return problems


def models_participant(models: dict) -> set[str]:
    return {v["name"] for v in models.values() if _is_participant_side(v["name"], v["original_file_path"].replace("dbt/", "", 1))}


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else MANIFEST
    problems = find_violations(json.loads(path.read_text()))
    if problems:
        print("LINEAGE VIOLATION: aggregate-only and participant models are mixed")
        for p in problems:
            print("  -", p)
        return 1
    print("lineage: aggregate-only sources are separate from participant counts")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
