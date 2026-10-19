"""Phase 5 feedback-loop demo (spec 3.5 and 6.4): what if the organizations that received a fix list acted on it? SIMULATED.

  uv run python -m scripts.fix_list_demo

Regenerates the three registration sources with `org_quality.fix_list_adoption` switched on (an exact share of the STRUGGLING organizations behave like TYPICAL ones in the final season only), loads and
rebuilds the label-free quality outputs in a COPY of the warehouse, and compares them with the current (adoption-off) warehouse. The warehouse itself is not changed. Writes docs/reports/fix_list_demo.md.
The adopters are known from the answer key only to the script (to say who adopted); every number compared is a label-free output of the scorecards and the nuance layer.
Because the generator places defects with weights by profile, switching the scenario on also reshuffles the defects of organizations that did not adopt (their overall rates are unchanged). The comparison
therefore sets the adopters against the STRUGGLING organizations that did not adopt, not against their own history alone.
"""
from __future__ import annotations

import copy
import shutil
import subprocess
import tempfile
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from generator import main as gen
from generator.population import load_config
from loader import load_raw
from scripts import validate_contracts

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "warehouse" / "flag.duckdb"
OUT = ROOT / "docs" / "reports" / "fix_list_demo.md"
SELECT = ["+dq_scorecard_org", "+dq_fix_list", "+dq_fix_ranking", "+mart_uncertainty_decomposition", "+mart_missingness_bias"]
PURPOSES = ("COUNT", "SEGMENT", "GEO", "RETAIN", "ACTIVATE")


def rebuild(tmp: Path, scenario_db: Path, cfg: dict) -> tuple[set[str], set[str]]:
    gen.run(cfg, raw_dir=str(tmp / "raw"), truth_dir=str(tmp / "truth"))
    load_raw.load(raw_dir=str(tmp / "raw"), db_path=str(scenario_db), cfg=cfg)
    validate_contracts.validate(db_path=scenario_db, write=True)
    (tmp / "profiles.yml").write_text(f"counting_flag_football:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n      path: {scenario_db}\n      threads: 4\n", encoding="utf-8")
    subprocess.run(["uv", "run", "dbt", "run", "--profiles-dir", str(tmp), "--target-path", str(tmp / "target"), "--select", *SELECT], cwd=ROOT / "dbt", check=True, capture_output=True)
    truth = pq.read_table(tmp / "truth" / "org_quality_truth.parquet").to_pylist()
    return {t["org_id"] for t in truth if t.get("adopted_fix_list")}, {t["org_id"] for t in truth if t["profile"] == "STRUGGLING" and not t.get("adopted_fix_list")}


def org_scores(db: Path, year: int, adopters: set[str], controls: set[str]) -> dict:
    con = duckdb.connect(str(db), read_only=True)
    try:
        out = {}
        for group, ids in (("adopters", adopters), ("struggling_non_adopters", controls)):
            idl = ",".join("'" + i.replace("'", "''") + "'" for i in sorted(ids)) or "''"
            out[group] = {p: con.execute(f"select round(avg(score), 2), count(*) from quality.dq_scorecard_org where dimension = 'PURPOSE_SCORE' and purpose = ? and season_year = ? and reported and org_id in ({idl})", [p, year]).fetchone()
                          for p in PURPOSES}
        return out
    finally:
        con.close()


def nuance(db: Path, year: int) -> dict:
    con = duckdb.connect(str(db), read_only=True)
    try:
        dq = con.execute("select point, low, high, contribution from quality.mart_uncertainty_decomposition where participation_year = ? and component = 'DQ_EXCLUSIONS'", [year]).fetchone()
        mb = con.execute("""select value_known_only, bound_low, bound_high, bound_high - bound_low, unknown, total from quality.mart_missingness_bias
                            where participation_year = ? and kpi = 'girls_share_of_youth' and segment_value = 'ALL' and club_market_id = 'ALL'""", [year]).fetchone()
        return {"dq": dq, "mb": mb}
    finally:
        con.close()


def persist(year: int, bs: dict, as_: dict, bn: dict, an: dict) -> None:
    """The numbers of the report, for the site (SIMULATED scenario): demo_fix_list.scores (purpose scores) and demo_fix_list.nuance (the nuance-layer measures). Counts and scores only."""
    con = duckdb.connect(str(DB))
    try:
        con.execute("create schema if not exists demo_fix_list")
        con.execute("create or replace table demo_fix_list.scores (season_year integer, org_group varchar, purpose varchar, orgs_scored integer, score_before double, score_after double)")
        names = {"adopters": "Organizations that acted on the fix list", "struggling_non_adopters": "Comparison: struggling organizations that did not"}
        con.executemany("insert into demo_fix_list.scores values (?, ?, ?, ?, ?, ?)",
                        [(year, names[g], p, bs[g][p][1], bs[g][p][0], as_[g][p][0]) for g in bs for p in PURPOSES])
        con.execute("create or replace table demo_fix_list.nuance (season_year integer, measure varchar, value_before double, value_after double)")
        con.executemany("insert into demo_fix_list.nuance values (?, ?, ?, ?)", [
            (year, "Participants lost under strict COUNT handling (DQ-exclusions component)", bn["dq"][3], an["dq"][3]),
            (year, "Youth participants with unknown gender", bn["mb"][4], an["mb"][4]),
            (year, "Width of the girls' share bounds (share points)", bn["mb"][3], an["mb"][3])])
    finally:
        con.close()


def main() -> None:
    cfg = load_config()
    year = max(cfg["seasons"]["years"])
    scen = copy.deepcopy(cfg)
    scen["org_quality"]["fix_list_adoption"]["enabled"] = True
    tmp = Path(tempfile.mkdtemp(prefix="fix_list_demo_"))
    try:
        scenario_db = tmp / "scenario.duckdb"
        shutil.copy(DB, scenario_db)
        adopters, controls = rebuild(tmp, scenario_db, scen)
        before_scores, after_scores = org_scores(DB, year, adopters, controls), org_scores(scenario_db, year, adopters, controls)
        before_n, after_n = nuance(DB, year), nuance(scenario_db, year)
        share = scen["org_quality"]["fix_list_adoption"]
        lines = [
            "# Feedback-loop demo: what if the fix list were acted on?",
            "",
            "> **SIMULATED.** Synthetic data and a made-up scenario: this shows what the engine would report if organizations acted on their fix list, not that any organization does or would.",
            f"> In the final season ({year}) {share['share_of_struggling_orgs']:.0%} of the STRUGGLING organizations ({len(adopters)} of them) behave like {share['final_season_improves_to']} ones (`org_quality.fix_list_adoption`, off by default).",
            "> Reproduce with `make fix-list-demo`. The warehouse is not changed: everything is rebuilt in a copy.",
            "",
            "## Purpose scores of the organizations that acted, final season",
            "",
            "Mean PURPOSE_SCORE (0 to 100) of organizations that reported in the season. *Before* is the current build, *after* the scenario. The STRUGGLING organizations that did not act are the comparison, because switching the scenario on reshuffles where defects fall (overall rates unchanged).",
            "",
            "| Purpose | Adopters before | Adopters after | Change | Comparison before | Comparison after | Change |",
            "|---|---|---|---|---|---|---|",
        ]
        for p in PURPOSES:
            a0, a1 = before_scores["adopters"][p][0], after_scores["adopters"][p][0]
            c0, c1 = before_scores["struggling_non_adopters"][p][0], after_scores["struggling_non_adopters"][p][0]
            f = lambda v: "n/a" if v is None else f"{v:.1f}"
            d = lambda x, y: "n/a" if x is None or y is None else f"{y - x:+.1f}"
            lines.append(f"| {p} | {f(a0)} | {f(a1)} | {d(a0, a1)} | {f(c0)} | {f(c1)} | {d(c0, c1)} |")
        n_ad = before_scores["adopters"]["COUNT"][1]
        lines += ["", f"Organizations scored: {n_ad} adopters that reported, {before_scores['struggling_non_adopters']['COUNT'][1]} comparison organizations.", ""]
        (d0, m0), (d1, m1) = (before_n["dq"], before_n["mb"]), (after_n["dq"], after_n["mb"])
        lines += [
            "## The nuance layer, final season",
            "",
            "| Measure | Before | After |",
            "|---|---|---|",
            f"| DQ-exclusions component: participants lost if only COUNT-fit records are counted | {d0[3]:.0f} | {d1[3]:.0f} |",
            f"| Girls' share of youth: participants with unknown gender | {m0[4]:.0f} of {m0[5]:.0f} | {m1[4]:.0f} of {m1[5]:.0f} |",
            f"| Girls' share of youth: width of the bounds (no imputation) | {m0[3]:.4f} | {m1[3]:.4f} |",
            "",
            "## How to read this",
            "",
            "- A fix at the source shows up clearly in the organizations' own scores (the retention and segmentation purposes most) and narrows the missingness bounds and the DQ-exclusions component only slightly, because the headline uncertainty is mostly coverage (organizations that sent no file), which a fix list does not touch. The cheapest way to improve an organization's numbers is upstream; it does not close the coverage gap.",
            "- What is simulated: that organizations act, and that acting makes them look like TYPICAL organizations for one season. What is not: any real organization, any real effect size.",
            "- The scenario regenerates the data, so small movements elsewhere are noise from where defects fall. Read the adopters against the comparison column, and read changes of a point or two as noise.",
            "- Whether a real fix list changes behaviour is an open question for the program owner; this demo cannot answer it.",
        ]
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        persist(year, before_scores, after_scores, before_n, after_n)
        print("\n".join(lines))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
