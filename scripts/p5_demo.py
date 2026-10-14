"""Phase 5 demo: one club market end to end, in the order of the talk. SYNTHETIC data; the club and the market are invented.

  uv run python -m scripts.p5_demo [--market MKT-06] [--interactive] [--no-answer-key]

Prerequisites: `make p5-feeds p5-score p5-retention` (the Makefile target `p5-demo` runs them). Everything printed is a count or a rate; no child, parent or record is shown.
Counts under the club minimum cell size are printed as "<10" (in tables and in the fix text).
--interactive waits for Enter at each pause; --no-answer-key drops the lines that use the synthetic ground truth (use it for an audience that should not see them).
A market with no club or no published view exits with the list of markets that work. Lines marked (answer key) use the synthetic ground truth and exist only to show how well the method does.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "warehouse" / "flag.duckdb"


def q(con, sql, params=None):
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def one(con, sql, params=None):
    return q(con, sql, params)[0]


def table(rows: list[dict], cols: list[str] | None = None, k: int | None = None, k_cols: tuple = ()) -> None:
    if not rows:
        print("  (none)")
        return
    cols = cols or list(rows[0])
    def fmt(c, v):
        if v is None:
            return "-"
        if k and c in k_cols and isinstance(v, int) and not isinstance(v, bool) and 0 < v < k:
            return f"<{k}"
        if isinstance(v, float):
            return f"{v:.3f}".rstrip("0").rstrip(".")
        return str(v)
    cells = [[fmt(c, r[c]) for c in cols] for r in rows]
    widths = [max(len(c), *(len(row[i]) for row in cells)) for i, c in enumerate(cols)]
    print("  " + "  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for row in cells:
        print("  " + "  ".join(v.ljust(w) for v, w in zip(row, widths)))


def heading(n: int, title: str) -> None:
    print(f"\n{'=' * 100}\n{n}. {title}\n{'=' * 100}")


INTERACTIVE = False
ANSWER_KEY = True


def pause(who: str, line: str) -> None:
    print(f"\n  >>> PAUSE for the {who}: \"{line}\"")
    if INTERACTIVE:
        try:
            input("      (press Enter to continue) ")
        except EOFError:                                    # not a terminal: carry on
            pass


def key(text: str) -> None:
    """A line that uses the synthetic answer key: shown only with the answer key on."""
    if ANSWER_KEY:
        print(text)


def mask(text: str, k: int) -> str:
    """Hide small counts inside free text ("on 3 registrations") the same way tables hide small cells."""
    return re.sub(r"\b([1-9]\d?)\b(?= (registrations|records|rows))", lambda m: f"<{k}" if int(m.group(1)) < k else m.group(1), text)


def pick_market(con) -> str:
    return one(con, """select market_id from phase5_club.p5_club_market_view
                       where status = 'PUBLISHED' and club_market_role = 'PRIMARY' order by participation_estimate desc limit 1""")["market_id"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market")
    ap.add_argument("--interactive", action="store_true", help="wait for Enter at each pause, for presenting")
    ap.add_argument("--no-answer-key", action="store_true", help="omit the lines that use the synthetic answer key")
    args = ap.parse_args()
    global INTERACTIVE, ANSWER_KEY
    INTERACTIVE, ANSWER_KEY = args.interactive, not args.no_answer_key
    con = duckdb.connect(str(DB), read_only=True)
    m = args.market or pick_market(con)
    k = int(one(con, "select value from reference.p5_params where param = 'club_min_cell'")["value"])
    status = q(con, "select status from phase5_club.p5_club_market_view where market_id = ? limit 1", [m])
    if not status or status[0]["status"] != "PUBLISHED":
        good = [r["market_id"] for r in q(con, "select distinct market_id from phase5_club.p5_club_market_view where status = 'PUBLISHED' order by 1")]
        why = "is not in any club's territory" if not status else f"has status {status[0]['status']} (no children observed, or too few to publish)"
        sys.exit(f"Market {m} {why}, so there is no club view to demo. Markets that work: {', '.join(good)}")
    club = one(con, "select club_name, market_name, club_market_role from phase5_club.p5_club_market_view where market_id = ? limit 1", [m])
    print(f"PHASE 5 DEMO: {club['club_name']}, {club['market_name']} ({m}, {club['club_market_role'].lower()} market). All data synthetic.")

    heading(1, "The mess: the feeds that reach one market")
    n_feeds = one(con, "select count(distinct feed) as n from phase5.p5_record_quality where market_id = ?", [m])["n"]
    print(f"  {n_feeds} of the six feeds place children here. School rosters carry no ZIP, so their children cannot be placed in any market (they are allocated in the estimate, step 5).")
    table(q(con, """select feed, count(*) as registrations, count(*) filter (where is_exact_duplicate_row) as exact_duplicate_rows,
                           count(distinct league_group) as leagues from phase5.p5_record_quality where market_id = ? group by 1 order by 2 desc""", [m]), k=k, k_cols=("registrations", "exact_duplicate_rows"))
    print("\n  Record-level defects in this market (pass rate; 1 = clean):")
    table(q(con, """select rule_id, description, round(pass_rate, 3) as pass_rate, n_fail from phase5.dq_rule_results_market
                    where market_id = ? and pass_rate < 0.97 and dimension <> 'CONSENT_PROVENANCE' order by pass_rate limit 6""", [m]),
          ["rule_id", "pass_rate", "n_fail", "description"], k=k, k_cols=("n_fail",))

    heading(2, "Resolution: the Phase 2 engine, reused, across the six feeds")
    r = one(con, """select (select count(*) from phase5.p5_record_quality where market_id = ?) as registrations,
                           (select count(*) from phase5_restricted.p5_child where market_id = ?) as children_resolved""", [m, m])
    dup = one(con, """select round(100.0 * count(*) filter (where is_exact_duplicate_row) / count(*), 1) as pct_exact_duplicates,
                             round(100.0 * count(*) filter (where not is_first_of_child_season) / count(*), 1) as pct_duplicates_after_resolution
                      from phase5.p5_record_quality where market_id = ?""", [m])
    print(f"  {r['registrations']} registrations -> {r['children_resolved']} resolved children (latest season). Duplicates caught before resolution: {dup['pct_exact_duplicates']}%; after: {dup['pct_duplicates_after_resolution']}%.")
    ev = one(con, "select precision, recall, sibling_or_twin_false_merge_pairs as sibling_merges from evaluation.eval_p5_resolution")
    key(f"  (answer key, all markets) precision {ev['precision']}, recall {ev['recall']}, sibling false-merge pairs {ev['sibling_merges']}: a finding, not hidden.")

    heading(3, "Scorecard: this market's leagues, graded")
    table(q(con, """select s.league_name, s.feed, s.grade, s.overall_score, s.fit_for_participation_reporting as fit_reporting, s.fit_for_club_activation as fit_activation, count(distinct c.p5_person_id) as children_here
                    from phase5_restricted.p5_child c join phase5.dq_score_league s on s.league_group = c.league_group
                    where c.market_id = ? group by all order by children_here desc limit 8""", [m]), k=k, k_cols=("children_here",))
    print("\n  Top fix for each of those leagues (what an operator can act on; the organization's own issue, ranked by impact):")
    fixes = q(con, """select f.org_name as league_name, f.rule_id, f.fix_guidance || ' (' || f.records_affected || ' records)' as fix from quality.dq_fix_list f
                      where f.season_year = (select max(season_year) from quality.dq_fix_list) and not f.is_systemic and f.rank_in_scope = 1 and f.org_id in
                      (select league_group from phase5_restricted.p5_child where market_id = ? group by 1 order by count(*) desc limit 4)""", [m])
    for row in fixes:
        row["fix"] = mask(row["fix"], k)
    table(fixes)
    mk = one(con, "select market_name, grade, overall_score, fit_for_participation_reporting as fit_reporting, fit_for_club_activation as fit_activation from phase5.dq_score_market where market_id = ?", [m])
    print(f"\n  This market overall: grade {mk['grade']} (score {mk['overall_score']}); fit for participation reporting: {mk['fit_reporting']}; fit for club activation: {mk['fit_activation']}.")
    pause("clubs lead", "here is what you can trust: counts by market and age band, yes; contacting households, not yet.")

    heading(4, "Consent provenance funnel: where households drop out, and why")
    f = one(con, f"""
        with hh as (select distinct h.household_id from phase5_restricted.p5_household_child h join phase5_restricted.p5_child c using (p5_person_id) where c.market_id = ?)
        select (select count(*) from phase5_restricted.p5_child where market_id = ?) as participants,
               (select count(distinct h.p5_person_id) from phase5_restricted.p5_household_child h join phase5_restricted.p5_child c using (p5_person_id) where c.market_id = ?) as children_in_a_contactable_household,
               (select count(*) from hh) as resolved_households,
               (select count(distinct household_id) from phase5_restricted.p5_consent_event where provenance_known and household_id in (select household_id from hh)) as known_consent_provenance,
               (select count(*) from phase5_restricted.p5_household_activation where eligible_for_club_activation and household_id in (select household_id from hh)) as eligible_for_club_activation""", [m, m, m])
    table([f], k=k, k_cols=tuple(f))
    print("\n  Why households are not eligible (counts under the minimum cell size shown as <%d):" % k)
    table(q(con, """select activation_status, count(*) as households from phase5_restricted.p5_household_activation a
                    where household_id in (select h.household_id from phase5_restricted.p5_household_child h join phase5_restricted.p5_child c using (p5_person_id) where c.market_id = ?)
                    group by 1 order by 2 desc""", [m]), k=k, k_cols=("households",))
    pl = one(con, "select league_comms_granted, admitted_only_by_a_careless_reading as blocked_by_purpose_limitation from phase5.p5_purpose_limitation")
    print(f"\n  Purpose limitation (all markets): {pl['league_comms_granted']} households agreed to league emails; treating that as marketing consent would have admitted {pl['blocked_by_purpose_limitation']} more. It does not.")
    ra = q(con, "select reason, sum(children) as children_deleted, sum(records) as records_deleted from pii_store.retained_aggregate where market_id = ? group by 1 order by 1", [m])
    last = one(con, "select max(run_id) as run_id, any_value(as_of) as as_of from pii_store.retention_log")
    print(f"\n  The deletion job (run {last['run_id']}, as of {last['as_of']}; periods are assumptions). Only aggregates are kept for this market:")
    table(ra, k=k, k_cols=("children_deleted", "records_deleted"))
    pause("privacy lead", "here is what never leaves the league: the child's name and birth year, and the parent's email. And here is the deletion job; its log holds counts only.")

    heading(5, "Market estimate: participation rate with a band, against the (synthetic) youth population")
    e = one(con, """select participation_estimate, estimate_low, estimate_high, youth_population, round(100 * participation_rate, 2) as rate_pct,
                           round(100 * participation_rate_low, 2) as rate_low_pct, round(100 * participation_rate_high, 2) as rate_high_pct, confidence, data_quality_grade, top_data_gaps
                    from phase5_club.p5_club_market_view where market_id = ? limit 1""", [m])
    print(f"  Estimate {e['participation_estimate']} children (band {e['estimate_low']} to {e['estimate_high']}) of a youth population of {e['youth_population']} (SYNTHETIC STUB, not Census): "
          f"{e['rate_pct']}% ({e['rate_low_pct']}% to {e['rate_high_pct']}%). Confidence {e['confidence']}, data quality grade {e['data_quality_grade']}.")
    print(f"  Top data gaps: {mask(e['top_data_gaps'] or 'none', k)}")
    t = one(con, "select naive_count, estimate, true_children, band_contains_truth from evaluation.eval_p5_market_estimate where market_id = ?", [m])
    key(f"  (answer key) true children {t['true_children']}; naive count {t['naive_count']}; estimate {round(t['estimate'])}; band contains the truth: {t['band_contains_truth']}. "
        "The estimate tends to run high across markets (docs/market-estimate.md), so read the band, not the point.")
    print("\n  Age bands (observed, placed children; small cells suppressed):")
    table(q(con, "select coalesce(age_band, 'TOTAL') as age_band, children, suppressed from phase5_club.p5_club_market_age_view where market_id = ? order by age_band nulls last limit 9", [m]), k=None)

    heading(6, "The ask: the data standard for next season")
    print("  For the feeds in this market, the standard fields they do not yet meet (95% present and valid):")
    table(q(con, """select source_system as feed, core_fields_met || '/' || core_fields as core_met, consent_fields_met || '/' || consent_fields as consent_met, array_to_string(failing_fields, ', ') as to_fix
                    from quality.dq_standard_summary where season_year = (select max(season_year) from quality.dq_standard_summary) and source_system in (select distinct feed from phase5.p5_record_quality where market_id = ?) order by source_system""", [m]))
    print("\n  The ask in one line: send birth year (not date of birth), ZIP3, the canonical league id, flag registrations only, and with each consent: when, which wording, which purposes, how.")
    print("  What it costs to ask for less (birth year and ZIP3 instead of date of birth and ZIP5): about 4 points of recall, no loss of precision (docs/data-standard.md).")
    print("\nDone. Open questions for the stakeholders: docs/questions-for-stakeholders.md")


if __name__ == "__main__":
    main()
