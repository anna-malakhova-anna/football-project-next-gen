"""Export the Phase 5 scorecard parameters from config/generation.yaml to dbt/seeds/p5_params.csv, so dbt never hard-codes a threshold or a season start."""
from __future__ import annotations

import csv
from pathlib import Path

from generator.population import load_config


def build_rows(cfg: dict) -> list[dict]:
    c5 = cfg["phase5"]
    rows = [{"param": f"season_start_{term.lower()}", "value": md, "description": f"Month-day the {term.title()} season starts (an assumption for the demonstration)."}
            for term, md in c5["season_start"].items()]
    rows += [{"param": k, "value": v, "description": f"phase5.dq.{k} in config/generation.yaml"} for k, v in c5["dq"].items()]
    return [{k: str(v) for k, v in r.items()} for r in rows]


def main(cfg: dict | None = None, out: str = "dbt/seeds/p5_params.csv") -> int:
    rows = build_rows(cfg or load_config())
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["param", "value", "description"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    print(f"{main()} Phase 5 parameters written")
