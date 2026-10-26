# ADR-029: Market prioritization and the Now/Next/Later board (DRAFT scores and lanes, for Anna to set)

- **Status:** Proposed for step 7 of the Phase 7 spec, 2026-10-26. **The method follows Anna's decision D5. The scores, lanes, actions and gates are drafts by Claude Code: Anna sets them.**
- **Synthetic data.** Privacy-risk scores rest on assumed regimes (`legal_regime`, unverified), not legal findings.

## Method (D5: the data products page's method)
1. **Four dimensions, 1 to 5:** value to goals, feasibility today, data readiness, privacy risk (5 is riskiest). **Priority = value + feasibility + readiness − privacy risk**, as in `product_prioritization`. The rank breaks ties by country code (ADR-023).
2. **Draft scores come from a rubric** (`gmp_priority_rubric`), applied in `mart_gmp_priority`, so no market's score is typed:

   | Dimension | Draft rule |
   |---|---|
   | Value to goals | clubs with rights: 10 or more = 5, 6 to 9 = 4, 3 to 5 = 3, 2 = 2, 1 = 1; plus 1 if new to the program (at most 5) |
   | Feasibility today | Measured 5, Partial 4, proxy-only with a national federation 3, proxy-only without one 2, dark 1 |
   | Data readiness | counting grade A 5, B 4, C 3, D 2, no data 1 |
   | Privacy risk | record-level returns under the EU, UK or Swiss regimes 4; record-level elsewhere 3; the aggregate minimum return 2; China 3 (PIPL data localization, assumed) |

3. **Anna's scores replace the draft** wherever she sets one (`gmp_market_priority_overrides`, empty today). `score_status` says whether a market's scores are DRAFT or SET_BY_ANNA.
4. **The board** (`gmp_market_roadmap`, a draft): one card per market. The lanes:
   - **MAINTAIN:** the Measured markets.
   - **NOW:** the two Partial markets, plus the two highest-ranked markets with no data.
   - **NEXT:** the next six.
   - **LATER:** the rest.

   Each card has an action and a gate. **The gate's value, status and bar are computed** in `mart_gmp_board` (PENDING, never 0, when a value is missing, as in the Phase 6 roadmap):
   - **Counting grade at least C:** the score against the band.
   - **Seasons of minimum return:** a known 0 for a market with no source.
   - **Proxy return filed:** for the darkest markets.

   Rationales state only the reason for the lane. Live facts (status, grade, clubs) come from the data.
5. **One port for the board** (`share_exec__gmp_board`, DP6 port `global_priorities`), not split by regime. It is a planning view across markets, and it carries nothing beyond what the regime ports already hold.

## The draft as it stands
- **Ranking:** Mexico, Canada, Germany, Austria, Spain, the UK; then Australia and Brazil, the highest-ranked markets with no data. Last are China and France.
  - Measured markets rank high because the method rewards feasibility and readiness, as on the products page.
  - Japan ranks 11th: only one club holds rights there.
- **Gates:** the five Measured markets meet "C or better". The UK and Japan are at 95% of the C bar (66.7 against 70). Every market with no data is at a known 0.

## Questions for Anna
1. The rubric's thresholds and the privacy-risk levels (especially China at 3, and EU/UK/Swiss record-level returns at 4).
2. ~~Whether Measured markets belong in the ranking at all, or only in MAINTAIN.~~ **Decided by Anna 2026-10-26: Measured markets stay in the ranking.**
3. The lanes. In particular, Italy (the walkthrough market) is in LATER on its rank. Move it up if the 2026 expansion makes it a priority.
