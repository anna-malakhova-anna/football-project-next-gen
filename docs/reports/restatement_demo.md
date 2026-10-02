# Restatement demonstrations

> Three recorded runs of the publish and restatement process (ADR-007): **(1)** one steward decision (`IDENTITY_CHANGE`), **(2)** new source
> data from extending the observation window (`NEW_SOURCE_DATA`), and **(3)** a methodology version bump (`METHODOLOGY_CHANGE`, added when
> methodology v1.1 is published). All data is synthetic; none of these is a real restatement.

---

## Example 1: one steward decision (`IDENTITY_CHANGE`)

> Synthetic data. This is a recorded run of the publish and restatement process (ADR-007), not a real restatement. The
> steward decision is a **demo**: `decided_by = DEMO_STEWARD`. The example was picked using the ground truth so that the
> decision is a correct one; a real steward would reach it by looking at the two records.

### 1. Publish 2025

`make publish YEAR=2025` ran every test (dbt, pytest, the eval-isolation check and the share-policy check), then wrote
`published/scorecard_2025_20261002T025126Z.parquet`: 17 KPI rows for 2025 with

| Context stored with the snapshot | Value |
|---|---|
| methodology version | 1.0 |
| git commit | `4d734b42` (working tree dirty: uncommitted Phase 3 work) |
| raw rows: US / CA / INTL | 10,605 / 2,014 / 1,712 |
| identity fingerprint (registration -> participant) | `58ba99159507...` |

2025 unique participants published: **3,962** (identity bounds 3,953 to 3,965).

### 2. One data steward decision

Two registrations of the same child were kept apart because the first name was mistyped (`Keff` for `Jeff`) and the household
guard blocks "same contact, different first name" (ADR-003). Same date of birth, same guardian email and phone, same year. The
steward confirms them as one person: one row in `review_decisions` (`MATCH`). Then:

```
cd dbt
uv run dbt seed --profiles-dir . --select review_decisions
uv run dbt run  --profiles-dir . --select identity marts evaluation facts measurement shares
```

### 3. The restatement log catches it

`measurement.mart_restatement_log` compares the rebuilt scorecard with the latest published snapshot:

| Year | KPI | Published | Now | Change | Relative | Likely cause | Headline KPI | Restatement required |
|---|---|---|---|---|---|---|---|---|
| 2025 | `girls_share_of_youth` | 0.4578 | 0.4579 | 0.0001 | +0.022% | IDENTITY_CHANGE | yes | no |
| 2025 | `multi_org_participants` | 288 | 289 | 1 | +0.347% | IDENTITY_CHANGE | yes | no |
| 2025 | `new_participants` | 1,699 | 1,698 | -1 | -0.059% | IDENTITY_CHANGE | yes | no |
| 2025 | `registrations_per_participant` | 1.416 | 1.4163 | 0.0003 | +0.021% | IDENTITY_CHANGE | yes | no |
| 2025 | `unique_participants` | 3,962 | 3,961 | -1 | -0.025% | IDENTITY_CHANGE | yes | no |
| 2025 | `identity_range_pct` | 0.003 | 0.0033 | 0.0002 | +8.251% | IDENTITY_CHANGE | no | no |
| 2025 | `open_review_items` | 61 | 62 | 1 | +1.639% | IDENTITY_CHANGE | no | no |
| 2025 | `pct_participants_high_confidence` | 0.9929 | 0.9927 | -0.0002 | -0.025% | IDENTITY_CHANGE | no | no |

Every change has the cause `IDENTITY_CHANGE`: the raw row counts and the methodology version are unchanged, only the
registration-to-participant assignment differs. The headline number moved by one person (-0.025%). Under ADR-007 a headline
KPI needs a restatement only above a 1% relative change (a percentage point for rates) or on any methodology change, so
**no restatement is required**: the change is logged and will appear in the next snapshot. The data-trust KPIs
(`open_review_items`, `identity_range_pct`, `pct_participants_high_confidence`) moved too; they are listed but never trigger one.

For the record, the synthetic truth for 2025 is 3,961 participants, so this decision moved the point estimate from 3,962 to
3,961. That is a property of this data (the decision was correct), not evidence that every steward decision improves the count.

### 4. Reset

The demo decision was removed afterwards (`review_decisions` is header-only again) and the models rebuilt, so the log is empty
and the scorecard matches the published snapshot.


---

## Example 2: the observation window grows (`NEW_SOURCE_DATA`)

Phase 4 extended the data from 2023-2025 to **2021-2025** (a configured `first_observed_year`; the first year, 2021, is now the left-censored
one). The 2023, 2024 and 2025 scorecards had already been published on the original window:

| Snapshot | Published raw rows (US / CA / INTL) |
|---|---|
| `scorecard_2023_20261002T030416Z` | 10,605 / 2,014 / 1,712 |
| `scorecard_2024_20261002T030507Z` | 10,605 / 2,014 / 1,712 |
| `scorecard_2025_20261002T025126Z` | 10,605 / 2,014 / 1,712 |

After regenerating and rebuilding, the raw tables hold **12,929 / 2,522 / 2,149** rows. `mart_restatement_log` compares the rebuilt
scorecard with those snapshots and finds **41 changed KPIs**, every one with the cause **`NEW_SOURCE_DATA`**: the raw row counts differ, and the methodology
version is unchanged. Of those, 29 are headline KPIs and **23 exceed ADR-007's threshold** (more than 1% relative, or a percentage point for
rates), so a restatement is required.

| Year | KPI | Published (3-year data) | Now (5-year data) | Relative change | Likely cause | Restatement required |
|---|---|---|---|---|---|---|
| 2023 | `girls_share_of_youth` | 0.4025 | 0.4281 | +6.4% | NEW_SOURCE_DATA | **yes** |
| 2023 | `international_participants` | 951 | 915 | -3.8% | NEW_SOURCE_DATA | **yes** |
| 2023 | `multi_org_participants` | 171 | 152 | -11.1% | NEW_SOURCE_DATA | **yes** |
| 2023 | `new_participants` | n/a | 945 |  | NEW_SOURCE_DATA | **yes** |
| 2023 | `reactivated_participants` | n/a | 1 |  | NEW_SOURCE_DATA | **yes** |
| 2023 | `registrations_per_participant` | 1.4308 | 1.4064 | -1.7% | NEW_SOURCE_DATA | **yes** |
| 2023 | `retention_rate` | n/a | 0.6566 |  | NEW_SOURCE_DATA | n/a (was not defined) |
| 2023 | `returning_participants` | n/a | 1,566 |  | NEW_SOURCE_DATA | **yes** |
| 2023 | `unique_participants` | 2,639 | 2,512 | -4.8% | NEW_SOURCE_DATA | **yes** |
| 2023 | `youth_girls_participants` | 956 | 953 | -0.3% | NEW_SOURCE_DATA | no |
| 2024 | `girls_share_of_youth` | 0.428 | 0.4376 | +2.2% | NEW_SOURCE_DATA | no |
| 2024 | `international_participants` | 1,205 | 963 | -20.1% | NEW_SOURCE_DATA | **yes** |
| 2024 | `multi_org_participants` | 224 | 148 | -33.9% | NEW_SOURCE_DATA | **yes** |
| 2024 | `new_participants` | 1,664 | 832 | -50.0% | NEW_SOURCE_DATA | **yes** |
| 2024 | `registrations_per_participant` | 1.4106 | 1.3968 | -1.0% | NEW_SOURCE_DATA | no |
| 2024 | `retention_rate` | 0.6393 | 0.6851 | +7.2% | NEW_SOURCE_DATA | **yes** |
| 2024 | `returning_participants` | 1,687 | 1,721 | +2.0% | NEW_SOURCE_DATA | **yes** |
| 2024 | `unique_participants` | 3,351 | 2,553 | -23.8% | NEW_SOURCE_DATA | **yes** |
| 2024 | `youth_girls_participants` | 1,287 | 999 | -22.4% | NEW_SOURCE_DATA | **yes** |
| 2025 | `girls_share_of_youth` | 0.4578 | 0.4533 | -1.0% | NEW_SOURCE_DATA | no |
| 2025 | `international_participants` | 1,495 | 1,086 | -27.4% | NEW_SOURCE_DATA | **yes** |
| 2025 | `multi_org_participants` | 288 | 214 | -25.7% | NEW_SOURCE_DATA | **yes** |
| 2025 | `new_participants` | 1,699 | 1,051 | -38.1% | NEW_SOURCE_DATA | **yes** |
| 2025 | `reactivated_participants` | 0 | 1 |  | NEW_SOURCE_DATA | **yes** |
| 2025 | `registrations_per_participant` | 1.416 | 1.4068 | -0.6% | NEW_SOURCE_DATA | no |
| 2025 | `retention_rate` | 0.6753 | 0.6992 | +3.5% | NEW_SOURCE_DATA | **yes** |
| 2025 | `returning_participants` | 2,263 | 1,785 | -21.1% | NEW_SOURCE_DATA | **yes** |
| 2025 | `unique_participants` | 3,962 | 2,837 | -28.4% | NEW_SOURCE_DATA | **yes** |
| 2025 | `youth_girls_participants` | 1,637 | 1,169 | -28.6% | NEW_SOURCE_DATA | **yes** |

Two things worth reading in this table:

- **2023 gains status.** In the old data 2023 was the left-censored year, so new, returning and retention were *not defined*. With 2021 and 2022
  in the data, 2023 now has real values for them. That is a legitimate change caused by new data, and it is why the log lists it.
- **The numbers move a lot, and not only because of the extra years.** Regenerating the synthetic population changed the earlier years as well
  (the random stream shifted, and the first-season weights are spread over five years instead of three). In a real restatement the cause would still be
  `NEW_SOURCE_DATA`, but a reviewer would want to separate "new rows" from "revised rows"; the log does not, and ADR-007 lists that as a limit.

**What was done.** The change is a restatement of three published years. The three old snapshots stay in `published/` (they are immutable) and a new
baseline for 2021-2025 is published on the five-year data; `docs/methodology/CHANGELOG.md` records it.

## Example 3: a methodology bump that only adds KPIs (`NEW_KPI`)

Methodology v1.1 (approved 2026-10-02) adds four KPIs from the school and recreation program headcounts (Source E):
`reported_headcount`, `voluntary_program_headcount`, `combined_reach_low`, `combined_reach_high`. The counting rules C1 to C15 and every existing
KPI definition are unchanged. The v1.0 baseline for 2021 to 2025 was published first (five snapshots, each from a clean commit), then
`methodology_version` was bumped to 1.1 and the scorecard rebuilt.

The restatement log, compared with the latest published snapshot of each year:

| Cause | Rows | Distinct KPIs | Restatement required |
|---|---|---|---|
| `NEW_KPI` | 20 (4 KPIs x 5 years) | 4 | **no** |
| any other cause | 0 | 0 | 0 |

Every one of the 17 v1.0 KPIs is identical to its published value in all five years: nothing was restated. The log lists the additions so they are
visible rather than silent (2025: reported headcount 8,441; combined reach 8,690 to 11,285, a range because aggregates cannot be matched to people).

**Why this matters.** Before this change the log could only see KPIs that already existed, so a new KPI would have been invisible and a changed
definition would have looked like an ordinary methodology change. `introduced_in` and `definition_changed_in` in the metric catalog now let the
log say `NEW_KPI` (listed, never a restatement) or `DEFINITION_CHANGED` (a restatement). The v1.1 snapshots for 2021 to 2025 have since been published (21 KPI rows each), and the log was empty again. It later gained one line per year when Source D became `Modelled` (the data-trust KPI `sources_onboarded` went from 4 to 5, cause `UNKNOWN`, no restatement required): a small live example of the gap ADR-008 describes, since snapshots do not record row counts for the school and fan sources or the registry status.
