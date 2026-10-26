# ADR-026: Global outlook models (DP6), and what the first evaluation of the planning scenario says

- **Status:** Accepted for step 4 of the Phase 7 spec, 2026-10-26. Applies [ADR-025](ADR-025-global-status-direction-and-scenario.md) without changing a rule. The implementation choices below were made **before** the evaluation was run. The results are recorded as they came out.
- **Synthetic data.** Flag football only. Every count is generated. The answer key's against-the-comparables share is an assumption (ADR-025 section 5).

## Implementation choices (made before the evaluation)
1. **A new product, DP6 Global Markets Outlook** (`products/DP6`, status `proposed`, version 0.1.0). It owns `stg_gmp_proxy` and the `mart_gmp_*` marts, plus two exec share models: `share_exec__gmp_markets` and `share_exec__gmp_scenario`. Each carries its regime port as a column. Splitting the outputs into the three regime ports (spec D10) is step 6. DP6 reads other products only through their ports:
   - **DP3 gains an aggregate port**, `mart_participation_by_org`: distinct participants with a valid registration, per organization and year (non-additive across organizations). ADR-025 section 2 asked for it if none existed.
   - **DP4 gains an aggregate port**, `dq_scorecard_country`: `dq_scorecard_source`'s method grouped by country. The test `dq_scorecard_country_matches_source` checks that a one-country source (Canada, the US) scores identically in both, so the copy cannot drift.
   - The scenario reads DP3's published `share_exec__participation_by_country`, so it uses the same suppressed counts an executive sees.
2. **Pooled noise floor:** the pool uses only season pairs that meet the organization minimum (`min_orgs_both_seasons`). This was not spelled out in ADR-025. It keeps three-organization noise out of the floor only where the label would also be "not detectable".
3. **Proxy signal:** a return counts as a signal if events are above zero, a game was played, or a national federation exists (the three signals of ADR-025 section 4). Blank events count as unknown, never zero. A market-season filed twice keeps the latest report.
4. **Status uses the latest observed season's grade**; a market with a source but no filing organization that season is Partial.
5. **The Data product tab draws only products that have tab copy** (`charts.yml` `summary.product_names`). DP6 stays off the tab and the one-pager until its copy is written and approved; `validate_products` still checks its spec.
6. **GMP_PROXY's staging is aggregate-only** in `scripts/check_lineage.py`, so nothing that counts participants can read it.

## What the rules produced (no answer key involved)
- **Status:** Measured 5 (Austria, Canada, Germany, Spain at C; Mexico at B); Partial 2 (UK and Japan, D, limited by timeliness); Proxy-only 9; Dark 6 (UAE, France, Ireland, Italy, New Zealand, Switzerland). This matches ADR-025's stated expectation.
- **Direction:** the pooled noise floor is **25.6%** (7 season pairs), so the minimum detectable change is **51%**. Every Measured market reads **flat**, including Canada's +36% (14 organizations in both seasons). Japan is not detectable (2 organizations in both seasons). Club proxy direction disagrees with the participation label in 5 of the 6 markets where both exist.
- **Scenario:** with every comparable flat, every scenario direction is flat. Asia-Pacific, Middle East and Africa markets fall back to all Measured markets, because Japan, the only Asia-Pacific market with data, is Partial.

## The first evaluation (`eval_gmp_scenario_summary`)

| Markets | Truth inside the range | Below | Above | Direction wrong | Proxy direction right (of known) | Comparables differ from the generator's |
|---|---|---|---|---|---|---|
| All 15 | 5 (33%) | 1 | 9 | 15 (100%) | 0 of 8 | 8 |
| Moving with their comparables (9) | 4 (44%) | 1 | 4 | 9 | 0 of 5 | 6 |
| Set against their comparables (6) | 1 (17%) | 0 | 5 | 6 | 0 of 3 | 2 |

## What it means
- **The evidence supports Anna's decision D3** (no number for a market with no data). The range missed two thirds of markets, mostly by undershooting. Per-club rates from a few small markets say little about a market's size, which the answer key assumes is only weakly tied to clubs with rights.
- **The scenario cannot give a direction at all with this much data.** With a 51% minimum detectable change, the comparables are always flat, while the answer key labels any change beyond ±3% as a direction. The gap between "what matters" (a few percent) and "what can be detected" (half again) is the finding for the executive: more organizations per market, not a cleverer formula, is what would make a direction readable.
- **Club proxy returns are not a substitute.** They matched the true direction in none of the 8 markets where they were known. The answer key makes them only weakly related to participation (an assumption), so this shows what weak proxies would do, not what real club returns would.
- **Where generator and dbt disagree on comparables** (8 markets), dbt drops the two Partial markets. That is reported, not corrected (ADR-025 addendum).
- No rule, threshold or parameter was changed after the evaluation. Changing one would need a new ADR that names this result.
