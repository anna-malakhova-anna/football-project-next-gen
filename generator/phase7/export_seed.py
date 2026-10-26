"""Export the Phase 7 rule parameters (ADR-025) from config/generation.yaml to dbt/seeds/p7_params.csv, so no global-outlook model hard-codes a threshold.

Only the rules dbt applies are exported (status, direction, scenario label). The answer-key and proxy parameters stay in config: dbt never needs them.
"""
from __future__ import annotations

import csv
from pathlib import Path

from generator.population import load_config


def build_rows(cfg: dict) -> list[dict]:
    p7 = cfg["phase7"]
    rows = [{"param": "measured_min_grade", "value": p7["status"]["measured_min_grade"],
             "description": "phase7.status.measured_min_grade: counting purpose grade at or above this band = Measured, below = Partial (ADR-025)"}]
    rows += [{"param": k, "value": v, "description": f"phase7.direction.{k} in config/generation.yaml (ADR-025)"} for k, v in p7["direction"].items()]
    rows.append({"param": "scenario_label", "value": p7["scenario"]["label"], "description": "phase7.scenario.label: carried on every planning-scenario row"})
    return [{k: str(v) for k, v in r.items()} for r in rows]


def main(cfg: dict | None = None, out: str = "dbt/seeds/p7_params.csv") -> int:
    rows = build_rows(cfg or load_config())
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["param", "value", "description"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    print(f"wrote {main()} rows to dbt/seeds/p7_params.csv")
