# Age-out and revocation retention

All data is **synthetic**. Every period below is an **assumption** for the demonstration: the actual retention period is an open question for the privacy lead ([questions](questions-for-stakeholders.md)). Context from public sources, stated as a design constraint and not a finding about anyone: the amended COPPA Rule requires a written retention policy and does not allow indefinite retention (Finnegan, linked in the data standard).

## What is implemented
A real job, not a document: `make p5-retention` (`retention/job.py` orchestrating `retention/sql/*.sql`). It runs on the **retention-managed copy** (schema `pii_store`), rebuilt from the Phase 5 dbt models each run. It never touches `raw` (the immutable source-system landing), `eval`, the dbt models or the published snapshots, so a dbt rebuild cannot undo a deletion and the deletion cannot corrupt the audit trail of what was received.

| Rule | When a record is due | What goes |
|---|---|---|
| `REVOKED` | the household revoked consent and `revocation_delay_days` (default 0) have passed | all child-level records of that household's children |
| `AGE_OUT` | Dec 31 of (birth year + `age_out_age`, default 18) plus `grace_months` (default 12) | all child-level records of that child |
| `MAX_AGE` | a registration is older than `max_record_months` (default 36), whatever the child's age | that record |
| `ORPHAN_HOUSEHOLD_PURGE` | a household has no child record left | the parent's email, the household's consent events and activation row |
| `REVOCATION_ACTIVATION_REMOVAL` | immediately, before any deletion | the household leaves every activation-eligible set |

Design points:
- **Oldest plausible birth year decides.** Only a birth year is collected (the data standard), so the latest possible birthday is used, and a child is judged on the oldest plausible year among their records: a typo that makes a child look younger cannot extend retention. Years before 1900 are ignored.
- **Aggregates survive, rows do not.** Before deleting, the job keeps counts by reason, market and age band (`retained_aggregate`). Anything published from them still goes through small-cell suppression.
- **Revoked parents are not forgotten into being contacted again.** The job keeps only a one-way hash of a revoked email in a do-not-contact list (`suppression_list`); the plain email goes with the household.
- **Revocation also sits in the consent chain.** A revocation is a `REVOCATION` consent event, so the dbt model `p5_household_activation` marks the household `CONSENT_REVOKED` on every rebuild (161 households here); the job's immediate removal covers a revocation that arrives between a dbt build and the job.
- **Counts only in the log.** `retention_log` holds the rule, table, rows, children and households affected, the parameters and the date. No name, email, date of birth, ZIP or id.

## How it is tested
- `tests/test_p5_retention.py` runs the job on a small seeded store with every case in it (a child on the exact age-out boundary; a typo that makes a child look younger; a record past the cap beside a newer one; a household that revoked before and one that revokes after the job date; a household with one aged-out and one young sibling; an implausible birth year) and asserts that nothing over the threshold survives, that parent data goes only when no child is left, that the log and aggregates contain no identifying value, that a second run deletes nothing more, and that the verification itself catches a planted survivor.
- The job re-checks six invariants in independent SQL after every run (`retention/sql/90_verify.sql`) and exits non-zero if any fails; `make all-phases` ends with it.

## On the generated data (`as_of` 2027-12-31)
7,657 resolved children before; 669 aged out, 190 revoked, and 3,188 lost one or more records to the 36-month cap (5,139 records); 1,366 households had no child left and their parent-side data was purged; 5,799 children remain. Which of those numbers a real policy would produce depends entirely on the periods, which are the open question.

## Not covered
Backups, logs of upstream systems, and copies the leagues hold themselves are outside this job. Deleting from the leagues' own systems needs a deletion request to each league, which is an operational process, not SQL.
