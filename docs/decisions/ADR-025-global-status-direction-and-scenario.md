# ADR-025: Global outlook rules, fixed before the answer key exists: market status, direction, and the dark-market scenario

- **Status:** Accepted for step 2 of the Phase 7 spec, 2026-10-25. Written **before** any Phase 7 ground truth is generated or read (ADR-010, ADR-011). Anna's decisions it applies: D1, D2, D3, D11 and D12 of the spec. Every parameter is in `config/generation.yaml` under `phase7` (exported to a seed); no model hard-codes one.
- **Synthetic data.** Flag football only. The markets are the 22 of the NFL Global Markets Program (ADR-024); every count is generated.

## Context
The executive asks where flag football is growing abroad, where we cannot tell, and what to do next. Seven program markets have participation data (Austria, Canada, Germany, Japan, Mexico, Spain, the United Kingdom); fifteen have none. Leagues want a number for those fifteen. Anna decided: no estimate in any published figure, a clearly labelled planning scenario for dark markets, and a synthetic answer key that shows what that scenario would get wrong.

The rules below are fixed now, so that the evaluation cannot be shaped by its own result.

## 1. Market status (one per market, latest season in `reference.observation_window`)

| Status | Rule |
|---|---|
| **Measured** | A participation source in the latest season, and the market's **counting purpose grade is C or better** (score at or above the C band of `dq_grade_bands`; the band is read, not restated). |
| **Partial** | A participation source exists, but the counting grade is D, or the market has no file in the latest season. |
| **Proxy-only** | No participation source, and at least one proxy signal in the latest season (section 4). |
| **Dark** | No participation source and no proxy signal. |

**The market's counting grade** is computed exactly as `dq_scorecard_source` computes a source's, grouped by country instead of source: severity-weighted dimension scores over the country's organizations, timeliness as the share of the country's known organizations that sent a file, purpose score = the minimum (ADR-014), Wilson interval below `dq_n_min`. Canada uses `CA_CLUB` (its only source); the other six use `INTL_FED`. The US is not a program market and gets no status.

**Expected, not tuned:** timeliness limits these grades today (about 67 for the UK and Japan, 75 to 100 for the others), so the UK and Japan should read Partial and the other five Measured. If the build shows otherwise, the rule stands and the expectation was wrong.

## 2. Direction (Measured and Partial markets only)

1. **Like for like.** Growth between season t-1 and t counts only organizations that sent a file in **both** seasons: g = (participants_t − participants_t-1) / participants_t-1 over those organizations. Participants are DP3's attributed counts, read through a port. If DP3 has no organization-season port yet, one is added as an aggregate port with small-cell suppression; DP6 never reads DP1 or DP3 internals.
2. **Noise floor.** σ = the **pooled** standard deviation of like-for-like growth over every Measured market and every season pair before the latest. It is pooled because no market has more than four season pairs, and some have one. With fewer than `phase7.direction.min_pooled_pairs` pairs in the pool, every market reads "not detectable".
3. **Label.** Growing if g > z·σ; shrinking if g < −z·σ; flat otherwise (z = `phase7.direction.z`). "Not detectable" if fewer than `phase7.direction.min_orgs_both_seasons` organizations reported in both seasons. Partial markets get a label, but it is shown with their status, never ranked.
4. **Rank** among Measured markets by g. No player counts appear on the map.
5. **Agreement.** The proxy direction (section 4) is shown beside the participation direction: agree, disagree, or no proxy. Components are shown side by side, never combined (ADR-015).
6. **Minimum detectable change** = z·σ. The tab says: "a one-season change smaller than this cannot be told apart from noise". The number of seasons a new market needs before it can have a direction is 2 (one like-for-like pair), plus whatever it takes to reach the organization minimum.

## 3. The planning scenario for dark and proxy-only markets (D3, D12)

1. **Comparables.** Measured markets with the **same region and the same legal regime** (`gmp_markets`). If there are none, the same region. If there are none, all Measured markets. The basis used is stored on every row (`comparable_basis`).
2. **Per-club rate.** For each comparable c in the latest season: r_c = participants_c / clubs_with_rights_c (clubs counted from `gmp_club_rights`).
3. **Range.** [min r_c, max r_c] × clubs_with_rights of the dark market. With one comparable, the range is that one rate times the dark market's clubs (low = high), and it says so.
4. **Scenario direction** = the comparables' direction if they all agree, else "mixed".
5. **Labels.** Every row carries "planning scenario, not a measurement". Scenario values live in their own share model and their own section of the tab. They are never summed with, ranked against or charted on the same axis as measured values.

This method is deliberately simple and explainable. It is **not** chosen or adjusted to do well against the answer key.

## 4. Proxy signals (the `GMP_PROXY` source, generated in step 3)
Per market and season: club fan events, games played in the market, and whether a national flag federation exists. Aggregate-only, onboarded through the playbook to `Contracted`, never counted as participation. Proxy direction = the sign of the change in (events + games) between the two latest seasons; "no proxy" if both are zero.

## 5. The answer key (generated in step 3, read only by `dbt/models/evaluation/`)
Stated now, so the evaluation's conditions are on record before its result:
- **Truth for the fifteen dark markets** comes from a new random stream (`seed + phase7.seed_offset`), so no existing file or number changes. It holds true participants per market and season, and the true direction.
- **True level** is related to clubs with rights only weakly (`phase7.truth.level_club_correlation`). **True direction** goes against the market's region-and-regime comparables in a configured share of markets (`phase7.truth.share_against_comparables`). These are **assumptions about how real markets might behave, chosen to represent the risk Anna named** (that a market can move against its neighbours). The evaluation therefore shows what the scenario would get wrong **if** markets behave this way. It is not evidence about real markets, and the tab says so.
- **Proxies** relate to true participation weakly and inconsistently (`phase7.proxy.*`).
- For the seven markets with data, the truth is the existing person registry; nothing new is generated for them.

## 6. The evaluation (whitelisted summaries only)
- **Coverage:** the share of dark markets whose true participants (latest season) fall inside the scenario range.
- **Direction error:** the share of dark markets whose scenario direction is not the true direction ("mixed" counts as not matching).
- **Proxy agreement:** how often proxy direction matches true direction.
- **Reported as they come out.** There is no pass threshold, because a good result is not the goal: the result is the evidence for or against publishing a number. A dbt test only checks that the summary exists and that its counts add up.

## Consequences
- Status, direction and scenario are separate models with separate share models (step 4). The scenario model reads no evaluation and no truth, and `check_eval_isolation` enforces this.
- If Anna changes a rule after seeing the evaluation, that is a new ADR that names the evaluation it saw, not an edit to this one.
