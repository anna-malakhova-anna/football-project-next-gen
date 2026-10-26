# Onboarding log: Italy, minimum return (Phase 7 walkthrough)

> Synthetic project. Roles are fictional. Process: [onboard-a-source.md](onboard-a-source.md) v1.3. Decisions: [ADR-030](../decisions/ADR-030-minimum-return-path-and-walkthroughs.md).
> **Italy is dark in the published build.** The stages marked *experiment* ran on a copy of the warehouse ([report](../reports/p7_italy_experiment.md)).

**Market:** Italy, new to the NFL Global Markets Program in 2026 (two anonymous clubs hold rights). **Partner:** the national flag federation (assumed to exist; how to reach it is a question for the international growth lead). **Source:** the minimum return (`contracts/templates/GMP_MINIMUM_RETURN.yml`).

## Stage log

| Stage | State | Evidence |
|---|---|---|
| Discovery | done, 2026-10-26 | this log |
| Profiling | experiment | the experiment report: the return as landed |
| Contracted | ready | the template contract, to be copied to `contracts/GMP_MINIMUM_RETURN_IT.yml` when the federation agrees |
| Staged | experiment | `stg_gmp_minimum_return` on the copy: all template checks pass |
| Modelled | experiment | `mart_gmp_market_status` on the copy: Italy reads Partial |
| Production | not started | waits for a real return |

## Discovery (2026-10-26)

- **Purpose:** move Italy from dark to readable. First give it a status (Partial) from one season of counts. Then, with a second season and club-level filing, a counting grade and a direction.
- **Key decision recorded before any data, so the data cannot argue us out of it:** Italy is asked for the **minimum return only**: counts of teams and players by region, age band and sex. It is **never** asked for player-level records. The minimum return holds no individual and no consent field, so no child's personal data leaves Italy.
- **Legal basis (design assumption, not legal advice):** EU GDPR is assumed to apply (`legal_regime` EU_GDPR, unverified). Questions for the privacy lead:
  - Is an aggregate return by region and age band outside personal data for small regions?
  - Does any small cell need suppression before it is shared?
- **What it will not do on day one:** a single season gives no counting grade (that needs club-level filings and timeliness) and no direction (that needs a like-for-like pair). The status will say so.

## Experiment (2026-10-26, on a copy)

A synthetic first return for the latest season landed in a copy of the warehouse (`make p7-italy-experiment`). It passed every template check. Italy moved from Dark to Partial, its planning scenario was retired, and its draft priority rose because feasibility went from 1 to 4. The return's total sits far above the scenario's range. Numbers are in the generated report.
