"""Fail if ground truth leaks into the matcher.

Parses dbt/target/manifest.json. Every node outside dbt/models/evaluation/ (models, tests, seeds, snapshots)
must have no `ground_truth` source anywhere in its upstream lineage. A model that refs an evaluation model is
caught too, because evaluation models depend on the ground_truth source.

  uv run python -m scripts.check_eval_isolation [path/to/manifest.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "dbt" / "target" / "manifest.json"
GROUND_TRUTH_SOURCE = "ground_truth"
ALLOWED_DIR = "models/evaluation/"


def _is_ground_truth(node_id: str, manifest: dict) -> bool:
    node = manifest["sources"].get(node_id)
    return bool(node) and node["source_name"] == GROUND_TRUTH_SOURCE


def _upstream(node_id: str, manifest: dict, seen: set | None = None) -> set[str]:
    seen = set() if seen is None else seen
    nodes = {**manifest["nodes"], **manifest["sources"]}
    for parent in nodes.get(node_id, {}).get("depends_on", {}).get("nodes", []):
        if parent not in seen:
            seen.add(parent)
            _upstream(parent, manifest, seen)
    return seen


def find_leaks(manifest: dict) -> list[tuple[str, str]]:
    """-> [(offending node path, ground-truth source it depends on)]"""
    leaks = []
    for node_id, node in manifest["nodes"].items():
        path = node["original_file_path"].replace("\\", "/")
        if path.startswith(ALLOWED_DIR):
            continue
        for up in _upstream(node_id, manifest):
            if _is_ground_truth(up, manifest):
                leaks.append((path, up))
    return sorted(set(leaks))


def main(path: str | Path = MANIFEST) -> int:
    path = Path(path)
    if not path.exists():
        print(f"{path} not found: run `dbt parse` (or any dbt command) first", file=sys.stderr)
        return 2
    manifest = json.loads(path.read_text())
    leaks = find_leaks(manifest)
    if leaks:
        print("GROUND TRUTH LEAK: nodes outside models/evaluation/ depend on the ground_truth source:", file=sys.stderr)
        for node, src in leaks:
            print(f"  {node}  <-  {src}", file=sys.stderr)
        return 1
    n_eval = sum(1 for n in manifest["nodes"].values() if n["original_file_path"].startswith(ALLOWED_DIR))
    print(f"eval isolation OK: ground_truth is referenced only by models/evaluation/ ({n_eval} nodes there)")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
