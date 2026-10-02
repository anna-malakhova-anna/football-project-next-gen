# Playbook: onboard a source

> **Synthetic project.** The roles are fictional and no partner is real. The process is what is being shown: a new source goes through the
> same front door every time, with a contract, evidence at each stage, and a recorded decision.

**Version 1.3** (2026-10-02). The playbook has its own [changelog](#playbook-changelog) at the bottom: it is improved when onboarding a
source shows it is wrong or missing something, and that improvement is recorded, not worked around in code.

## Principles

1. **Onboard through the front door.** Every source follows these stages in order. A source is never added by one-off code.
2. **Contracts before code.** Raw data is validated against a written contract. Violations are logged in `quality.dq_contract_results` and
   reported; they are not silently fixed in staging.
3. **Evidence at every exit.** A stage is done when its exit criteria are met and its artifacts exist, not when someone says so.
4. **Friction goes in the playbook.** If following the playbook is hard, fix the playbook (and log it), do not route around it.

## Stages

Each stage maps to a status in `docs/source_inventory.md` and `dbt/seeds/source_registry.csv`.

| Stage | Exit criteria | Artifacts |
|---|---|---|
| **Discovery** | Owner named; purpose stated; legal basis and consent fields identified; minors-present flag set | Inventory row; contract draft |
| **Profiling** | Raw sample loaded as-is; `dq_source_profile` run (or the equivalent for the shape); issues listed | Profile output; issue list |
| **Contracted** | Contract agreed: schema, grain, keys, refresh, PII classes, quality thresholds, consent fields | `contracts/<source>.yml` (version, effective date) |
| **Staged** | Staging model and tests pass; contract validation passes, or each violation is accepted with a written reason | Staging model; tests; accepted-violations note |
| **Modelled** | Integrated into identity resolution and / or the facts; evaluation re-run | Updated evaluation results |
| **Production** | Included in the published scorecard; methodology updated if counting changes | Publish; CHANGELOG entry |

## RACI per stage

R = responsible (does the work), A = accountable (signs off), C = consulted, I = informed.

| Stage | Partner | Data lead | Data engineering | Privacy | Analytics |
|---|---|---|---|---|---|
| Discovery | C (describes the feed, owner, consent) | A | R | C (legal basis, minors) | I |
| Profiling | C (answers questions about oddities) | A | R | I | C |
| Contracted | C (agrees thresholds and cadence) | A | R | C (PII classes, consent fields) | C |
| Staged | I | A | R | C (consent mapping) | I |
| Modelled | I | C | R | C (if linking people or households) | A |
| Production | I | C | R | C | A |

The Data lead is accountable for getting a source safely in; Analytics is accountable once the source changes what is counted. **Privacy must
be consulted at Discovery, Contracted, Staged and Modelled**, and is the approver of any step that links data for a new purpose (see ADR-009
for the fan engagement example).

## Contracts

A contract is `contracts/<source_system>.yml`. Required fields: `source_system`, `owner_role`, `partner_type`, `delivery` (format, mechanism,
cadence), `grain`, `primary_key`, `person_identifier` (quality: `none` / `partial` / `stable`), `schema` (column, type, required, allowed values or
pattern, `pii` class), `quality` (threshold rules), `consent_fields` and what each permits, `minors_present`, `version` and `effective_date`.
Start from `contracts/_template.yml`.

`scripts/validate_contracts.py` (`make contracts`) validates the **raw** tables against the contract and writes
`quality.dq_contract_results` (source, rule, threshold, observed, status, run_at). Status:

- `PASS`: within the threshold.
- `WARN`: a quality threshold was breached. The default. It is reported and must be accepted with a reason at the Staged stage.
- `ERROR`: **fails the build.** Used for PII and consent structure: a declared consent column missing entirely, a consent column holding a value
  the contract does not allow, a required PII column missing, a raw column the contract does not declare (it could be new PII), or any rule
  that the contract marks `severity: ERROR`.

When the data legitimately changes, the contract changes: bump `version`, set a new `effective_date`, and record why in the source's onboarding log.

## Onboarding log

For each new source, keep `docs/playbook/onboarding_log_<source>.md`: the date each stage was completed, issues found, **playbook changes
made** (and a pointer to the changelog entry), and decisions. It is the evidence the process was followed.

## Checklist (copy into an issue)

```markdown
### Onboard <SOURCE_SYSTEM>  (partner type: ..., owner: ...)

**Discovery**
- [ ] Owner named (role): ...
- [ ] Purpose stated: ...
- [ ] Legal basis and consent fields identified (design assumption, not legal advice): ...
- [ ] Minors present? yes / no
- [ ] Inventory row added (`docs/source_inventory.md`); `source_registry.csv` status = Discovery
- [ ] Contract draft started from `contracts/_template.yml`

**Profiling**
- [ ] Raw sample landed as-is (strings in, strings stored); lineage columns present
- [ ] Profile run; issues listed with counts: ...
- [ ] Onboarding log created (`docs/playbook/onboarding_log_<source>.md`)

**Contracted**
- [ ] Contract agreed with the partner (thresholds, cadence): version ..., effective ...
- [ ] PII classes assigned to every column; consent fields and what each permits written down
- [ ] `make contracts` runs: 0 ERROR, WARNs reviewed

**Staged**
- [ ] Staging model 1:1 with the raw grain; typed, standardized, flags raised, nothing dropped except true junk (which is logged)
- [ ] Unknown consent is NULL, never FALSE
- [ ] Staging tests pass; every WARN accepted with a reason: ...
- [ ] `source_registry.csv` status = Staged; inventory updated (including contract status and version)

**Modelled**
- [ ] Integrated into identity resolution and / or the facts (a decision is recorded if it must NOT be mixed with resolved participants)
- [ ] Evaluation re-run; results compared with before
- [ ] Privacy consulted if the source links people or households for a new purpose

**Production**
- [ ] Methodology updated if counting changes (version bump, CHANGELOG)
- [ ] Included in the published scorecard; restatement log reviewed
- [ ] Inventory status = Production; onboarding log closed
```

## Aggregate-only sources

Some sources contain no individuals (counts by program, school or region). They follow the same stages, with these differences:

- **Decide at Discovery, in writing, how the source will be reported** and that it will never be added to resolved participants. Record it in the
  onboarding log before any data lands.
- **"Modelled" means a separate fact, not identity resolution.** The fact is deduplicated for the *source's own* double reporting, never against people.
  A lineage check (`scripts/check_lineage.py`) fails the build if the fact or its staging model feeds the participant facts, marts or identity models.
- **Overlap with participants cannot be measured, only bounded.** Report a range (low = the larger of the two counts, high = their sum), never a
  point estimate. Evaluation, with ground truth, may show where the true overlap fell.
- **Small cells still identify.** A small program is a small cell: apply suppression anywhere programs are shown.
- **Contract rules** may need cross-column checks (`max_expression_rate`) because aggregates carry their own arithmetic (total = girls + boys).

## Playbook changelog

Changes made to this playbook because onboarding a real source exposed a gap. Newest first. Each entry says what was wrong, what changed, and
which source's onboarding found it.

### v1.3 (2026-10-02): a source delivered as several tables
Found while onboarding **FAN_ENGAGEMENT** (Source D) at the Contracted stage: an accounts snapshot (CSV) and an event stream (JSON Lines) need
different raw tables and different contracts. A contract file may now be named `SOURCE__component.yml` and must declare `component:`; the
validator reports each component separately (`dq_contract_results.component`) and the coverage test still keys on `source_system`. Also added to
Discovery: if the source will be **joined to another source holding personal data**, record the governance question and its ADR before any
linking is built (here ADR-009), and keep the join in a restricted schema.

### v1.2 (2026-10-01): contract rules for aggregates
Found at the **Contracted** stage of SCHOOL_AGGREGATES. (1) The `max_expression_rate` rule was specified but unused: it is now implemented in
`scripts/validate_contracts.py` (a named SQL predicate over raw columns; the share of rows where it is TRUE is compared with the threshold) and
tested. The school contract uses it for total = girls + boys and for round-number estimates. (2) A contract with `person_identifier.quality: none`
may declare an empty `consent_fields` list; every source that has individuals must still declare them (enforced by a test).

### v1.1 (2026-10-01): aggregate-only sources
Found while onboarding **SCHOOL_AGGREGATES** (Source E) at the Discovery stage. The playbook assumed every source contains people. Added the
"Aggregate-only sources" section (decide the reporting rule at Discovery; "Modelled" means a separate fact with a lineage guard; overlap is
bounded, not estimated; small programs are small cells; cross-column contract rules). Also added the `max_expression_rate` contract rule
(documented in v1.2).

### v1.0 (2026-10-01): initial
Written before onboarding sources D (fan engagement) and E (school and recreation program headcounts). Stages Discovery to Production, with
**Contracted** added between Profiling and Staged (the inventory had no such status). Sources A to C received retrofitted contracts as a test
of the template.
