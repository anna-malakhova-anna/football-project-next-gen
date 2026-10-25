"""Print the club-market lens: coverage, grades and the funnel by club market. SYNTHETIC data; the club markets are a PROJECT APPROXIMATION (contiguous ZIP3 groups), not any club's territory.

  uv run python -m scripts.print_markets            (make markets)

Counts are allocated (fractional where a ZIP3 is shared). No participation rate is shown unless population_denominators is loaded: it is empty until Anna runs scripts/fetch_acs_youth_population.py.
"""
from __future__ import annotations


import duckdb
from scripts.common import DB, print_table



def _cell(v) -> str:
    return "-" if v is None else ((f"{v:,.3f}" if abs(v) < 2 else f"{v:,.1f}") if isinstance(v, float) else str(v))


def table(rows, cols):
    print_table(rows, cols, _cell)


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    y = con.execute("select max(participation_year) from quality.mart_market_coverage").fetchone()[0]
    print(f"CLUB-MARKET COVERAGE, {y}: the ten largest markets (allocated counts; a project approximation of territory)\n")
    table(con.execute("""
        select club_market_id, participants_allocated, participants_zip_placed as placed, participants_unplaced_allocated as unplaced_alloc, orgs_known, orgs_reporting, orgs_dark,
               coverage_point as dark_est, interval_low, interval_high, pct_records_geo_fit as geo_fit, grade_count || grade_segment || grade_geo || grade_retain || grade_activate as grades_CSGRA
        from quality.mart_market_coverage where participation_year = ? and club_market_id not in ('OUTSIDE_US', 'UNALLOCATED') order by participants_allocated desc limit 10""", [y]).fetchall(),
          ["market", "participants", "placed", "unplaced (alloc.)", "orgs known", "reporting", "dark", "dark est.", "interval low", "interval high", "geo fit", "grades C S G R A"])
    r = con.execute("""select sum(participants_allocated) filter (where club_market_id not in ('OUTSIDE_US')), sum(participants_unplaced_allocated), sum(participants_allocated) filter (where club_market_id = 'NO_CLUB_MARKET'),
                              sum(participants_outside_us), min(denominator_status) from quality.mart_market_coverage where participation_year = ?""", [y]).fetchone()
    print(f"\n  US participants {r[0]:,.0f} (of which allocated because they have no usable ZIP: {r[1]:,.0f}); in ZIP3s with no club: {r[2]:,.0f}; outside the US: {r[3]:,.0f}. Participation rate: {r[4]}.")
    print("\nSHARED MARKETS: a ZIP3 shared by two markets splits each participant equally (the labelled default)\n")
    table(con.execute("select mapping_method, count(distinct zip3) as zip3s, count(distinct club_market_id) as markets from reference.club_market_map group by 1 order by 1").fetchall(), ["method", "ZIP3", "markets"])
    print(f"\nACTIVATION FUNNEL by club market, {y}: households consenting to CLUB_MARKETING (allocated), with the split of the loss\n")
    table(con.execute("""
        select market_id, max(n) filter (where step_no = 3) as households, max(n) filter (where step_no = 5) as known_provenance, max(n) filter (where step_no = 6) as consenting,
               max(lost_dq) filter (where step_no = 6) as dq_loss_at_6, max(lost_privacy) filter (where step_no = 6) as privacy_loss_at_6
        from quality.mart_activation_funnel where participation_year = ? and market_id not in ('ALL', 'UNALLOCATED') group by 1 order by households desc limit 8""", [y]).fetchall(),
          ["market", "households", "known provenance", "consenting", "DQ loss (step 6)", "PRIVACY loss (step 6)"])
    print(f"\nGIRLS' SHARE OF YOUTH BY MARKET with bounds (US markets, {y})\n")
    table(con.execute("""select club_market_id, total, unknown, value_known_only, bound_low, bound_high from quality.mart_missingness_bias
                         where participation_year = ? and kpi = 'girls_share_of_youth' and club_market_id not in ('ALL', 'OUTSIDE_US', 'NO_CLUB_MARKET') order by total desc limit 6""", [y]).fetchall(),
          ["market", "youth", "unknown", "known only", "bound low", "bound high"])


if __name__ == "__main__":
    main()
