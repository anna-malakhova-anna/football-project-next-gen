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
