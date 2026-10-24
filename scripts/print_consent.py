"""Print the consent provenance results and the activation funnel. SYNTHETIC data.

  uv run python -m scripts.print_consent            (make consent)

Counts only. The funnel separates DQ losses (the data cannot say) from PRIVACY losses (the family said no or withdrew). The last block compares the Phase 3 marketing contact list with the
consent chain: it is a FINDING, reported, not a change to the Phase 3 share.
"""
from __future__ import annotations


import duckdb
from scripts.common import DB, print_table



def _cell(v) -> str:
    return "-" if v is None else (f"{v:,}" if isinstance(v, int) and not isinstance(v, bool) else str(v))


def table(rows, cols):
    print_table(rows, cols, _cell)


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    year = con.execute("select max(participation_year) from quality.mart_activation_funnel").fetchone()[0]
    print(f"ACTIVATION FUNNEL, national, {year}: losses split into DQ (the data cannot say) and PRIVACY (the family said no)\n")
    table(con.execute("""select step_no, step, n, lost, lost_unit, lost_dq, lost_privacy from quality.mart_activation_funnel
                         where market_id = 'ALL' and participation_year = ? order by step_no""", [year]).fetchall(), ["step", "what", "n", "lost", "unit change", "DQ loss", "PRIVACY loss"])
    print("\n  why households leave:")
    table(con.execute("""select step_no, reason, loss_type, households from quality.mart_activation_funnel_loss where market_id = 'ALL' and participation_year = ? and reason <> 'CONSENTING'
                         order by step_no, households desc""", [year]).fetchall(), ["step", "reason", "type", "households"])
    print(f"\nCONSENT PROVENANCE by source and wording version ({year} registrations): KNOWN_FULL needs the wording version, a time and the purpose named\n")
    table(con.execute("""
        select e.source_system, e.consent_text_version, count(*) as events,
               round(100.0 * count(*) filter (where provenance_grade = 'KNOWN_FULL') / count(*), 1) as pct_full,
               round(100.0 * count(*) filter (where provenance_grade = 'KNOWN_PARTIAL') / count(*), 1) as pct_partial,
               round(100.0 * count(*) filter (where provenance_grade = 'UNKNOWN') / count(*), 1) as pct_unknown
        from linkage.int_consent_event e where e.event_kind = 'MARKETING_OPT_IN' and e.season_year = ? group by all order by 1, 2""", [year]).fetchall(),
          ["source", "wording version", "marketing events", "% full", "% partial", "% unknown"])
    print("\nMARKETING OPT-INS BY WHAT THE FORM NAMED (all years): an opt-in on a form that never named the purpose is not evidence of that consent\n")
    table(con.execute("""select status, has_purpose_coverage as form_names_purpose, count(*) as events from linkage.int_consent_event where event_kind = 'MARKETING_OPT_IN' group by all order by 1, 2""").fetchall(),
          ["choice", "form names club marketing", "events"])
    print(f"\nFINDING: the Phase 3 marketing contact list against the consent chain ({year})\n")
    r = con.execute("""
        with c as (select contact_email from share_marketing.share_marketing__contact_list),
        hh as (select distinct c.contact_email, s.marketing_status
               from c join marts.dim_participant d on d.contact_email = c.contact_email
               join linkage.int_household h on h.participant_id = d.participant_id
               join linkage.int_household_year_consent s on s.household_id = h.household_id and s.participation_year = ?)
        select (select count(*) from c), count(distinct contact_email) filter (where marketing_status = 'GRANTED_FULL'),
               count(distinct contact_email) filter (where marketing_status = 'GRANTED_INCOMPLETE'), count(distinct contact_email) filter (where marketing_status = 'REVOKED'),
               count(distinct contact_email) filter (where marketing_status not in ('GRANTED_FULL', 'GRANTED_INCOMPLETE', 'REVOKED'))
        from hh""", [year]).fetchone()
    print(f"  contacts on the Phase 3 list: {r[0]:,}; of those matched to a {year} household: GRANTED_FULL {r[1]:,}, GRANTED_INCOMPLETE {r[2]:,} (opt-in on a form without the purpose), REVOKED {r[3]:,}, other {r[4]:,}.")
    print("  The Phase 3 list applies its own rule (every participant sharing the address opted in). It does not read the wording or a revocation. Reported, not changed here.")


if __name__ == "__main__":
    main()
