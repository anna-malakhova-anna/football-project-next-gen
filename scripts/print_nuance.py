"""Print the Phase 5 'nuance' results: the uncertainty decomposition against the truth, and the missingness bias in the girls' share against the truth. SYNTHETIC data.

  uv run python -m scripts.print_nuance            (make nuance)

The decomposition and the bias are label-free; the comparison with the truth (evaluation models) shows how well they work and is for the team, not for production.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "warehouse" / "flag.duckdb"


def table(rows, cols):
    cells = [[("-" if v is None else (f"{v:,.0f}" if isinstance(v, float) and abs(v) >= 100 else (f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)))) for v in r] for r in rows]
    widths = [max(len(c), *(len(r[i]) for r in cells)) if cells else len(c) for i, c in enumerate(cols)]
    print("  " + "  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for r in cells:
        print("  " + "  ".join(v.ljust(w) for v, w in zip(r, widths)))


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    print("UNCERTAINTY DECOMPOSITION: three separate bars around the reported participant count, never added\n")
    table(con.execute("""
        select participation_year, component, point, interval_low, interval_high, contribution from quality.mart_uncertainty_decomposition where participation_year >= (select max(participation_year) - 2 from quality.mart_uncertainty_decomposition)
        order by participation_year, case component when 'IDENTITY' then 1 when 'DQ_EXCLUSIONS' then 2 else 3 end""").fetchall(),
          ["year", "component", "point", "interval low", "interval high", "width"])
    print("\nTRUTH vs COMPONENTS (answer key; evaluation only)\n")
    table(con.execute("""
        select participation_year, true_participants_in_data, identity_low, identity_high, identity_interval_contains_truth as identity_ok, round(100 * identity_point_error, 1) as ident_err_pct,
               true_participants_missing_from_data as true_missing, round(coverage_low) as cov_low, round(coverage_point) as cov_point, round(coverage_high) as cov_high,
               coverage_interval_contains_truth as cov_ok, round(100 * coverage_point_error, 1) as cov_err_pct
        from evaluation.eval_uncertainty_decomposition order by 1""").fetchall(),
          ["year", "true in data", "id low", "id high", "id ok", "id err %", "true missing", "cov low", "cov point", "cov high", "cov ok", "cov err %"])
    print("\nMISSINGNESS BIAS: girls' share of youth (Phase 3 figure, known-only, Manski bounds with no imputation, and the verdict)\n")
    table(con.execute("""
        select participation_year, unknown, total, value_phase3, value_known_only, bound_low, bound_high, missing_share, missingness_verdict, associated_factors
        from quality.mart_missingness_bias where kpi = 'girls_share_of_youth' and segment_value = 'ALL' order by 1""").fetchall(),
          ["year", "unknown", "youth", "phase 3", "known only", "bound low", "bound high", "missing", "verdict", "associated with"])
    print("\n  where the 2025 blank genders concentrate (records):")
    t, d = con.execute("select top_orgs, top_divisions from quality.mart_missingness_bias where kpi = 'girls_share_of_youth' and participation_year = (select max(participation_year) from quality.mart_missingness_bias) limit 1").fetchone()
    print(f"    organizations: {t}\n    divisions:     {d}")
    print("\n  tests of 'missing at random' (2025, blank gender; approximate chi-square p-values):")
    table(con.execute("""select factor, records, records_missing, chi2, df, p_value, lowest_group_missing_rate, highest_group_missing_rate, associated_with_missingness
                         from quality.mart_missingness_tests where kpi = 'girls_share_of_youth' and participation_year = (select max(participation_year) from quality.mart_missingness_tests) order by factor""").fetchall(),
          ["factor", "records", "missing", "chi2", "df", "p", "lowest group", "highest group", "associated"])
    print("\nGIRLS' SHARE vs TRUTH (answer key; evaluation only)\n")
    table(con.execute("""select participation_year, true_girls_share, value_known_only, bound_low, bound_high, known_only_error, phase3_error, truth_inside_bounds, known_only_closer_than_phase3
                         from evaluation.eval_missingness_bias order by 1""").fetchall(),
          ["year", "truth", "known only", "bound low", "bound high", "known-only err", "phase 3 err", "truth inside", "known-only closer"])


if __name__ == "__main__":
    main()
