# ADR-012: Phase 5, data quality under privacy constraints: scope and design

- **Status:** Accepted for steps 1 and 2; later steps will append. Decided by Anna on 2026-10-13 (defaults confirmed).
- **Synthetic data.** The feeds, leagues, consent wordings and every number are generated. Feed shapes and consent wordings are **assumptions** made for the demonstration; none describes a real NFL, RCX, vendor or club system.

## Context
The participation data a governed platform receives is thin and messy, and the obvious fixes (collect more, buy enrichment, share more) are the ones privacy rules block. Phase 5 asks how to fix quality anyway, for a privacy lead and a club analytics lead.

## Decisions
1. **Isolated scope.** The six Phase 5 feeds are derived from the existing true US youth registry with their own random stream (`phase5.seed_offset`). No Phase 1 to 4 file, identity metric or published snapshot changes; a test compares the bytes. The cost is that the Phase 5 children are the same people as in the US league source but are not linked to it.
2. **Season window not extended.** 2025 stays the latest season; the Pop Warner and PAL feeds carry 2024 and 2025 and are stand-ins for 2026 intake.
3. **Reuse of Phase 2, not a rewrite.** The Phase 5 resolution runs the Phase 2 macros (`pair_attributes`, `pair_level_ctes`, `name_similarity`, `dob_agreement_level`, `connected_components`) on an input table with the same columns. The ordered rules R1 to R6 were moved into one macro (`idr_rules_rule_id`) so both phases apply identical rules; the Phase 2 output was checked unchanged (same row count and hash of every pair, tier and rule). The only extension is **R7** for feeds with no DOB.
4. **Rules are data.** Every quality check is a row in the `p5_dq_rules` seed: id, dimension, description, SQL predicate, a threshold for each purpose, and the fix text an operator can act on. One macro evaluates every row against `p5_record_quality`. TRUE passes, FALSE fails, NULL means not applicable, so a check never counts a record it could not evaluate. Thresholds, ages, lateness, grade bands and season starts are configuration (`phase5.dq` in `config/generation.yaml`, exported to the `p5_params` seed).
5. **Two purposes, two bars.** Participation reporting (counts by market and age band) has the lower bar; club activation (contactable households) has the higher bar and requires consent provenance. The same league can be fit for one and not the other, and the scorecard says so.
6. **Never guess.** A two-digit-year DOB is NULL, not read as 20xx; an ambiguous league spelling (the same name in two states) resolves to no league; a Pop Warner association that runs two flag leagues and sends no league code stays unresolved. Each is a finding on the scorecard.

## What the resolution found (step 2, on the generated data)
Graded against the answer key in `evaluation.eval_p5_resolution`: precision 0.9998, recall 0.866 on final clusters. The recall gap is by design: school rosters (no DOB, no parent contact) and age-group-only records cannot be matched without a guess. **3 sibling false-merge pairs remain** (a finding, not yet fixed): two children with the same first and last name in one household, one with an unreadable DOB, are indistinguishable by every rule. A first version of R7 that accepted nicknames made 15 sibling merges (James and Jamie, Michael and Mike in one family); tightening it to an exact first name, and checking the age group against the DOB elsewhere, removed all but this case. Per CLAUDE.md a sibling merge is a privacy incident, so the residual is reported, not hidden.

## Consequences
- Phase 5 models carry the dbt tag `phase5`; `make build`, `make test` and the phase 2 to 4 test targets exclude them; `make all-phases` generates the feeds and runs everything; `make p5-score` runs just the Phase 5 scorecard.
- The scorecard tables are for the data steward and league operators. The club-facing view (aggregate only, minimum cell size) is a later step.
