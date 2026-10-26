# ADR-027: A partner audience for federation report cards, a minimum-return template, and a quality trend per market

- **Status:** Accepted for step 5 of the Phase 7 spec, 2026-10-26. Applies Anna's decisions D4 (quality: score federations, send report cards, build checks into the template, track a trend) and D13 (a new `partner` audience).
- **Synthetic data.** Roles are fictional. How a federation would receive its card, and the 5-player minimum roster, are **assumptions**.

## Decisions
1. **An eighth audience, `partner`** (schema `share_partner`): a data partner's view of its **own** data quality. Like exec, it gets no direct identifier (`scripts/check_share_policy.py`), and every column is in `audience_column_policy.csv`. DuckDB has no per-user grants (ADR-006), so "a federation sees only itself" is a **row scope**: the `federation` column, applied when the card is sent. The test `share_partner_rows_are_scoped_to_one_federation` checks that every row names one program-market federation, that no federation has more than three fixes, and that no small cell is published.
2. **The report card** (`mart_gmp_federation_report`, then `share_partner__federation_report_card`, DP6's port `federation_report_card`). For each of the six federations, in the latest season:
   - the counting grade and its change since the previous season;
   - clubs known, and clubs that filed;
   - **how many more clubs would have to file for the market to read Measured**. This is given only when timeliness alone holds the grade back and every other counting dimension already clears the band. It is never a promise where filing alone would not be enough.
   - the **top three fixes**: DP1's `dq_fix_list` (each club's ranked list, records affected, no identity) summed over the federation's clubs. A fix that moves the counting grade (the COUNT purpose, which market status rests on) ranks first, then by records affected. Records affected below `k_min` are hidden.
   - **DP4's impact ranking is deliberately not used.** Its impact is measured on linked households, and the share-policy check (`LINKAGE_LEAK`) refused a partner share with household linkage upstream. Nothing household-linked reaches a partner (ADR-009).
3. **The minimum-return template** (`contracts/templates/GMP_MINIMUM_RETURN.yml`, with an example in `docs/playbook/templates/`): season, region, age band, teams, girls, boys, sex not recorded, players. It contains no individual and no consent field, so it is the first thing to ask a market with no data for. Its checks are the ones a federation runs **before** sending:
   - players = girls + boys + not recorded;
   - every team has at least the minimum roster;
   - no round-number estimates;
   - age bands from the list;
   - no duplicate rows.

   It sits outside `contracts/*.yml`, so it does not validate on every build. `tests/test_minimum_return_template.py` runs it through the same validator as every contract: the example passes, and each kind of mistake is caught by its own check.
4. **A quality trend per market for the exec tab** (`share_exec__gmp_quality_trend`): counting score, grade, limiting dimension, clubs known and filed, per season, for the seven markets with a participation source.

## What the cards say (latest season)
- **UK and Japan (Partial, D):** 4 of 6 clubs filed. **One more filing** would make each market Measured. Their top fix is the one that moves the counting grade: get the missing clubs to file.
- **Mexico (B, up from C):** all six clubs filed, so its fixes are consent records (wording version, consent time, a parent email).
- **Spain (C, down from B):** one of its four clubs did not file.
- **Austria and Germany (C, unchanged):** one missing club each.

## Consequences
- The access-policy document (`make docs`) lists the partner audience and how it is enforced. The site's audience summary gains a row.
- The GMP_PROXY onboarding log is complete through Modelled.
- Sending a card to a real federation would need an agreement and a channel. Both are out of scope; the share is what would be sent.
