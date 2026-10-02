# Restatement demonstration

> Synthetic data. This is a recorded run of the publish and restatement process (ADR-007), not a real restatement. The
> steward decision is a **demo**: `decided_by = DEMO_STEWARD`. The example was picked using the ground truth so that the
> decision is a correct one; a real steward would reach it by looking at the two records.

## 1. Publish 2025

`make publish YEAR=2025` ran every test (dbt, pytest, the eval-isolation check and the share-policy check), then wrote
`published/scorecard_2025_20261002T025126Z.parquet`: 17 KPI rows for 2025 with

| Context stored with the snapshot | Value |
|---|---|
| methodology version | 1.0 |
| git commit | `4d734b42` (working tree dirty: uncommitted Phase 3 work) |
| raw rows: US / CA / INTL | 10,605 / 2,014 / 1,712 |
| identity fingerprint (registration -> participant) | `58ba99159507...` |

2025 unique participants published: **3,962** (identity bounds 3,953 to 3,965).

## 2. One data steward decision

Two registrations of the same child were kept apart because the first name was mistyped (`Keff` for `Jeff`) and the household
guard blocks "same contact, different first name" (ADR-003). Same date of birth, same guardian email and phone, same year. The
steward confirms them as one person: one row in `review_decisions` (`MATCH`). Then:

```
cd dbt
uv run dbt seed --profiles-dir . --select review_decisions
uv run dbt run  --profiles-dir . --select identity marts evaluation facts measurement shares
```

## 3. The restatement log catches it

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

## 4. Reset

The demo decision was removed afterwards (`review_decisions` is header-only again) and the models rebuilt, so the log is empty
and the scorecard matches the published snapshot.
