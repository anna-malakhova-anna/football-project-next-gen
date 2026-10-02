"""Render the executive participation report. FORMATTING ONLY: no calculations.

Reads ONLY from the exec share (share_exec.*) and the KPI scorecard (measurement.mart_kpi_scorecard); every number in the
report is a value those tables already hold. Where the exec share suppressed a small cell, the report says so and shows no
number. Data-trust figures sit directly under the headline numbers, not in an appendix.

  uv run python -m scripts.render_report [year]        (make report)
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "warehouse" / "flag.duckdb"
OUT_DIR = ROOT / "docs" / "reports"
MEMO = "../methodology/counting-a-participant.md"

# the ONLY relations this script may read
SOURCES = ("share_exec.share_exec__participation_by_country", "share_exec.share_exec__participation_segments",
           "share_exec.share_exec__reported_headcount", "measurement.mart_kpi_scorecard")

HEADLINE = [("north_star", "unique_participants"), ("growth", "new_participants"), ("growth", "returning_participants"),
            ("growth", "retention_rate"), ("growth", "reactivated_participants"), ("reach", "youth_girls_participants"),
            ("reach", "girls_share_of_youth"), ("reach", "international_participants"), ("reach", "countries_with_participants"),
            ("depth", "multi_org_participants"), ("depth", "registrations_per_participant")]
TRUST = ["identity_range_pct", "pct_participants_high_confidence", "open_review_items", "pct_registrations_failing_dq",
         "sources_onboarded", "sources_known"]
RATE_KPIS = {"retention_rate", "girls_share_of_youth", "identity_range_pct", "pct_participants_high_confidence", "pct_registrations_failing_dq"}
RATIO_KPIS = {"registrations_per_participant"}


def fmt_value(kpi: str, v) -> str:
    if v is None:
        return "not defined"
    if kpi in RATE_KPIS:
        return f"{v:.1%}"
    if kpi in RATIO_KPIS:
        return f"{v:.2f}"
    return f"{v:,.0f}"


def fmt_change(kpi: str, change, pct) -> str:
    if change is None:
        return "n/a"
    if kpi in RATE_KPIS:
        pts = f"{change * 100:+.1f}"
        return ("0.0" if pts in ("+0.0", "-0.0") else pts) + " pts"
    if kpi in RATIO_KPIS:
        return f"{change:+.2f}"
    return f"{change:+,.0f}" + ("" if pct is None else f" ({pct:+.1%})")


def fmt_bounds(kpi: str, low, high) -> str:
    return "" if low is None or high is None else f"{fmt_value(kpi, low)} to {fmt_value(kpi, high)}"


def fmt_cell(v, suppressed: str) -> str:
    if v is not None:
        return f"{v:,.0f}"
    return "suppressed" if suppressed != "NONE" else "n/a"


def table(header: list[str], rows: list[list[str]]) -> str:
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(r) + " |" for r in rows])


def render(con: duckdb.DuckDBPyConnection, year: int) -> str:
    kpi = {r[0]: r[1:] for r in con.execute(
        "select kpi_id, kpi_name, value, prior_year_value, yoy_change, yoy_change_pct, low, high, methodology_version "
        "from measurement.mart_kpi_scorecard where participation_year = ?", [year]).fetchall()}
    if not kpi:
        raise SystemExit(f"no scorecard rows for {year}")
    version = next(iter(kpi.values()))[-1]

    def row(k: str, with_bounds: bool = True) -> list[str]:
        name, value, prior, change, pct, low, high, _ = kpi[k]
        cells = [name, fmt_value(k, value), fmt_value(k, prior) if prior is not None else "n/a", fmt_change(k, change, pct)]
        return cells + ([fmt_bounds(k, low, high)] if with_bounds else [])

    headline = table(["Headline", str(year), "Prior year", "Change", "Identity range (low to high)"], [row(k) for _, k in HEADLINE])
    trust = table(["Data trust", str(year), "Prior year", "Change"], [row(k, False) for k in TRUST])

    countries = con.execute(
        "select country_code, participants_attributed, participants_present, suppressed "
        "from share_exec.share_exec__participation_by_country where participation_year = ? order by country_code nulls first", [year]).fetchall()
    country_rows = [["All countries" if c is None else c, fmt_cell(a, s), "n/a" if c is None else fmt_cell(p, s)] for c, a, p, s in countries]
    country_table = table(["Country", "Participants (attributed, adds up)", "Participants (present, overlaps)"], country_rows)

    girls = con.execute(
        "select participation_year, participants, girls_share_of_youth, suppressed from share_exec.share_exec__participation_segments "
        "where country_code is null and age_band is null order by participation_year").fetchall()
    girls_rows = [[str(y), fmt_cell(p, s), "suppressed" if g is None else f"{g:.1%}"] for y, p, g, s in girls]
    girls_table = table(["Year", "Participants", "Girls' share of youth participation"], girls_rows)
    youth_girls = con.execute(
        "select participation_year, value from measurement.mart_kpi_scorecard where kpi_id = 'youth_girls_participants' order by 1").fetchall()
    youth_table = table(["Year", "Youth girls participants"], [[str(y), fmt_value("youth_girls_participants", v)] for y, v in youth_girls])

    reach_section = ""
    if "reported_headcount" in kpi:      # methodology 1.1 onwards; the share is read as published, nothing is calculated here
        rh = con.execute(
            "select country_code, reporting_programs, reported_headcount, voluntary_program_headcount, combined_reach_low, combined_reach_high, suppressed "
            "from share_exec.share_exec__reported_headcount where participation_year = ? order by country_code nulls first", [year]).fetchall()
        rh_rows = [["All countries" if c is None else c, fmt_cell(p, sup), fmt_cell(h, sup), fmt_cell(v, sup),
                    "suppressed" if lo is None else f"{lo:,.0f} to {hi:,.0f}"] for c, p, h, v, lo, hi, sup in rh]
        reach_section = f"""## Appendix: school and recreation program reach, {year} (a stretch source, not part of the headline)

{table(["Country", "Programs reporting", "Children reported (program places)", "Of which voluntary", "Combined reach with participants (range)"], rh_rows)}

These are children counted by schools and recreation departments. They are **not** participants and are **not** added to the participant
count: an aggregate cannot be matched to people, so some of these children are also registered participants and some are counted in more
than one program. The combined reach is therefore a **range**: the low end assumes as much overlap as is possible, the high end assumes none.
*Voluntary* means intramural and after-school programs; PE units are exposure during class, not participation. Countries with fewer than
10 reporting programs are suppressed.

"""
    return f"""# Participation report {year}

> **Synthetic data.** Every person in this report is generated. Numbers count **registered participants in onboarded
> sources**: not total flag football participation, and a registration is not proof that someone played a game.
> *DRAFT numbers from the exec share and the KPI scorecard; the narrative is for the program team to write.*

## Headline numbers, with how far to trust them

{headline}

Identity range: how much identity resolution alone could move a number (a person split in two, or two people merged). It
does **not** cover missing sources, informal play, or errors in the source data.

### Data trust (read with the numbers above)

{trust}

## Participants by country, {year}

{country_table}

Use the **attributed** column for totals: each person is counted once, in the country of their most recent registration this
year. The **present** column counts a person in every country they played in, so it adds up to more than the total; use it
to answer "who played here". Cells too small to publish safely are shown as *suppressed*.

## Girls' participation

{girls_table}

{youth_table}

Girls' share is registration-reported sex over all youth participants (sex not captured stays in the denominator, never
guessed). Youth means 17 or under on December 31 of the year.

{reach_section}---
*Methodology version {version}. How a participant is counted: [counting a participant]({MEMO}). Generated by
`scripts/render_report.py` from `share_exec` and `mart_kpi_scorecard`; it performs no calculations.*
"""


def main(argv: list[str]) -> int:
    con = duckdb.connect(str(DB), read_only=True)
    try:
        year = int(argv[0]) if argv else con.execute("select max(participation_year) from measurement.mart_kpi_scorecard").fetchone()[0]
        text = render(con, year)
    finally:
        con.close()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"participation_report_{year}.md"
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
