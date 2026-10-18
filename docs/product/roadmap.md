# Roadmap: vision, MVP, now / next / later

> **Draft for Anna.** The scores are proposals (`dbt/seeds/product_prioritization.csv`, status `DRAFT`), the MVP is a recommendation she confirms, and every target is a blank placeholder in `dbt/seeds/product_targets.csv`. Nothing here is a real target. Synthetic data.

## Vision
A trusted, privacy-safe picture of who plays flag football worldwide, where it is growing, and whether playing turns families into fans.

## How the products are scored
Each product gets four scores from 1 to 5: **value to the goals**, **feasibility today**, **data readiness** (from the Phase 5 data quality grades of its inputs), and **privacy risk** (5 is riskiest). Priority is value plus feasibility plus readiness minus privacy risk. The seed carries a written reason for every score.

| Product | Value | Feasibility | Readiness | Privacy risk | Priority (draft) |
|---|---|---|---|---|---|
| DP1 Intake | 4 | 5 | 3 | 1 | 11 |
| DP4 US growth and clubs | 5 | 4 | 3 | 2 | 10 |
| DP2 Participant and household master | 4 | 4 | 4 | 4 | 8 |
| DP3 Global participation | 4 | 3 | 2 | 2 | 7 |
| DP5 Flag-to-fan conversion | 5 | 2 | 1 | 5 | 3 |

## Recommended MVP (a proposal; Anna confirms)
**DP4, US Flag Growth & Club Market Insights, with DP1 as its required foundation.**

1. **The real pain is sparse, poor-quality domestic data.** DP4 with DP1 addresses it directly, and the fix list and the data standard improve the supply while the product is in use.
2. **DP5 cannot be trusted yet.** Participant counts, households and consent capture have to be reliable first. Today 3 of 11 sources are ready for contacting families and 67% of consent records show exactly what the family agreed to. Building DP5 first would produce confident numbers on weak foundations.
3. **DP3 relies on federation returns,** which are a lower priority than the domestic gap, and it can reuse DP4's methods.

## Now / next / later (no dates)
| Horizon | Release | Content | Exit criteria (thresholds are placeholders) |
|---|---|---|---|
| **Now** | DP1 v1 + DP4 v1 (the MVP) | Data standard, contracts, scorecards, club market view (aggregates), fix lists | At least **X%** of US records fit for counting and for placing on the map; clubs can read their market tile; the privacy lead signs off on the club share |
| **Next** | DP2 v1 formalized, DP3 v1 | The master and the review queue as a product; global participation with its uncertainty | Identity range at most **Y%**; at least **N** federations contracted |
| **Next** | DP5 v0 (analytics only) | Household-level fan engagement uplift in the restricted schema; aggregate outputs | Fully known consent provenance for at least **Z%** of consent records; privacy approval of the household linkage (ADR-009) |
| **Later** | DP5 v1 (activation) | Consent-gated club activation counts | A separate guardian consent for club marketing is captured at registration |

X, Y, Z and N are config values in `product_targets.csv`; Anna sets them.

## What would change this order
- If privacy approval for the household linkage comes early, DP5 v0 (analytics only) can move up. It still cannot reach activation without the guardian consent step.
- If federations start sending cleaner returns, DP3 moves ahead of DP2's formalization.
