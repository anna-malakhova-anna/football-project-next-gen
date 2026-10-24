"""Print the household -> fan account linkage results: the link rate, who gets linked, and how right the links are (ground truth is read only through
the evaluation models). Counts and shares only; the restricted `linkage` schema holds contacts and is never printed.

  uv run python -m scripts.print_linkage
"""
from __future__ import annotations


import duckdb
from scripts.common import DB



def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    q = lambda sql: con.execute(sql).fetchall()  # noqa: E731
    print("SYNTHETIC DATA. Household -> fan account linkage (ADR-009: restricted zone, aggregate output only).\n")
    print("1. Households and the link rate")
    for m, d, n, s in q("select measure, detail, n, share from linkage.linkage_summary"):
        print(f"   {m:22s} {d:13s} {n:>7,}" + ("" if s is None else f"  {s:6.1%}"))
    print("\n2. Who gets linked (link rate by group; a gap in share_of_linked vs share_of_all means the linked set is not representative)")
    for dim, val, linked, households, rate, gap in q("select dimension, value, linked, households, link_rate, share_gap from linkage.linkage_link_bias "
                                                     "where dimension in ('country', 'children') order by dimension, value"):
        print(f"   {dim:9s} {val:13s} {linked:>5,} of {households:>5,} linked  {rate:6.1%}  share gap {gap:+.1%}")
    print("\n3. Household formation vs truth")
    for m, n, s in q("select measure, n, share from evaluation.eval_household_formation"):
        print(f"   {m:28s} {n:>6,}" + ("" if s is None else f"  {s:6.1%}"))
    print("\n4. Links vs truth")
    for m, n, v in q("select measure, n, value from evaluation.eval_household_linkage"):
        print(f"   {m:55s} {n:>6,}" + ("" if v is None else f"  {v:6.1%}"))


if __name__ == "__main__":
    main()
