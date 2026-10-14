# ADR-017: Retention versus deletion in the identity and linkage zones

Status: accepted for the demonstration. **Synthetic data; every retention period is an assumption** and the actual period is an open question for the privacy lead (questions 18 and 19). Context from public sources, stated as a design constraint and not a finding about anyone: the amended COPPA Rule requires a written retention policy and does not allow indefinite retention.

## The tension
Phase 4 retention analytics need history across seasons. A retention limit requires child-level identifiers to be deleted. Both cannot be fully true of one identifier, so the policy has to say which analytics are kept and on what.

## Decision
- The v1 job (`retention/job.py`, `make p5-retention`) keeps working on the retention-managed store. It is **reconciled, not replaced**: `retention/zones.py` applies the same rule (`phase5.retention`: Dec 31 of birth year + `age_out_age`, plus `grace_months`, on the oldest plausible birth year among a person's records) to the zones that identity resolution and household linkage leave behind: `identity.idr_input_records`, `intermediate.int_registrations_unioned`, `marts.dim_participant`, `marts.participant_identifiers`, `linkage.int_household`.
- A participant who was ever a minor in the data and is past the age-out plus grace is **anonymized irreversibly**: names, name keys, date of birth, email and phone removed; the postal code cut to three characters; the rows of the identifier and household-link tables deleted. The pseudonymous participant id, birth year, sex, country, seasons and divisions stay: these are the coarsened facts the retention marts are built from. An adult is never touched by this rule.
- Counts only are logged (`retention_audit.zone_deletion_log`); an independent check requires every surviving identifier count to be 0.
- The experiment runs on a **copy** of the warehouse (`make retention-vs-deletion`). The warehouse itself is not deleted from because raw is immutable by convention and the build recreates every zone from it. A real deletion would also have to reach raw (question 18); this ADR does not claim it does.

## What survives (`mart_retention_vs_deletion`; tolerance `phase5.retention.survival_tolerance`, 0.5%)
| Figure | Baseline | Facts-only rebuild | Identity re-run on anonymized inputs |
|---|---|---|---|
| Unique participants | 13,395 | 13,395 (0%) | 15,460 (+15.4%) |
| Seen in 2+ seasons | 5,365 | 5,365 | 4,903 (-8.6%) |
| Retained one season after entry | 57.8% | 57.8% | 48.2% (-16.7%) |
| Retained two / three seasons | 35.2% / 21.6% | unchanged | 29.7% / 18.5% |

- **The Phase 4 retention marts are unchanged when rebuilt from the pseudonymous facts** (2,639 participants anonymized). They never read a name, a date of birth or a contact: only the participant id, year, age band, sex, country and division. A pytest (`tests/test_p5_zone_deletion.py`) runs the deletion on a copy and asserts this within tolerance.
- **They do not survive a naive rebuild.** If the pipeline re-runs identity resolution on the anonymized inputs, the matcher has nothing to link a child's seasons with: participants inflate by 15%, and retention falls by about 15%. A deletion policy therefore has to freeze the participant ids (the pseudonymous key) before the identifiers go, and identity resolution must not be re-run over deleted records. This is a design constraint on the pipeline, not a finding about any system.
- **What cannot be shown here:** re-linking a returning adult to their youth history is the analytic most directly broken, but this synthetic data contains no child who plays on as an adult inside the window (the baseline figure is 0), so the data cannot measure it. It is stated as a loss by design, not a measured one.
- Anything the policy keeps (pseudonymous ids, birth year, ZIP3) is still personal data in a combination (ADR-006, ADR-018); this ADR does not claim the residue is anonymous.

## Not covered
Raw, the staging views, backups and the leagues' own copies; deletion requests to each league are an operational process, not SQL.
