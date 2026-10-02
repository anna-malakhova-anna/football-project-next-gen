# ADR-008: Phase 4 scope, decisions along the way, and what it found

- **Status:** Accepted (Phase 4). Records decisions that did not fit in a narrower ADR, and findings that should not be buried. All data is synthetic.

## Decisions

1. **The data window is configuration, not code.** The window grew from three years (2023 to 2025) to five (2021 to 2025). `seasons.first_observed_year` is the
   only place the first year is set; an `observation_window` seed carries it into SQL, a test fails if a model contains a literal year, and the censored first
   year (new, returning and retention are not defined for it) comes from the seed. Growing the window restated three published years (Example 2 in
   `docs/reports/restatement_demo.md`: 41 KPIs changed, 23 requiring restatement). The old snapshots stay; a v1.0 baseline for all five years was published.
2. **Sources are onboarded by a playbook, with contracts.** `docs/playbook/onboard-a-source.md` (stages Discovery to Production, a RACI, an onboarding log per
   source). Every source has a contract in `contracts/`, validated against the raw tables on every build; a missing consent column, an undeclared raw column or
   a bad consent value is an `ERROR` that fails the build, other breaches are `WARN`. The playbook was changed three times by what onboarding exposed
   (aggregate-only sources, contract rules for aggregates, a source delivered as several tables); its changelog says which source found each gap.
3. **An aggregate-only source never becomes participants.** School and recreation program headcounts (Source E) are a separate fact, guarded by a lineage
   check, reported as a bounded range for combined reach, and suppressed by program count. Methodology v1.1 added four KPIs and changed none (a catalog
   `introduced_in` gate keeps new KPIs out of older versions; the restatement log gained `NEW_KPI` and `DEFINITION_CHANGED`).
4. **The methodology memo stays a skeleton until Anna writes it.** The generator marks every prose paragraph `DRAFT: Anna to rewrite` and refuses to overwrite
   rewritten prose. Phase 4 proceeded with the skeleton (Option B) rather than waiting; v1.1 changes are drafted with the same markers.
5. **Censoring is the point of the retention analysis.** An age-out (turning 18) and the end of the data are censored, never churn; the naive version is
   computed beside the correct one against the generator's true churn parameters. The generator has no adult continuation, so a youth-to-adult rate would be about
   zero by construction. (The youth-to-adult, transition and driver models were built and then removed by the rework, below.)
6. **Linking registrations to fan accounts is a governance decision, not an engineering one** (ADR-009, decided by Anna on 2026-10-02: restricted zone, phone fallback kept, never to marketing). The
   result of the analysis it enables is ADR-010.
7. **The Phase 3 and Phase 4 layers are built together.** A Phase 3 scorecard reads a Phase 4 model, and Phase 4 marts read Phase 3 marts, so the tag-based
   phase targets no longer build independently. `make all-phases` is the supported full build; `make phase3` and `make phase4` are aliases for it.
8. **Evaluation checks live in `models/evaluation/`.** A dbt test that reads the truth, placed in `tests/`, broke the isolation rule and was caught by the
   publish gate. Truth-reading checks are now models with a pass/fail column and an `accepted_values` test.
9. **The site is generated and computes nothing.** `scripts/build_site.py` reads only `share_exec`, an approved aggregate, whitelisted evaluation summaries and
   governance metadata, and fails the build if a chart spec calculates, aggregates, bins, folds or windows in the browser.
10. **The fan-acquisition rework (`rework-fan-acquisition-spec.md`) supersedes parts of this phase.** Retention transitions, drivers and the youth-to-adult
   model were cut (nothing published depended on them). Source E (school headcounts) was demoted to a stretch: its code, data, contract, tests and v1.1 KPIs
   stay, but it is off the site's main pages and the report headline (it has an appendix page). Source D, the household linkage, the fan DiD and the site are
   extended or restructured by the rework; `docs/rework_inventory.md` has the disposition of every component.

## Findings worth keeping in view
- **Identity at scale.** With the rework's 15,000 people the final matcher merges **9 groups of twins** on the international returns (the rules baseline merges none, the
  literal Fellegi-Sunter version 213). Twins share a family name, an exact birth date, an organization and a season; international returns carry no guardian email for most
  minors and no phone, so the contact-based guard never fires. Nothing was tuned in response. A label-free fix exists (two records in the same organization and season with
  different first names cannot be one person) but it changes the matcher after the answer key was seen, so it is left as a **decision for the project owner**; until then the
  incidents are reported (`docs/identity_resolution.md`, `docs/phase2_results.md`).
- **Linkage is biased and its phone fallback is weaker.** Link rate 36% of households, 40% in the US and Canada, 13% to 21% elsewhere; email links are 100%
  precise, phone links 88% (ADR-009; the numbers were re-measured after the rework).
- **The naive fan estimate is about 1.7 times too big; matching gets close but not exact** (ADR-010, re-measured after the rework).
- **Published snapshots record row counts for the three registration sources only.** New school or fan data would not be named `NEW_SOURCE_DATA` by the
  restatement log. Extending the snapshot context (and the log) to every source is the obvious next change; it was not made in Phase 4 because it changes the
  snapshot schema that five baseline snapshots already use.
- **Test time.** The fan event stream (1.1 million lines) makes a full-size generator run slow, so the test configuration shrinks it for every test except
  `tests/test_fan.py` (`tests/conftest.py`). A full pytest run takes about 80 seconds.

## Consequences
- Anything that reads the truth lives in `models/evaluation/`; anything that reaches an audience is an approved aggregate; both are checked on every build.
- A source's status in `source_registry` is a claim the build checks (a contracted source needs a contract that passes).
