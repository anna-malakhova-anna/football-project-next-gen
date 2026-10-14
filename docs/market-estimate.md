# Estimate instead of enrich: the market participation estimate

**Audience:** club analytics leads (what can I trust in my territory) and the privacy lead (what is never bought or shared).
All data is **synthetic**: the markets, clubs, youth population and every count describe a generated world, and the clubs are invented (no real club, team or metro is represented).

## Why we do not enrich
The tempting fix for sparse youth participation data is to buy third-party enrichment on the children (demographics, households, interests). We do not, for three reasons. It means disclosing minors' data to a
data provider, and under the amended COPPA Rule disclosure of under-13 data to a third party needs separate verifiable parental consent unless it is integral to the service; advertising and data-broker
disclosures are not (public source: Finnegan, linked in the data standard). It contradicts the minimization the [data standard](data-standard.md) asks of leagues. And it would not fix the actual problem, which is
that registrations are unattributed, unplaced or duplicated. Instead we **estimate from aggregates**: what we can count, what we can place, what we can allocate, and how unsure that leaves us. Whether a club is a
"third party" for COPPA purposes, given joint ownership, is an open question for the privacy lead and is not decided here.

## How a child is placed in a club market
1. **ZIP to market.** The child's home ZIP3 maps to a market (`market_geo_map`). A child with no usable ZIP is *unplaced*.
2. **Market to club (`p5_club_territory`).** Each synthetic club owns one or more markets. Two cases are handled on purpose, as in reality:
   - **Shared markets** (the New York, Los Angeles and Bay Area pattern): the market's first listing in a configured state is owned by every club in that state (`role = SHARED`). Each club sees the same **market-level** figures; counts are never split between clubs, because a split would invent precision.
   - **Areas with no club**: some markets have no row. They are estimated for the data steward (`p5_market_estimate`, coverage `NO_CLUB`) and are absent from every club-facing table.
   The design (which states share, which markets are uncovered) is configuration (`phase5.club_design`) and an **assumption**, not a statement about any real club's territory.
3. **Unplaced children are allocated, not dropped.** A child with no ZIP counts once, spread over markets in proportion to where *placed children of the same league* live (needs at least five), else of the same state; else they stay unallocated and are reported as such. This is an estimate, and each market shows how many children it contains only by allocation (`allocated_children`).

## The estimate and its band
For the latest season, per market:

| Quantity | Definition |
|---|---|
| **Estimate** | placed children + allocated share of unplaced children |
| **Low** | the estimate minus *weakly identified* children (no parent email and no birth year, i.e. school rosters, which no rule could match to another registration and which may all duplicate a child already counted), scaled by the label-free low end of the identity range (PROBABLE links also merged), times `(1 - band_base)` |
| **High** | estimate x `(1 + band_base + band_k x missing)`, where *missing* = 1 minus the pass rate of the counting rules (`band_rules`: league identified, age signal present, ZIP present, league current) |
| **Rate** | estimate / youth population (ages 5 to 17) of the market |
| **Confidence** | HIGH, MEDIUM or LOW by the band's relative width (`confidence_high`, `confidence_medium`); NO_DATA when no child was observed |

**This band is a rule of thumb that makes poor data look uncertain. It is not a statistical confidence interval**, and its parameters are configuration, not fitted. The less complete a market's counting data, the wider the upper end. A market with no observed child is `NO_DATA`: we cannot tell zero participation from no feed.

## The youth population is a labelled stub
The real source would be ACS 5-year estimates (ages 5 to 17, ZCTA aggregated to ZIP3). Synthetic ZIPs do not correspond to real ZCTAs, so joining real Census data would produce meaningless rates. `p5_youth_population_zip3` is therefore a **synthetic stub** (the market's invented household population spread over its ZIP3s, times 0.55 youth per household, with noise); every row says `SYNTHETIC STUB: not US Census / ACS data`. In a real deployment replace the seed, and note the rate is then only as good as the ZIP3 to market mapping.

## What a club sees
Two tables in schema `phase5_club`, both aggregate only (no row is a child, no column can identify one):
- `p5_club_market_view`: per club and market, the estimate with its band, the rate with its band, confidence, the market's data quality grade, and its top data gaps. Estimates under the minimum cell size (`club_min_cell`, default 10) are suppressed.
- `p5_club_market_age_view`: observed children per market and age band, with primary and secondary suppression (the shared macro from ADR-006), so a hidden cell cannot be recovered from the total.
The test `p5_club_view_is_aggregate_only` fails the build if the schema holds a table or column not in `p5_club_view_policy`, a child-like column name, a count cell between 1 and the minimum size minus one, or a duplicate club-market row.

## How well it works (synthetic answer key, evaluation only)
Graded in `eval_p5_market_estimate` against the true number of children registered in the latest season whose home is in the market, next to the naive count (children placed by ZIP, nothing else).

- The point estimate **overshoots**: mean error about 8%, against about 5% for the naive count. The reason is the matcher's recall limit (0.87): children it could not link are counted more than once, and allocating the unplaced adds to it. Using the naive count is closer on average only because under-counting unplaced children happens to offset the duplicates.
- The **first design** of the low end (identity range from PROBABLE links only) contained the truth in **9 of 20** markets. The weakly identified adjustment was added *after* seeing that miss, so the **20 of 20** coverage of the final design is not an independent test: it was designed knowing the answer. Both numbers are in ADR-012.
- Confidence is MEDIUM or LOW in every market with data, never HIGH: the data is not complete enough to claim more.

## Open questions
Which market boundaries clubs actually use; how shared metros should be reported to each club; whether the activation purpose can ever be served from a market estimate (it cannot, by design: no household or child is in this view).
