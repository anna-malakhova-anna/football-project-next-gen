"""Print the Phase 5 data quality scorecards: the source scorecard (latest season) and the worst organizations, by purpose. SYNTHETIC data.

  uv run python -m scripts.print_dq            (make dq)

Reads warehouse/flag.duckdb. The scorecards are label-free (no ground truth): they use only the rule registry and what the data and the organization registry say.
A purpose score is the MINIMUM of its dimension scores (ADR-014); `limiting` names the weakest dimension.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "warehouse" / "flag.duckdb"
PURPOSES = ["COUNT", "SEGMENT", "GEO", "RETAIN", "ACTIVATE"]


def table(rows, cols):
    cells = [[("-" if v is None else (f"{v:.1f}" if isinstance(v, float) else str(v))) for v in r] for r in rows]
    widths = [max(len(c), *(len(r[i]) for r in cells)) if cells else len(c) for i, c in enumerate(cols)]
    print("  " + "  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for r in cells:
        print("  " + "  ".join(v.ljust(w) for v, w in zip(r, widths)))


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    season = con.execute("select max(season_year) from quality.dq_scorecard_source").fetchone()[0]
    print(f"SOURCE SCORECARD, season {season}: purpose score (0-100) and grade; limiting = the weakest dimension\n")
    rows = con.execute("""
        select source_system, purpose, score, grade, limiting_dimension, record_count, reporting_orgs, known_orgs
        from quality.dq_scorecard_source where season_year = ? and dimension = 'PURPOSE_SCORE' order by source_system, purpose""", [season]).fetchall()
    by_source: dict[str, dict] = {}
    for s, p, score, g, lim, n, rep, known in rows:
        by_source.setdefault(s, {"n": n, "orgs": f"{rep}/{known}" if known else "-"})[p] = f"{score:.0f} {g} ({lim[:4].lower() if lim else '-'})"
    table([[s, d["n"], d["orgs"], *[d.get(p, "-") for p in PURPOSES]] for s, d in by_source.items()], ["source", "records", "orgs reporting", *PURPOSES])

    print(f"\nFIVE WORST REPORTING ORGANIZATIONS OF THE MODELLED SOURCES, season {season} (mean of the five purpose scores; Wilson lower bound where the sample is small)")
    print("(the six Phase 5 channel feeds are scored too; school rosters lack a ZIP and an email by design and would crowd this list, so they are shown below)\n")
    worst = con.execute("""
        with s as (
            select source_system, org_id, org_name, channel, record_count, interval_applied,
                   avg(score) as mean_score, list(purpose || ' ' || grade order by purpose) as grades
            from quality.dq_scorecard_org where season_year = ? and dimension = 'PURPOSE_SCORE' and reported
              and source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') group by all)
        select * from s order by mean_score limit 5""", [season]).fetchall()
    table([[w[0], f"{w[2]} [{w[1]}]", w[3], w[4], "yes" if w[5] else "no", round(w[6], 1), ", ".join(w[7])] for w in worst],
          ["source", "organization [id]", "channel", "records", "interval", "mean score", "grades by purpose"])
    for w in worst:
        print(f"\n  {w[2]} ({w[0]}): what limits it")
        for p, lim, rules in con.execute("""select purpose, limiting_dimension, top_failing_rules from quality.dq_scorecard_org
                                           where season_year = ? and org_id = ? and source_system = ? and dimension = 'PURPOSE_SCORE' order by score limit 2""", [season, w[1], w[0]]).fetchall():
            for rid in rules[:2]:
                guide = con.execute("select fix_guidance from reference.dq_rule_registry where rule_id = ?", [rid]).fetchone()
                print(f"    {p:9s} limited by {lim.lower():18s} {rid}: {guide[0] if guide else ''}")

    print(f"\nWORST CHANNEL-FEED ORGANIZATIONS (the six Phase 5 feeds), season {season}\n")
    cw = con.execute("""
        select source_system, org_name, record_count, round(avg(score), 1), list(purpose || ' ' || grade order by purpose)
        from quality.dq_scorecard_org where season_year = ? and dimension = 'PURPOSE_SCORE' and reported and source_system not in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED')
        group by all order by 4 limit 3""", [season]).fetchall()
    table([[a, b, c, d, ", ".join(e)] for a, b, c, d, e in cw], ["feed", "organization", "records", "mean score", "grades by purpose"])

    dark = con.execute("""select count(*) filter (where not reported), count(*) from quality.dq_scorecard_org where season_year = ? and dimension = 'PURPOSE_SCORE' and purpose = 'COUNT'""", [season]).fetchone()
    print(f"\nDARK ORGANIZATIONS: {dark[0]} of {dark[1]} known organizations sent no file in {season}; each scores 0 on timeliness and so on every purpose.")
    print("Coverage and the other dimensions are not independent: the minimum rule means the share of organizations that report caps every organization-based source.")
    ooc = con.execute("select entity_type, count(*) filter (where out_of_control), count(*) from quality.dq_trend where prior_seasons >= 1 group by 1 order by 1").fetchall()
    print("\nTREND (P-chart), points outside the control limits: " + "; ".join(f"{t} {o} of {n}" for t, o, n in ooc))


if __name__ == "__main__":
    main()
