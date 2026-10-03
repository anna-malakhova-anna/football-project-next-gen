# Rework inventory: Phase 4 against the fan-acquisition rework

> Written for `rework-fan-acquisition-spec.md` section 0. All data is synthetic. **Awaiting Anna's review before any change is made.** Nothing below has been changed yet.

## Baseline

`make all-phases` (the supported full build; `make phase3` is an alias for it) was run from the committed tree: **exit 0**, 292 dbt tests passing (1 existing warning),
149 pytest tests, and the four build checks (ground-truth isolation, aggregate lineage, share policy, participant-ID stability) all OK. Published: v1.0 baseline and two
v1.1 snapshot sets for 2021 to 2025 (`published/`), the latest set recorded with Source D `Modelled`. The restatement log is empty. Last commit: `f988633`.

## Status and disposition of every Phase 4 component

| Phase 4 component | Build status | Disposition under the rework | What that means in this repo |
|---|---|---|---|
| Data window extension (2021 to 2025) | **done** | **Keep** | `seasons.first_observed_year`, `observation_window` seed, no-literal-years test |
| Playbook, contracts, contract validation | **done** (playbook v1.3, 6 contracts, validator with `component`) | **Keep** | Fan contracts are rewritten for the new files (spec 3.4); consent and transaction rules at `ERROR` |
| Source E (school headcounts) | **done** (`Modelled`; fact, mart, shares, eval, lineage guard, contract, log) | **Demote to stretch**: keep it, remove it from the site's main pages and the exec report headline | Remove the combined-reach chart from the Participation page and the overview headline; remove the school section from `render_report.py` and the README results row. Code, data, tests and the playbook log stay |
| Methodology v1.1 (headcounts) | **done and published** (two snapshot sets) | **Keep** (Source E is done) | v1.1 stays in force; v2.0 (spec section 9) comes after it |
| Retention: cohorts and Kaplan-Meier | **done** (`retention_spells`, `mart_retention_cohorts`, `mart_retention_survival`, `eval_retention`, `eval_retention_checks`, shares, site charts) | **Keep**, repositioned as an input to fan value | Stays on the Participation page; becomes an input to the "child churn vs fan lapse" analysis (5.4) |
| Retention transitions and drivers | **done** (`mart_retention_transitions`, `mart_retention_drivers`, `mart_youth_to_adult`) | **Cut** | Remove the three models, their yml entries, the `retention_marts_are_consistent` assertions for them, the catalog entries (`one_year_retention_rate`, `youth_to_adult_rate`) and the lines in `print_retention.py`. None is on the site |
| Source D (fan feed) as specified in Phase 4 | **done** (accounts + one event stream with purchase events, contracts, staging, truth, defects) | **Replace** with spec section 3; extend, do not rewrite | Keep the generator skeleton, causal structure, defects and linkage. Add `acquisition_source`, holder `birth_year`, a consent-events file, a transactions file, new event types, duplicate accounts, the staggered rollout |
| Household linkage and ADR-009 | **done**, decided by Anna (restricted zone, phone fallback kept, never to marketing) | **Keep**, extend | A household may link to several accounts; `market_id` added; ADR-009's "never to marketing" is **revisited by spec section 7** (see question 3) |
| Fan DiD (household engagement uplift) | **done** (matched DiD, event study, summary, `eval_fan_effect`, ADR-010) | **Keep**, repositioned as "value uplift among existing fans" | Scope it to `EXISTING_ACTIVE` and `LAPSED_*` households, split by spend category and engagement type |
| Results site | **done** (6 pages, 13 charts, build rules enforced) | **Restructure** | New page order with Fan acquisition first (spec 8); the build checks stay |
| Not in the spec's table: README, ADR-008/009/010, demo script skeleton, CI workflow, `make all-phases` | done | Rewrite or extend in step 12 | README headline and results table, demo script order, ADR-008 scope note |

## What the generator change does to everything already published

Spec step 3 changes the generator upstream (registrations in a market start only after its launch year; revised Source D). That is not confined to fan data:

- **Every participation number moves.** Registrations, participants, new/returning, retention, identity evaluation, the school overlap truth and every published KPI change.
  All three published snapshot sets (v1.0, v1.1, v1.1 again) will differ from the rebuilt numbers for all five years.
- **The restatement is real, and large.** It is `NEW_SOURCE_DATA` in the log's terms (the generated source rows change), so most headline KPIs would be flagged for restatement
  (this is Example 2 again, at a different scale). Spec section 9 then bumps to v2.0, which adds a `METHODOLOGY_CHANGE` restatement on top.
- **Hard-coded expected values will break and need updating:** the README results table, `docs/phase2_results.md`, `docs/eval/*.csv`, the methodology memo's numbers, ADR-006 and
  ADR-010 results, the restatement demo (Examples 1 to 3), `tests/test_render_report.py` (it asserts 2025 values), and the site's headline.
- **ADR-010's fan-effect numbers** (+45.6% naive, +17.2% matched, truth +14.7%) will change, because the households, selection and enrollment timing change.

## Questions and risks for Anna before step 2

1. **Population size is too small for market-level incrementality.** 6,000 people are about 5,000 households; spread over about 40 synthetic markets that is roughly 125
   households per market, and the United States, Canada and eight other countries are not equally sized. Net-new fan accounts per launch market per year would be a handful, so
   a stacked market-level DiD with an event study from -2 to +3 would be mostly noise, and `eval_acquisition` could not tell a good design from luck. **Proposal:** raise the
   generated population (for example to 30,000 to 40,000 people) as part of step 3, accept a longer build (the full build is 2.5 minutes today; the fan stream alone is most of it),
   and re-measure the CI budget. **Decision needed:** keep 6,000 and accept a noisy incrementality result, or scale up.
2. **What does `household_population` mean?** The spec gives each market a synthetic household population (the denominator for "new fan accounts per 1,000 households"). The generator
   creates non-participant fan households only. **Proposal:** treat `household_population` as the synthetic universe of households in the market, and have the generator create
   organic fan accounts at a configured penetration rate of it (so the rate per 1,000 is meaningful and the staggered rollout adds a lift on top). Participant households are drawn
   from that universe. Say so in ADR-011 and in the seed notes.
3. **Spec section 7 reverses part of ADR-009.** ADR-009 (decided by Anna, 2026-10-02) says nothing linked reaches `share_marketing`, even with both-sides consent. Spec section 7
   says `share_marketing` gets the addressable audience **list** (guardian contact, channel, fan status, RFM segment) built from linked fan accounts and consent history. That is a
   different position, with its own consent question. The spec does keep the safeguards (only opted-in channels as of the run date, guardians only, never `UNLINKED` households,
   never minors). **Decision needed:** confirm the rework supersedes the "never" position and that ADR-009 gets a dated amendment (I would write it and leave the decision marker for you),
   or keep "never" and drop the marketing list from step 11 (the addressable-audience counts in the exec share would stay).
4. **`as of` dates.** The funnel's "active (engaged in the last 90 days)" and "contactable" need an as-of date. **Proposal:** measure them at the end of each registration cohort year
   (so the funnel is a time series by cohort), and the marketing list at the run date. Windows come from `fan_params.csv` as the spec requires.
5. **Markets outside the US and Canada.** Registrations from other countries carry no postal code, so they map to markets by country (one or two per country, as the spec says).
   The market-level incrementality will therefore be mostly US and Canadian markets; INTL markets would be too few households to include. **Proposal:** run incrementality on markets
   with at least `k_min` participant households and say which markets were excluded.
6. **Holder `birth_year` on accounts (3.1).** It is an adult-only field used for the guardians-only rule, and it adds a quasi-identifier to the accounts file. **Proposal:** carry it,
   tag it `pii: quasi`, keep it out of every share, and use it only for the guardian check.
7. **Cut items still in the published snapshots?** The cut retention models feed no KPI or share, so removing them changes no published number.
8. **Source E and v2.0.** Because Source E is done, v1.1 stays and v2.0 builds on it (it does not fold v1.1 in). The new fan KPIs are added with `introduced_in: 2.0`.

## What step 2 will do once you say go (nothing before)

Remove the three cut retention models and everything that references them (listed above); demote Source E on the site and in the exec report headline only (its code stays); rebuild
with `make all-phases` and confirm green. No generator change happens in step 2.

## Anna's decisions (2026-10-02), recorded before step 3

1. **Population: scale up to 15,000 people** (from 6,000), so market-level incrementality has enough households per market.
2. **Marketing: "never" stands.** ADR-009's position is kept: nothing linked reaches `share_marketing` or `share_media`. The rework's marketing audience **list** (spec section 7) is
   therefore **dropped** from step 11. The addressable-audience and consent-gap **counts** stay (they are aggregates in `share_exec`), and the guardians-only rule still applies to every
   fan output. ADR-009 needs no amendment.
3. **Market denominators: yes.** `household_population` is the market's synthetic household universe; organic fan accounts are created at a configured rate of it.
4. **As-of dates: yes.** Funnel stages (active, contactable, retained) are measured at the end of each registration cohort year; any run-date view uses the run date; windows come from `fan_params.csv`.

## Step 3 status (2026-10-02)

Done and green (`make all-phases`: 296 dbt tests, 154 pytest tests, the four build checks). What changed:
- **Markets:** `generator/markets.py` builds 46 synthetic markets (28 US, 12 CA, one per international country) with launch years (10 launch in 2021, 8 in 2022, 7 in 2023, 5 in 2024, 10 never,
  among the 40 US and CA markets; international launches are listed), a team-market flag and a household population. Seeds `market_map.csv` and `market_geo_map.csv`; `market_id` is on
  `fct_registration`, `fct_participant_year`, `int_household_profile` and fan accounts.
- **Population and rollout:** 15,000 people; nobody registers before their market's launch year; never-launched markets have no registrants.
- **Revised Source D:** accounts (with `acquisition_source` and holder `birth_year`), consent events, engagement events (with `fantasy_activity` and `flag_content_view`), transactions, duplicate
  accounts, lapse and reactivation, true acquisition lift. New truth: `fan_market_truth`, `fan_consent_truth`, `fan_effect_truth`. Consent and transactions are loaded to raw; their contracts, staging and
  models are step 4.
- **Expected values updated:** the README table, `docs/phase2_results.md`, `docs/identity_resolution.md`, the generated memo numbers and report, ADR notes, the CHANGELOG, restatement Example 4.
- **Restatement captured:** Example 4 (88 rows, 59 requiring restatement; 2025 unique participants 2,837 to 8,959). No snapshots reissued yet (v2.0, step 12).

Findings to put in front of Anna:
1. **Nine twin false merges at scale** (final matcher, international returns). Reported, not tuned (ADR-008, `docs/identity_resolution.md`). A label-free fix is available; it is Anna's call.
2. **`eval_fan_checks` thresholds were restated** from "naive at least 2x the truth, matched error under a fifth of the naive" to orderings (naive overstates by at least 25%, matched error under half the
   naive error, matched within 30% of the truth), because the new generator weakens selection among account holders. The truth also became exact (an oracle table).
3. **Pytest now takes about 5 minutes** (it was 80 seconds); with the build that is close to CI's 10-minute budget. Step 13 will cut it (smaller test populations, fewer full generations).

## Step 4 and 5 status (2026-10-02)

Step 4 is committed (`a52db22`): fan contracts with ERROR severities, staging, the account collapse, `dim_fan_account`, the consent SCD2, engagement and transaction facts; the DQ log now finds all 66
injected out-of-order consent events, 971 of 1,000 duplicate accounts (international phones are not normalized) and every orphan refund.

Step 5 (built, awaiting Anna): `link_household_fan_account` now links to the **canonical** fan account (duplicates collapsed first); `fct_household_engagement_month` and the matched DiD run on the canonical
engagement fact; the timeline covers every household; `fct_household_fan_status` assigns the spec's statuses from `fan_params` windows, plus two additions the spec's table leaves open (see the questions
in the summary): `EXISTING_COOLING` (engaged 91 to 180 days before, none in the last 90) and `INSUFFICIENT_HISTORY` (the lapsed window is not observable, or the account is younger than it). `make fan-status`
prints the distribution and the comparison with the truth. The fandom estimates were re-run on the collapsed accounts: naive +26.1%, matched +20.3%, truth +18.0%.

## Step 6 and 7 status (2026-10-02)

Step 6 is committed (`e125e69`): the funnel (`mart_fan_funnel`, 13,043 participant households: 37% linked, then 71% contactable, 83% active, 77% monetized; net-new fans monetize far less than
existing fans, 45 to 48% against 91 to 93%).

Step 7 (built, awaiting Anna): `mart_acquisition_incrementality` (stacked, cohort-specific group-time effects against not-yet-treated and never-treated markets, no pooled two-way fixed effects),
`mart_acquisition_event_study` (-2 to +3), `mart_acquisition_summary`, `eval_acquisition` and its event study, `fan_incrementality_is_sound` (comparison markets never already treated). `make acquisition`
prints it. Result on the synthetic data: the programme added **988 new fan accounts (range 622 to 1,354)** in launch cohorts 2022 to 2024, years 0 to +3; the generator's truth is **1,111** (inside the range);
the naive claim, linked households whose account was created after registering, is 939 observed (it sees only linked households, so it lands near the truth by cancellation) and **2,543 when scaled by the
link rate (2.3x the truth)**. The pre-period is flat and every truth lies inside its interval.

Two generator corrections made on the way, both found by checking the estimate against the truth rather than by tuning the analysis: (1) a participant household's existing account is opened before the
data starts (it used to bunch up just before each market launched, inflating the base year); (2) the fan-effect truth is now computed over the households and months each estimator averages over.
Consequence: in this generator the NAIVE fan-engagement estimate (+17.5%) lands on its own truth (+17.7%) by cancellation (selection pushes it up, a low-baseline net-new mix pulls it down), so the
spec's expected "naive badly inflated" does NOT hold for engagement; it does hold for acquisition once scaled. The checks were restated accordingly and the unmatched gap is reported (+9.8% before
registration, +33% after) so the selection is visible. This is a finding for Anna.

## Step 8 status (2026-10-02)

Built: `mart_fan_value_uplift` (the Phase 4 matched DiD scoped to existing and lapsed fans, by engagement type and spend category, spend net of refunds in synthetic currency), `mart_fan_survival` (Kaplan-Meier of fan
activeness through the new `kaplan_meier` macro: months from origin to the first lapse, six quiet months, censored at the end of the data), `mart_fan_ltv` (36-month value = net spend per active month x the
area under the survival curve, range from the survival interval), `mart_fan_activeness` (active, at risk, lapsed, new and the transitions by month), `int_fan_rfm_scores` and `mart_fan_rfm` (NTILE(5) quintiles
over the trailing 12 months, named segments from `rfm_segment_map`), and `mart_fan_lapse_after_child_churn` (association only, person-time split at the churn month, lapse placed by its onset).
Evaluation: `eval_fan_value_uplift` (the exact expected effect per outcome from the oracle, which now records expected net spend by category), `eval_fan_lapse_after_child_churn`, `eval_fan_value_checks`.
Results: existing fans' net-spend total +1.13 per account-month against a truth of +1.33 (inside the interval; ticket and subscription inside too); lapsed fans' events +0.18 against +0.21 (inside);
the existing-fans engagement estimate (+0.211) sits above its truth (+0.182) with the truth just outside the interval, reported and not tuned; fans lapse 1.71 times faster after the child stops (built-in
hazard multiplier 1.5, an association by construction); net-new flag-prompt fans survive less (58% at 36 months) than existing fans (72%) and are less often Champions (19% against 31%).
Caveats: percentages are unstable for LAPSED households (the counterfactual is near zero), so the per-month difference is the headline there; content_views and flag_content_views move oppositely because of a
relabel (all_content_views is the sum); the LTV range reflects survival uncertainty only (spend per active month is treated as known).

## Step 9 status (2026-10-02)

Built: `int_fan_account_month_state` (activeness state per account and month end, now shared), `int_household_audience_month`, `mart_addressable_audience` (contactable participant households by channel over time, the consent gap
and its illustrative value in synthetic currency), `mart_consent_capture` (opt-in rate by capture point, by source system and by partner for flag-prompt accounts, partners under k_min flagged unreliable),
`mart_opt_out_after_contact` (opt-outs per 1,000 opted-in account-months against engagement volume, a proxy for contact), `eval_consent_history` and `eval_consent_checks`, and the `fan_audience_is_sound` test. Per the
decision that nothing linked reaches marketing, there is no audience LIST; these are counts. Result in December 2025: 13,043 participant households, 4,665 linked, 3,511 contactable (75% of linked), 803 active
households with no channel opted in (a consent gap valued at 96,360 synthetic currency at the median monetized household's spend); flag-prompt consent capture is strongest by email (86%); opt-outs rise from
4 to 16 per 1,000 as monthly engagement rises. Finding: resolving consent by timestamp leaves 58 of 96,660 account-channels wrong, all in the unsafe direction (the history says opt-in, the account opted out); the
out-of-order flag catches 55 of them and 3 look like a legal sequence and cannot be seen from the data. Any contact use must fail closed on flagged accounts; the residue is the limit of timestamp resolution.

## Step 10 status (2026-10-02)

Built: `mart_market_profile` (per market: participation and fan accounts per 1,000 households, net-new rate, link rate, girls' share, consent capture rate, and the quadrant against thresholds from
`market_quadrant_params`, blank = the median) and `mart_household_shape_profile` (adult player vs youth households by years active against fan status and value), with `fan_market_profile_is_sound`.
Result (46 synthetic markets): 15 Retention and engagement play, 8 Program growth opportunity, 3 Acquisition white space, 20 Long-term build (the never-launched markets and the small, thin ones);
thresholds 5.5 participant households and 10.5 fan accounts per 1,000 households.
Two real bugs found by the soundness test and fixed (no change to the random stream): (1) the INTL markets have a blank region, which the seed loads as NULL, so international accounts and registrations
had no market (the lookup compared with an empty string); (2) cross-border movers registered in the new country with a random postal code in the state, which could be a market that had not launched; their
postal code now comes from the market chosen for the move.
Numbers to refresh in step 12 (the README, ADR-009 and ADR-010 still quote earlier runs): fan engagement uplift is now naive +17.5% (0.99x its truth), matched +22.6% (truth +20.5%); phone links are 85.8% precise;
acquisition incremental estimate 1,264 (897 to 1,630) against a truth of 1,111.

## Step 11 status (2026-10-02)

Built, all approved linkage aggregates (counts and rates, small cells suppressed, no identifier): EXEC `share_exec__fan_funnel`, `share_exec__acquisition_incrementality` (the estimate with its interval next to the
naive net-new count), `share_exec__fan_value` (LTV with a range, synthetic currency), `share_exec__addressable_audience` (audience counts and the consent gap by month and group), `share_exec__market_quadrants`
(markets under k_min participant households are rolled up per quadrant, so no small market is published alone); ANALYST `share_analyst__fan_acquisition_event_study` (cells under 3 treated markets suppressed) and
`share_analyst__fan_market_year` (the market-year panel the estimate is built from). `check_share_policy` approves exactly these names for the linkage schema; marketing and media stay at none. 38 metric-catalog
rows added; the suppression singular tests cover the funnel, audience and value shares independently of the macro.
Deviations from the spec, on purpose: NO marketing audience list (ADR-009, "never to marketing", the user's decision) and NO pseudonymized household-month panel for analysts (a household-level table from the
restricted linkage schema would break the aggregates-only rule; the market-year panel serves re-estimation instead).

## Step 12 status (2026-10-02)

Built: the site restructured into Overview, Fan acquisition (first chart: incremental vs naive vs truth), Fan value & activeness, Audience & consent, Participation (with retention), Data trust & governance (identity,
contracts, access, restatements); 25 charts, 42 datasets, every spec compiled and rendered against its data in a Vega check. Four more exec shares were needed for it (`share_exec__fan_rfm`, `fan_survival`,
`fan_value_uplift`, `consent_capture`, each with policy rows, catalog entries and a suppression test). README headline and results table rewritten around the fan question; demo-script skeleton restructured
(talking points still Anna's); ADR-011 written; ADR-008/009/010 refreshed with the final numbers (phone precision 85.8%, naive +17.5%, matched +22.6%); v2.0 fan-acquisition memo skeleton with DRAFT markers.
NOT done, on purpose: the methodology version bump to 2.0, publishing a new 2021 to 2025 baseline and v2.0 snapshots, and the restatement capture. Bumping and publishing are Anna's approval (as for v1.1); the CHANGELOG
records v2.0 as proposed and what the bump would do. The new fan metrics carry `introduced_in: 1.1` until then. The memo's numbers are typed in from the marts (no generator script yet).

## Step 13 status (2026-10-02)

Full local build green: 348 dbt tests, 155 pytest, isolation, lineage, share policy and ID stability all pass. pytest now runs on 4 workers (`pytest-xdist`, `-n 4`; `-n auto` was slower from contention): 5.5 minutes down to about 3.3.
The full `make all-phases` is still about 6 to 8 minutes, so the CI job timeout moved from 10 to 25 minutes (the test asserts at most 25). Not verified: the workflow has never run, because there is no GitHub remote yet; "CI green" is
a local claim until it is pushed.
