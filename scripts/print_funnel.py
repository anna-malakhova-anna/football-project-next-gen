"""Print the fan acquisition funnel (rework step 6): participant households -> linked -> contactable -> active -> monetized -> retained, by registration cohort and fan status,
with the step conversion rates. Counts only (restricted `linkage` schema). UNLINKED is its own line.

  uv run python -m scripts.print_funnel
"""
from __future__ import annotations


import duckdb
from scripts.common import DB



def pct(v) -> str:
    return "    n/a" if v is None else f"{v * 100:5.1f}%"


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    q = lambda sql: con.execute(sql).fetchall()  # noqa: E731
    print("SYNTHETIC DATA. The fan funnel by registration cohort, measured at the end of the cohort year. Stages are cumulative; rates are step rates.\n")
    print(f"{'cohort':>6} {'status':18s} {'households':>10} {'linked':>7} {'contact.':>8} {'active':>7} {'monetized':>9} {'retained':>8} | {'link':>6} {'contact':>7} {'active':>7} {'monetize':>8} {'retain':>7}")
    for r in q("select cohort_year, fan_status, households, linked_households, contactable_households, active_households, monetized_households, retained_households, "
               "link_rate, contactable_rate, active_rate, monetized_rate, retained_rate from linkage.mart_fan_funnel "
               "where segment = 'ALL' and market_type = 'ALL' and fan_status in ('ALL', 'EXISTING_ACTIVE', 'NET_NEW', 'UNLINKED') "
               "order by cohort_year, case fan_status when 'ALL' then 0 when 'EXISTING_ACTIVE' then 1 when 'NET_NEW' then 2 else 3 end"):
        print(f"{r[0]:>6} {r[1]:18s} {r[2]:>10,} {r[3]:>7,} {r[4]:>8,} {r[5]:>7,} {r[6]:>9,} {r[7]:>8,} | {pct(r[8])} {pct(r[9])} {pct(r[10])} {pct(r[11])} {pct(r[12])}")
    print("\nSegments (all cohorts, all statuses): who converts?")
    print(f"{'segment':26s} {'households':>10} {'link':>6} {'contact':>7} {'active':>7} {'monetize':>8}")
    for r in q("select segment, sum(households), sum(linked_households), sum(contactable_households), sum(active_households), sum(monetized_households) "
               "from linkage.mart_fan_funnel where market_type = 'ALL' and fan_status = 'ALL' group by 1 order by 2 desc"):
        print(f"{r[0]:26s} {r[1]:>10,} {pct(r[2] / r[1])} {pct(r[3] / r[2]) if r[2] else '   n/a'} {pct(r[4] / r[3]) if r[3] else '   n/a'} {pct(r[5] / r[4]) if r[4] else '   n/a'}")
    cohort = q("select last_observed_year from reference.observation_window")[0][0]      # the latest cohort, read from the data window
    print(f"\nThe unconditional counts show the cost of the funnel's order (cohort {cohort}, all statuses):")
    r = q("select linked_households, contactable_regardless, contactable_households, active_regardless, active_households from linkage.mart_fan_funnel "
          f"where cohort_year = {cohort} and segment = 'ALL' and market_type = 'ALL' and fan_status = 'ALL'")[0]
    print(f"  linked {r[0]:,}; contactable {r[2]:,} (consent held by {r[1]:,} linked accounts); active and contactable {r[4]:,} (active whether or not contactable: {r[3]:,})")


if __name__ == "__main__":
    main()
