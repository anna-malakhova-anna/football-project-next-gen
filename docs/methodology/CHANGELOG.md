# Methodology changelog

> Synthetic data. Every change to how a participant is counted, and every restatement of a published number, is recorded here
> (ADR-007). A methodology change bumps the version and requires a restatement of published headline KPIs.

## v1.0: 2026-10-01

**Initial methodology.** Rules C1 to C15 as defined in [ADR-005](../decisions/ADR-005-counting-rules.md):

- A participant is a resolved person with at least one valid registration in the calendar year; exact duplicates are not valid; records
  with an impossible date of birth count.
- US spring and fall roll up into the participation year; a separate US seasonal view is never blended with annual sources.
- A person in two leagues is counted once (globally and in each organization); a person in two countries once globally, in the country of
  their most recent registration in the additive view and in each country in the presence view.
- Age is age on December 31; youth is 17 or under; sex is registration-reported and `U` is its own group.
- New / returning / reactivated are defined against the prior year; the first data year (2023) is censored.
- Counts are registered participants in onboarded sources, not total participation, and not attendance.

**Published snapshots.** `scorecard_2025_20261002T025126Z`: 2025 unique participants 3,962 (identity bounds 3,953 to 3,965).

**Restatements.** None. (A recorded demonstration of the process is in [restatement_demo.md](../reports/restatement_demo.md); it was not a
real restatement.)
