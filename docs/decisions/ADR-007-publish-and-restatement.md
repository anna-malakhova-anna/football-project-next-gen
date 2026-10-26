# ADR-007: Publish and restatement

> **Numbers in this ADR are from the data at the time it was written** (6,000 people, three then five years). The fan-acquisition rework regenerated the data (15,000 people, synthetic
> markets with a staggered programme rollout), so current figures are in `docs/phase2_results.md`, the README and the results site, and every published snapshot was restated
> (`docs/reports/restatement_demo.md`, Example 4).


- **Status:** Accepted (Phase 3)
- **Context:** An executive number that quietly changes after it was reported destroys trust. Published numbers need to be versioned,
  and a change after publication needs a cause, a threshold and an owner. All data is synthetic.

## Decision

**Publishing.** `make publish YEAR=2025` (`scripts/publish.py`) first runs **every** test: `dbt test` for all phases, `pytest`, the
eval-isolation check and the share-policy check. If any fails it refuses and writes nothing. Otherwise it writes
`published/scorecard_<year>_<UTC timestamp>.parquet` with the year's KPI rows and the context needed to explain a later change:
methodology version, git commit SHA (and whether the working tree was dirty), the row counts of the three raw source tables, and a
fingerprint (md5) of the registration-to-participant assignment. Snapshots are committed and **immutable**: the script refuses to
overwrite one. Warn-level tests (for example the analyst k-anonymity warning) do not block a publish; failing ones do.

**Detecting a change.** `mart_restatement_log` compares the current `mart_kpi_scorecard` with the latest published snapshot of each year
(`loader/load_published.py` loads the committed parquet into `published.scorecard_snapshots`) and lists every KPI whose value changed, with
old value, new value, delta, relative change and a `likely_cause`, decided in this order:

| Cause | Test |
|---|---|
| `DEFINITION_CHANGED` | the methodology version differs and the metric catalog says this KPI's definition changed in a version after the published one (`definition_changed_in`) |
| `METHODOLOGY_CHANGE` | the methodology version differs (the definition did not change) |
| `NEW_KPI` | the KPI is not in the published snapshot of that year. Listed so the addition is visible; it never requires a restatement (v1.1, Phase 4) |
| `SOURCE_REGISTRY_CHANGE` | a KPI counted from the source registry alone (sources known, sources onboarded) moved: a source was added or changed status. Added in Phase 7, when onboarding GMP_PROXY moved sources known from 12 to 13 and the log had called it `IDENTITY_CHANGE` ([ADR-025](ADR-025-global-status-direction-and-scenario.md)) |
| `NEW_SOURCE_DATA` | the raw row counts of the sources differ (new or late files) |
| `IDENTITY_CHANGE` | the registration-to-participant assignment differs (new links, a steward decision, a new run) |
| `UNKNOWN` | none of the above explains it |

An empty log means nothing published has changed.

## Restatement policy

- **Threshold.** A *headline* KPI (north star, growth, reach, depth) must be restated when its value changes by **more than 1%**
  (relative; for rates, more than one percentage point) **or** on any methodology version change. Data-trust KPIs (open review items,
  identity range, DQ failure rate, sources) move legitimately as stewards work; they are logged but never require a restatement.
- **Who approves.** The **Program Insights Lead** (owner of the headline metrics) approves a restatement and the **Data Governance Lead**
  confirms the cause; a methodology change also needs the **Privacy Lead** if it touches what an audience can see. The Flag Football
  Data Lead prepares the change and the explanation. (These are fictional roles in this synthetic project.)
- **How it is recorded.** A reissued number is a **new snapshot** (`make publish`), never an edit. `docs/methodology/CHANGELOG.md`
  records the date, the KPIs and old and new values, the cause, the approvers and the snapshot id. A change below the threshold is
  logged in `mart_restatement_log` and appears in the next snapshot without a reissue.
- **Pre-publication.** Numbers can change freely until a year is published; the rule applies from the first snapshot.

## Demonstration

`docs/reports/restatement_demo.md` records it: publish 2025, apply one steward decision (a first-name typo, `Keff` for `Jeff`, that had
kept two registrations of one child apart), rebuild, and the log lists eight KPIs, all `IDENTITY_CHANGE`: 2025 unique participants
3,962 to 3,961 (-0.025%), new participants -1, multi-organization +1, with the data-trust KPIs moving too. Every change is below the
threshold, so no restatement is required. The demo decision was then removed and the models rebuilt, so the log is empty again.

## Limits

- The snapshot's git SHA is only as meaningful as the commit discipline around `make publish`; the first snapshot here was taken with an
  uncommitted working tree and says so (`git_dirty`).
- The log compares against the **latest** snapshot only; it does not chart the whole history of a number.
- Tests passing is necessary, not sufficient: a wrong but internally consistent methodology would publish.

## Consequences

A published number can always be traced to code, data volumes and a methodology version, and a later change is caught with a probable
reason. The process is light (one script, one model, one policy) and demonstrates the discipline; a production version would add
workflow, sign-off records and notification.
