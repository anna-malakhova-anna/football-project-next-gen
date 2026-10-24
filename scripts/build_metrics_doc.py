"""Generate docs/metrics.md from dbt/seeds/metric_catalog.csv, so the metrics documentation cannot drift from the catalog
that the tests enforce.  (make docs)
"""
from __future__ import annotations

import csv
from pathlib import Path
from scripts.common import ROOT

CATALOG = ROOT / "dbt" / "seeds" / "metric_catalog.csv"
OUT = ROOT / "docs" / "metrics.md"
GROUPS = [("north_star", "North star"), ("growth", "Growth"), ("reach", "Reach"), ("depth", "Depth"),
          ("data_trust", "Data trust (reported beside the headline numbers, never hidden)"), ("supporting", "Supporting metrics")]
ADDITIVITY = {
    "ADDITIVE": "can be summed across any dimension of its grain",
    "ADDITIVE_BY_ATTRIBUTION": "sums across countries only in the attributed view (a person assigned to one country); never in the presence view",
    "NON_ADDITIVE": "distinct counts that overlap across a dimension; never sum them",
    "RATIO": "never summed or averaged; recompute from numerator and denominator",
    "STATE": "a point-in-time value, not a flow",
}


def _cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def render(path: Path = CATALOG) -> str:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = [
        "# Metric catalog",
        "",
        "> **Generated** from `dbt/seeds/metric_catalog.csv` by `scripts/build_metrics_doc.py` (`make docs`). Edit the CSV, not this",
        "> file. Every KPI in `mart_kpi_scorecard` and every metric column in `share_exec` must be in the catalog; a test enforces it.",
        "> All data is synthetic. A count is **registered participants in onboarded sources**, not total flag football participation.",
        "",
        f"Methodology version: **{rows[0]['methodology_version']}** at the time of the first metric; *Since* is the methodology version that introduced each KPI, and a KPI appears in the scorecard only from that version (see [the methodology memo](methodology/counting-a-participant.md) and the",
        "[CHANGELOG](methodology/CHANGELOG.md)). Counting rules C1 to C15 are in ADR-005.",
        "",
        "## Additivity",
        "",
        "| Value | Meaning |",
        "|---|---|",
    ]
    out += [f"| `{k}` | {v} |" for k, v in ADDITIVITY.items()]
    for key, title in GROUPS:
        group = [r for r in rows if r["kpi_group"] == key]
        if not group:
            continue
        out += ["", f"## {title}", "", "| Metric | Name | Definition | Grain | Additivity | Unit | Owner | Since |", "|---|---|---|---|---|---|---|---|"]
        out += [f"| `{r['metric_id']}` | {_cell(r['name'])} | {_cell(r['definition'])} | {_cell(r['grain'])} | `{r['additivity']}` | {r['unit']} | {_cell(r['owner'])} | {r['introduced_in']}{' (definition changed ' + r['definition_changed_in'] + ')' if r['definition_changed_in'] else ''} |" for r in group]
    return "\n".join(out) + "\n"


def main() -> None:
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
