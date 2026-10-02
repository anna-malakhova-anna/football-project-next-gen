# Onboarding log: FAN_ENGAGEMENT (Source D)

> Synthetic project. Roles are fictional. Process: [onboard-a-source.md](onboard-a-source.md) v1.3.

**Source:** fan app and ticketing: an accounts snapshot (CSV) and an event stream (JSON Lines, one file per delivery month).
**Owner (role):** Fan Engagement Product Lead. **Partner type:** fan app and ticketing vendor. **Holders:** adults only.

## Stage log

| Stage | Completed | Evidence | Notes |
|---|---|---|---|
| Discovery | 2026-10-02 | inventory row; `source_registry` | governance question raised before any data was linked |
| Profiling | 2026-10-02 | `quality.dq_summary` rows for FAN_ENGAGEMENT (observed vs configured) | |
| Contracted | 2026-10-02 | `contracts/FAN_ENGAGEMENT__accounts.yml`, `__events.yml` v1.0.0: 0 ERROR | playbook v1.3 (two components) |
| Staged | 2026-10-02 | `stg_fan_accounts`, `stg_fan_events`; `dq_summary`: 6 detectable defects OK | |
| Modelled | 2026-10-02 | `int_household`, `link_household_fan_account` in the restricted `linkage` schema; fandom models; ADR-009 decided | restricted zone, phone fallback kept, never to marketing |

## Discovery (2026-10-02)
- **Purpose:** program-impact analysis: does a household's engagement change after its first registration? Aggregate output only.
- **Legal basis / consent:** the accounts carry their own `marketing_opt_in`, which permits contact from the app. It says **nothing** about using
  registration data. Linking account to registration is a new purpose, so it is a governance decision, not an engineering one: ADR-009.
- **Minors present:** no. Accounts are adults. A household's children are reachable only through the linkage, which is why the linkage is restricted.
- **Key decision at Discovery:** events and accounts are never joined to a registration outside the restricted `linkage` schema, and nothing linked
  is used for contact. Decided before any data existed.

### Friction found (playbook change)
The playbook assumed one raw table per source. Source D arrives as two tables with different shapes and different contracts. Contracts may now be
split into components (`SOURCE__component.yml`); see the playbook changelog, v1.3.

## Profiling (2026-10-02)
1,136,358 delivered event lines over 60 months for 17,749 accounts. Observed vs configured (`dq_summary`): duplicate events 0.50% (config 0.5%),
late-arriving 2.0% (2%), account emails with capitals or spaces 5.0% (5%), blank marketing opt-in 5.0% (5%), no orphan events, no unknown event
types. Not visible from the data: clock skew (1% configured) and the share of accounts whose email differs from the registration email.

## Contracted (2026-10-02)
Two contracts, one per delivered table. `make contracts`: 0 ERROR. Warnings accepted: marketing_opt_in blank 5.0% (> 2%) and unnormalized emails
5.0% (> 2%): both repaired or carried as NULL in staging (a blank opt-in is NULL, never FALSE).

## Staged (2026-10-02)
`stg_fan_accounts` (normalized email and phone with the same macros as registrations) and `stg_fan_events` (a table, 1.1M rows): `is_duplicate`
marks every extra delivery of an event_id and the fact never counts it; `event_month` comes from `event_ts`, never from the file, so a late
event lands in the month it happened in. Clock skew is not detectable and is documented as such.

## Modelled (2026-10-02)
Households and links are built and evaluated in the restricted `linkage` schema. [ADR-009](../decisions/ADR-009-household-linkage-governance.md) was decided by Anna on
2026-10-02: aggregate linkage in a restricted zone is the project policy, the phone fallback stays on (78.8% precise, caveated), and nothing linked ever reaches
marketing. Only approved, suppressed aggregates leave the schema, and a build check enforces it. Source D is now `Modelled`.

## Used in analysis (2026-10-02, under the ADR-009 default)
Step 7 built the fandom models on the linkage ([ADR-010](../decisions/ADR-010-fandom-outcomes-design.md)). They run in the restricted schema and nothing
from them reaches an audience except as approved aggregates (step 8).
