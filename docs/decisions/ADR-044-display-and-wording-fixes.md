# ADR-044: Display and wording fixes across the site (no number or method changed)

- **Status:** Accepted, 2026-10-27, from Anna's review list. Every fix is at its source (formatter, dataset SQL, copy or label), never in generated HTML.

## Causes found and fixes
1. **"410.0%" on Data quality (Q4 table).** `share_pct` is already a percent (0 to 100), but the formatter read any `_pct` value of 5 or less as a fraction and multiplied it by 100. Columns that hold percents are now listed (`PERCENT_UNIT_COLUMNS`) and print as they are. The scan found one other exposed column, `participant_count_error_pct` (0.1 to 0.2 percent).
2. **"2,024" in year columns.** `first_year`, `season_year` and `year` were not plain identifiers. Every year or season column now prints without a separator (`is_year_column`).
3. **Mixed precision for "per 1,000".** One rule gave 4 decimals below 10 and 1 decimal above. Every per-100 or per-1,000 rate now has one decimal.
4. **"6 Products" on the one-page summary.** It counted every product spec, including DP6. It now counts the portfolio the tab draws: 5.
5. **Girls' share.** The landing page's 47% is the share of youth players whose sex is recorded, the same figure as the Data products scorecard's 46.8%. The Participation chart's 46.5% includes players with no sex recorded. The landing page names its denominator, and the chart's note names both.
6. **24 versus "26 markets graded".** The market scorecard grades the 24 club markets plus two groups, players in no club market and players outside the US. DP4's label and health panel now say so.
7. **"16 health measures" versus "15".** Both read the same count: 16 goal measures, 1 not measurable by design. The landing page now calls them goal measures and mentions the separate product health panels.
8. **"Markets shown 10" versus "Markets 20".** This is suppression: small markets are rolled up and not drawn. The Audience page now says so, with the count from the data.
9. **Texas market 2, "0 of 0 leagues reporting".** Confirmed. Players are allocated by ZIP3 weight, while each league belongs to the one market with the highest weight for its ZIP3 (ADR-016; the handover said ADR-020). The tile and panel now say "Players placed here by ZIP code; no league is assigned to this market yet". **The grade is unchanged:** whether to grade such markets was a method question for Anna, settled by ADR-045: they keep their grade.
10. **Coverage band above the index line.** Correct, not a bug. The band is the players counted plus the estimate for leagues that sent nothing, on the same first-year base, so it can never fall below the line. The card says so.
11. **Purple funnel segment.** The data already separates the two. Purple is only DECLINED and REVOKED, and "never asked" (a marketing choice never captured) was already in the orange fixable segment. Only the label was wrong: it now reads "Said no or withdrew", and the glossary entry is corrected.
12. **Linking versus consent.**
    - **Landing and Audience pages:** a sentence names both limits with figures from the data: 36% linked, 75% of those contactable, 1 of 4 consent forms naming club marketing.
    - **One-page summary:** the same point without numbers, because its numbers must come from Data products exports.

## Final scan
- **Percents over 100%:** one, a +215.8% restatement change on Identity and governance, which is a real increase.
- **Years with commas:** none.
- **Headline figures:** consistent. Some appear in rounded forms by design: "about 1,260" fan accounts on Acquisition and Value; the one-page summary's 7,400 players and about 1,300 fans.
