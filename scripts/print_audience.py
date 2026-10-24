"""Print the addressable audience and the consent gap (rework step 9): contactable participant households by channel over time, the consent gap and its illustrative value, consent capture by capture
point and partner, and opt-outs against engagement volume. Aggregates only (restricted `linkage` schema); the gap is valued in SYNTHETIC CURRENCY.

  uv run python -m scripts.print_audience
"""
from __future__ import annotations


import duckdb
from scripts.common import DB



def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    q = lambda sql: con.execute(sql).fetchall()  # noqa: E731
    print("SYNTHETIC DATA. Governance sets the size of the marketable audience. Guardian accounts only; UNLINKED households have no account and so no consent.\n")
    print("1. Participant households and who we can talk to (December of each year)")
    print(f"   {'year':>4s} {'registered':>10s} {'linked':>7s} {'contactable':>11s} {'email':>6s} {'sms':>5s} {'push':>5s} | {'active':>7s} {'consent gap':>11s} {'gap value (synthetic)':>22s}")
    for r in q("select year(month), households_registered, linked_households, contactable_households, contactable_email, contactable_sms, contactable_push, active_households, "
               "consent_gap_households, consent_gap_value from linkage.mart_addressable_audience where household_group = 'ALL' and month(month) = 12 order by 1"):
        print(f"   {r[0]:>4d} {r[1]:>10,} {r[2]:>7,} {r[3]:>11,} {r[4]:>6,} {r[5]:>5,} {r[6]:>5,} | {r[7]:>7,} {r[8]:>11,} {r[9]:>22,.0f}")
    print("\n   The consent gap is households whose account is ACTIVE but with NO channel opted in; valued at the median net spend of monetized households that year (illustrative, not revenue).")
    print("\n2. By household group, December of the last year")
    for r in q("select household_group, households_registered, linked_households, contactable_households, consent_gap_households from linkage.mart_addressable_audience "
               "where month = (select max(month) from linkage.mart_addressable_audience) order by 1"):
        print(f"   {r[0]:22s} registered {r[1]:>6,}  linked {r[2]:>5,}  contactable {r[3]:>5,}  consent gap {r[4]:>4,}")
    print("\n3. Consent capture: opt-in rate among the lines that exist (no line means not captured)")
    print(f"   {'capture point':20s} {'email':>7s} {'sms':>7s} {'push':>7s}")
    for cp in ("signup", "checkout", "flag_registration", "preference_center"):
        d = dict(q(f"select channel, opt_in_rate from linkage.mart_consent_capture where cut = 'BY_CAPTURE_POINT' and dimension_value = '{cp}'"))
        print(f"   {cp:20s} {d['email']:>7.1%} {d['sms']:>7.1%} {d['push']:>7.1%}")
    print("   Flag registration prompt, by source system (email opt-in):")
    for dv, n, rate in q("select dimension_value, consent_lines, opt_in_rate from linkage.mart_consent_capture where cut = 'BY_SOURCE_SYSTEM' and channel = 'email' order by 3 desc"):
        print(f"     {dv:12s} {n:>5,} lines  {rate:>6.1%}")
    n_rel = q("select count(*) filter (where reliable), count(*) from linkage.mart_consent_capture where cut = 'BY_PARTNER' and channel = 'email'")[0]
    print(f"   By partner (organization): {n_rel[0]} of {n_rel[1]} partners have enough lines to read (k_min); the rest are noise.")
    print("\n4. Opt-outs per 1,000 opted-in email account-months, by engagement volume that month (association only)")
    for b, rate in q("select engagement_band, opt_outs_per_1000_account_months from linkage.mart_opt_out_after_contact where channel = 'email' and engagement_band <> 'ALL' order by engagement_band"):
        print(f"   {b:>4s} events: {rate:>6.1f}")
    r = q("select account_channels_compared, mismatches, unsafe_mismatches, unsafe_mismatches_flagged_as_doubtful from evaluation.eval_consent_history")[0]
    print(f"\n5. Consent history against the truth: {r[0]:,} account-channels compared, {r[1]} differ ({r[2]} unsafe: history says opt-in, the account opted out), {r[3]} of the unsafe ones carry the out-of-order flag.")


if __name__ == "__main__":
    main()
