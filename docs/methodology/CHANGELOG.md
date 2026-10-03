# Methodology changelog

> Synthetic data. Every change to how a participant is counted, and every restatement of a published number, is recorded here
> (ADR-007). A methodology change bumps the version and requires a restatement of published headline KPIs.

## v2.0: 2026-10-03

> **Approved by Anna on 2026-10-03.** The fan-acquisition rework adds a second memo, [Flag as fan acquisition](flag-as-fan-acquisition.md) (skeleton with DRAFT markers; her prose), and the fan KPIs.
> A fresh **v1.1 baseline for 2021 to 2025 was published first** on the reworked data (snapshots `scorecard_<year>_20261003T0219Z` to `T0243Z`), so the restatement log can show what 2.0 changed. The v2.0 snapshots follow.

**Added, nothing restated.** Four scorecard KPIs, each `introduced_in: 2.0`: `net_new_households` (linked households with no account before their first registration, by cohort year), `incremental_fan_accounts`
(the market-level estimate with its 95% interval as low / high; 2022 onward, where a launched market has a pre-period), `audience_contactable` (registered households a guardian has opted in on at least one channel, December
of the year) and `consent_gap_households` (active households with no opt-in, December). The scorecard goes from 21 to 25 KPIs. The metric catalog also gains the funnel, value, survival, uplift, consent-capture and
market-profile metrics behind the new shares, all `introduced_in: 2.0`. The restatement log against the v1.1 baseline lists the four as `NEW_KPI` (19 KPI-years) and requires no restatement.

- Counting rules C1 to C15 are **unchanged**; no existing KPI changes definition.
- Fan results describe **households linked to a fan account** under the restricted-zone policy (ADR-009); `UNLINKED` means unknown, not non-fan; every account holder is an adult guardian.
- Acquisition is measured at **market level** from staggered launches (ADR-011), always beside the naive count. The audience is published as counts only: nothing linked reaches marketing or media.
- The rework regenerated the synthetic world (15,000 people, markets, staggered launches, a revised fan source). That is a regeneration, not a methodology change: the **earlier v1.0 and v1.1 snapshots in `published/` describe the old world** and are kept as the record.

## v1.1: 2026-10-02

> **Approved by Anna on 2026-10-02.** The v1.0 baseline for 2021 to 2025 was published first (snapshots `scorecard_<year>_20261002T1341Z` to
> `T1347Z`), so the restatement log can show what 1.1 changed. The v1.1 snapshots for 2021 to 2025 were then published
> (`scorecard_<year>_20261002T1444Z` to `T1450Z`, 21 KPI rows each: the 17 original KPIs plus the four new ones). Nothing was restated, and the restatement log was empty. (Afterwards Source D became `Modelled` when ADR-009 was decided, which moved the data-trust KPI `sources_onboarded` from 4 to 5 in every year: the log listed it as `UNKNOWN`, never a restatement, because snapshots record raw row counts for the three registration sources only; see ADR-008. A second set of v1.1 snapshots was then published, `scorecard_<year>_20261002T1501Z` to `T1507Z`, and the log is empty again. The earlier v1.1 snapshots remain in `published/`.)

**Added, nothing restated.** Four KPIs introduced by onboarding Source E (school and recreation program aggregate headcounts), each marked
`introduced_in: 1.1` in the metric catalog: `reported_headcount`, `voluntary_program_headcount`, `combined_reach_low`, `combined_reach_high`.

- Counting rules C1 to C15 are **unchanged**. No existing KPI changes definition (`definition_changed_in` is empty for all of them).
- Aggregate headcounts are **never added to unique participants**. They are a separate fact (`fct_reported_headcount`), guarded by lineage
  (`scripts/check_lineage.py`).
- Combined reach is a **range**: low = participants (low) + reported headcount - maximum possible overlap; high = participants (high) +
  reported headcount. The maximum overlap per country is the smaller of the reported headcount and the resolved youth participants.
- Rules for the aggregate rows: the latest report wins when a program-year is reported twice; girls + boys replaces a stated total that
  disagrees with it; round totals are flagged as probable estimates but kept.
- Small programs are small cells: a country-year with fewer than 10 reporting programs is suppressed in the exec share.
- **Retention** is defined (see the metric catalog): entry cohort, retained, churn event (the first gap while still youth-eligible), age-out and
  the end of the data as censoring, youth-to-adult tracked separately (the youth-to-adult, transition and driver models were removed later by the fan-acquisition
  rework; the censoring definitions stand). Reported as Kaplan-Meier curves with Greenwood intervals; no scorecard
  KPI changes. Evaluated against the true churn parameters in `eval_retention`.
- The restatement log gains two causes, `NEW_KPI` (listed, never a restatement) and `DEFINITION_CHANGED` (a restatement).

**Evaluated against the synthetic truth** (`eval_headcount_overlap`): the true combined reach was inside the range in every year 2021 to 2025.
The range is wide (about 1,800 to 2,600) because the overlap bound is deliberately conservative; the true overlap was 150 to 200.

## Data: fan-acquisition rework, 2026-10-02 (no version change)

The generator changed upstream (rework step 3): 15,000 people instead of 6,000, synthetic markets with a staggered programme rollout (registrations in a market start only after
its launch year; some markets never launch), and a revised Source D (fan accounts, consent events, engagement events and transactions). The counting rules and every KPI
definition are unchanged. Every participation number moved, so this is `NEW_SOURCE_DATA`, not a methodology change: the restatement log shows 88 changed KPI rows across 19 KPIs,
59 of them requiring a restatement (2025 unique participants 2,837 to 8,959). It is Example 4 in [restatement_demo.md](../reports/restatement_demo.md). The published snapshots
(v1.0 and v1.1) were **not** reissued yet: methodology v2.0 (rework step 12) publishes on the new data and records the `METHODOLOGY_CHANGE`.

## Data window: 2026-10-01 (no version change)

The observation window was extended from 2023 to 2025 to 2021 to 2025, configured in one place (`seasons.first_observed_year`). 2021 is now the
censored year (new, returning and reactivated are not defined for it); 2023 is no longer censored. This is new source data, not a methodology
change: it is recorded as Example 2 in [restatement_demo.md](../reports/restatement_demo.md) (41 KPIs changed, 23 requiring restatement).

## v1.0: 2026-10-01

**Initial methodology.** Rules C1 to C15 as defined in [ADR-005](../decisions/ADR-005-counting-rules.md):

- A participant is a resolved person with at least one valid registration in the calendar year; exact duplicates are not valid; records
  with an impossible date of birth count.
- US spring and fall roll up into the participation year; a separate US seasonal view is never blended with annual sources.
- A person in two leagues is counted once (globally and in each organization); a person in two countries once globally, in the country of
  their most recent registration in the additive view and in each country in the presence view.
- Age is age on December 31; youth is 17 or under; sex is registration-reported and `U` is its own group.
- New / returning / reactivated are defined against the prior year; the first data year is censored (2023 when v1.0 was written; 2021 since the window was extended).
- Counts are registered participants in onboarded sources, not total participation, and not attendance.

**Published snapshots.** `scorecard_2025_20261002T025126Z`: 2025 unique participants 3,962 (identity bounds 3,953 to 3,965).

**Restatements.** None. (A recorded demonstration of the process is in [restatement_demo.md](../reports/restatement_demo.md); it was not a
real restatement.)
