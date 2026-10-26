# ADR-024: Global Markets Program reference data, and Panama renamed to Spain without changing a number

- **Status:** Accepted for step 1 of the Phase 7 spec (Global outlook tab), 2026-10-25. Decided by Anna: anonymous clubs, Panama out of the data, a restatement accepted if needed (draw-neutral rename chosen after a first attempt changed the population).
- **Synthetic data.** Every count is generated. The markets and the countries each club holds come from the public NFL Global Markets Program page (read 2026-10-25). **Clubs are anonymous**; no real club name is stored anywhere in the project.

## Context
Phase 7 adds an executive Global outlook tab over the 22 markets of the NFL Global Markets Program, flag football only. It needs the markets, which clubs hold rights where, and the data-protection regime each market is assumed to fall under. The federation returns (`INTL_FED`) carried one country that is not a program market, Panama.

## Decisions
1. **Three reference seeds** (tag `phase7`, tested in `_seeds.yml` and `dbt/tests/gmp_reference_is_consistent.sql`):
   - `gmp_markets`: the 22 markets, a project region (a grouping choice), the assumed legal regime, and whether the page lists the market as new (Italy).
   - `gmp_club_rights`: 86 club-country rows for 32 clubs, labelled "Club 01" to "Club 32" in an order shuffled with the global seed. Clubs with rights per market are counted in SQL, never typed. Two page details are kept as notes, not resolved: one club's "Island of Ireland" is counted as IE (Northern Ireland is UK territory), and one club's Canada row is marked new in the page's table but not in its text.
   - `legal_regime`: 17 regimes, each with the DP6 output port it falls under (`global_eu_uk`, `global_canada`, `global_other`; the US is `domestic_reference` and stays in DP4). **Every row is an assumption for design, `UNVERIFIED`, with no source URL**, until Anna or the privacy lead checks it.
2. **Panama is renamed to Spain** (a program market, Spanish-language, EU). Spain takes Panama's place in every source: federation sheet (`ESP`, "Spain", "España"), the yearly Player ID reissue defect, school district suffix, fan country code, `country_map`, `gender_map`, contracts. Spain uses its own category labels ("Senior Femenino", "Senior Masculino", mapped in `division_map`) and four Spanish club towns.
3. **The rename keeps every random draw identical.** A first attempt (Spanish name locale, 9-digit phones, plain alphabetical sorts) regenerated the whole population: three estimator evaluations missed their answer key and two latent bugs surfaced (see Consequences). Anna chose the draw-neutral rename instead:
   - `generator/draw_order.py`: wherever the generator sorts by country code or by an organization id (`"ES|<club>"`), Spain sorts in Panama's former slot. Used by the population, federation, school and organization-profile generators, and to seed the school name generator.
   - Spain keeps Panama's `es_MX` name locale and 8-digit phone numbers (labelled in config and code as kept for draw stability, not as facts about Spain).
   - The four Spanish club towns were chosen so their club names sort in the same order Panama's did.
4. **Spain's consent jurisdiction is EU** (`age_consent_jurisdiction_map`). This is the one intended change in meaning.

## What changed, measured against the build before the rename
Every audience-facing table (128 in the `share_*`, `evaluation`, `published`, `marts`, `measurement`, `quality` and `phase6` schemas) was snapshotted before the change and compared after a full `make all-phases`:
- **The synthetic population and all ground truth are identical**, except labels (sheet name, district suffix, club towns).
- **No published number changed.** Every changed `public/` file holds the same numbers as before; the changes are "PA" to "ES", "Market 46 (ES)", the EU and default jurisdiction legends, and one row order (a club name sorts differently).
- Spain's 291 participant-years move from DEFAULT to EU in `int_participant_age_tier` (restricted). **No consent permission changes**: under both rule sets every Spanish household is guardian-only with nothing captured. Household ids of Spanish families change, since they hash contact details that now carry +34.
- Below display precision only: match probabilities move in the sixth decimal place (term frequencies over renamed values), with no link, cluster or count change, and the activation funnel's fractional sums move by about 1e-13 (float summing order).
- **No restatement is logged** (ADR-007), because no published figure changed. ADR-022's jurisdiction counts are updated, with the before-and-after counts.

## Consequences
- Labels in generated docs and eval CSVs say Spain; the README results are unchanged.
- **Found by the first attempt, not fixed here (follow-ups):** with a different population, `a_participant_turning_18_carries_no_fan_link` found one youth profile carried into an adult household with a fan link, and `dq_trend_limits_are_consistent` found two organization-seasons whose out-of-control flag disagrees with their limits. Both are latent defects that this seed does not trigger. Separately, three estimator checks (acquisition incrementality, two fan-value intervals) missed the answer key under that population: a finding about how much their coverage depends on the seed, not something to tune (ADR-010, ADR-011).
- The Phase 7 spec's scenario method, status rules and direction rules move to ADR-025.
