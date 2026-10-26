# Italy onboarding experiment (Phase 7, step 8)

> **Generated** by `scripts/p7_italy_experiment.py` (`make p7-italy-experiment`). SYNTHETIC. Run on a **copy** of the warehouse; the published
> warehouse and the published tab keep Italy dark ([ADR-030](../decisions/ADR-030-minimum-return-path-and-walkthroughs.md)).

A synthetic first minimum return for Italy's 2025 season (15 rows: region x age band) landed in a copy of the warehouse. It was checked against the
minimum-return template with the same validator as every contract, and the global-outlook models were rebuilt on the copy.

**Template checks:** 10 of 10 passed.

| | Before (published) | After (copy) |
|---|---|---|
| Status | DARK | PARTIAL |
| Why | no participation source and no proxy signal | minimum return received for the latest season (counts only): no counting grade or like-for-like direction yet |
| Participation source | none | GMP_MINIMUM_RETURN |
| Participation direction | NOT_MEASURED | NOT_DETECTABLE |
| Planning scenario | 29 to 79 players, FLAT | none (the market now has data) |
| Board | Next, a first season of counts: not yet met | Next, a first season of counts: met |
| Priority (feasibility, readiness, score, rank) | 1, 1, 3, 16 | 4, 1, 6, 7 |
| Markets measured / partial / proxy-only / dark | 5 / 2 / 9 / 6 | 5 / 3 / 9 / 5 |

## What the first return says against the planning scenario

The return reports **396 players**. The planning scenario Italy had was **29 to 79** (from the per-club rates of Austria, Germany and Spain
times Italy's clubs with rights). The answer key's true count is **396**: the return matches it, and the scenario
missed it by a factor of about 5.
One season of counts is enough to leave the scenario behind. It is not enough for a counting grade or a direction: those need a second season and
organization-level filings (ADR-025).

## What the experiment does not show

- A real federation's return would carry its own errors. This one is built to pass every check, so the walkthrough shows the path, not the friction.
- Italy's board milestone is a first season of counts: not yet met in the published build, met on the copy.
