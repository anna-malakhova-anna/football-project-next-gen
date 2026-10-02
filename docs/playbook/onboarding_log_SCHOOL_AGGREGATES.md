# Onboarding log: SCHOOL_AGGREGATES (Source E)

> Synthetic project. Roles are fictional. Process: [onboard-a-source.md](onboard-a-source.md) v1.2. Playbook changes made during this
> onboarding are in the playbook's own changelog and are cross-referenced below.

**Source:** school and recreation program aggregate headcounts. **Shape:** CSV per year, one row per program per year; **no individuals**.
**Owner (role):** Program Partnerships, Education. **Partner type:** school district / municipal recreation department.

## Stage log

| Stage | Completed | Evidence | Notes |
|---|---|---|---|
| Discovery | 2026-10-01 | inventory row; contract draft; `source_registry` = Discovery | see below |
| Profiling | 2026-10-01 | `quality.dq_headcount_profile` over `raw.school_headcounts` (357 rows) | issue list below |
| Contracted | 2026-10-01 | `contracts/SCHOOL_AGGREGATES.yml` v1.0.0; `make contracts`: 15 PASS, 4 WARN, 0 ERROR | playbook v1.2 |
| Staged | 2026-10-01 | `stg_school_headcounts`; `dq_summary`: all 6 Source E defects OK vs config; registry = Staged | WARNs accepted below |
| Modelled | 2026-10-01 | `fct_reported_headcount`, `mart_reported_headcount`, `eval_headcount_overlap`, `scripts/check_lineage.py`, `share_exec__reported_headcount`; registry = Modelled | aggregate-only meaning of Modelled |

## Discovery (2026-10-01)

- **Purpose:** report how many children are *reached* through school and recreation programs, as context beside the resolved participant count. It
  can never be a participant count: there is no person in it.
- **Owner:** Program Partnerships, Education.
- **Legal basis / consent (design assumption, not legal advice):** aggregate counts of minors reported by an institution. No individual, no
  contact details, no consent field. The consent question does not arise, but **re-identification of small programs** does (a program of 12 girls
  in one grade at one school): small cells must be suppressed wherever programs are shown.
- **Minors present:** yes, as counts only (no individual records).
- **Key decision recorded at Discovery:** these counts are **never** added to resolved participants. They are reported as a separate,
  non-deduplicated "reported headcount" line, with a combined-reach *range* (no point estimate, because aggregates cannot be deduplicated against
  people). This was decided before any data existed, so the data cannot argue us out of it.
- **Distinction to keep:** `PE_UNIT` is *exposure* during class (everyone in the grade); `INTRAMURAL` and `AFTER_SCHOOL` are voluntary
  participation. Exposure may be reported but is never called "players".

### Friction found at Discovery (playbook change)
The playbook assumed every source has people in it. It said nothing about **aggregate-only sources**: what "Modelled" means when records cannot
be linked to people, and how to guarantee they stay out of the participant counts. Added to the playbook (see its changelog, v1.1).

## Profiling (2026-10-01)

357 rows across five years; countries US 232, CA 80, MX 12, GB 9, JP 9; program types PE_UNIT 155, AFTER_SCHOOL 106, INTRAMURAL 96.
Issue list (profile counters, not truth):

| Issue | Rows | Share | Treatment decided |
|---|---|---|---|
| Same program reported twice in a year | 10 | 2.8% | dedupe at Staged, keep the latest `report_date`; flag |
| `grade_band` missing | 17 | 4.8% | keep the row, grade band `UNKNOWN`; flag |
| Round-number total (100/150/200/250/300) | 38 | 10.6% | keep, flag as an estimate; it still counts toward the range |
| `total_count` is not girls + boys | 28 | 7.8% | keep, flag; report girls + boys as the total, `total_count` otherwise |
| Non-numeric counts | 0 | 0% | none needed |
| Region blank (international rows) | 12.6% | | acceptable: region is optional |

## Contracted (2026-10-01)

Contract v1.0.0 declares no consent fields and no person identifier. Four rules breach their WARN thresholds on the real file, matching the profile:
grade_band nulls (4.76% > 2%), duplicate programs (2.8% > 1%), total != girls + boys (7.84% > 5%), round totals (10.64% > 5%).
Thresholds were set from what a healthy partner file should look like, not from this file, so the WARNs are real and are accepted at Staged with
the treatments above. Playbook change: v1.2 (implemented `max_expression_rate`; empty `consent_fields` for aggregates).

## Staged (2026-10-01)

`stg_school_headcounts` is 1:1 with the raw grain (357 rows). Treatments from the Profiling table are applied and every flag is logged in
`dq_defect_log`. Observed vs configured (`dq_summary`): total mismatch 28 (7.8% vs 8%), missing grade band 17 (4.8% vs 5%), duplicate report 10
(2.8% vs 3%), round number 38 (10.6% vs 10%), unmapped program type 0, unmapped country 0. All OK.

**The four contract WARNs are accepted** (owner: Program Partnerships, Education) with the treatments above. They do not block Modelled because the
arithmetic is repaired in staging (`headcount`), duplicates are superseded, and round totals are flagged as probable estimates, not discarded.

## Modelled (2026-10-01)

For an aggregate-only source, Modelled means a **separate fact with a lineage guard**, not resolution into participants.

- `fct_reported_headcount` (program x year): the staged, non-superseded rows with the repaired headcount.
- `mart_reported_headcount` (year x country, plus `ALL`): reported headcount, voluntary headcount, program count, and the **combined-reach range**.
  The overlap with registered participants cannot be measured, only bounded: per country, no more than the smaller of the reported headcount and
  the resolved youth participants. Low = participants (low) + reported - maximum overlap; high = participants (high) + reported.
- `scripts/check_lineage.py` (run by `make isolation` and `make test`) fails if any participant model reads the aggregate source or the aggregate
  fact reads a participant model. Only the reporting models named in the script may see both, and they report ranges.
- KPIs `reported_headcount`, `voluntary_program_headcount`, `combined_reach_low`, `combined_reach_high` are in the metric catalog with
  `introduced_in: 1.1`; the scorecard shows them only once `methodology_version` reaches 1.1.
- Exec share `share_exec__reported_headcount` with policy rows: a country-year with fewer than 10 reporting programs is suppressed, and the headcounts
  and reach bounds are hidden whenever the program count is small.

**Graded against the synthetic truth** (`eval_headcount_overlap`, evaluation only): the true combined reach was inside the range in all five years.

| Year | Reported | True headcount | True overlap | Overlap bound used | True combined reach | Range | Naive sum error |
|---|---|---|---|---|---|---|---|
| 2021 | 9,205 | 9,213 | 153 | 1,836 | 11,096 | 9,404 to 11,245 | +146 |
| 2022 | 9,151 | 8,964 | 168 | 2,106 | 11,182 | 9,426 to 11,541 | +354 |
| 2023 | 8,676 | 8,825 | 162 | 2,226 | 11,176 | 8,961 to 11,199 | +12 |
| 2024 | 8,661 | 8,628 | 193 | 2,283 | 10,989 | 8,928 to 11,220 | +225 |
| 2025 | 8,441 | 8,336 | 204 | 2,579 | 10,968 | 8,690 to 11,285 | +310 |

Honest reading: the range is wide because the only label-free bound on overlap is the youth participant count, about 10 times the true overlap here.
The naive sum (participants + headcount) was off by 0.1% to 3%, so in this synthetic world ignoring overlap would have cost little; that is a property
of the generator (`overlap_share_of_participants` 0.15), not a reason to skip the bound. The headcount itself is off by -1.7% to +2.1% from the
true total (duplicates, mismatched totals and estimates, after repair).
