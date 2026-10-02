# User stories: onboarding a new registration source

> Context: the program receives registration data from partners (leagues, clubs, federations) in different shapes.
> These stories define what "onboarded" means before a source can affect participation counts. All data in this
> project is synthetic.

## Story 1: Profile before modelling

> As the Flag Football data lead, I want each new registration source profiled before it's modelled, so that quality issues are known before they affect participation counts.

**Acceptance criteria**
- The source lands in `raw` exactly as delivered (strings in, strings stored) with source file and row lineage.
- `dq_source_profile` has a row per column with row count, null rate, distinct count, top values (suppressed for identifiers) and parse-failure rate.
- Every defect found is a flag in `dq_defect_log` with the raw value and a rule description.
- Defects that cannot be detected without identity matching are listed explicitly, not silently dropped.

**Definition of done**
- Profile reviewed by the data lead; findings recorded under the source's "Known quality issues" in `docs/source_inventory.md`.
- Source status set to `Profiling`.

## Story 2: Map to the common schema without guessing

> As a data engineer, I want a new source staged into the common registration schema with explicit, tested rules, so that its records can be unioned with existing sources without hidden cleaning.

**Acceptance criteria**
- One staging model, 1:1 with the raw grain; types, names, emails, phones and postal codes standardized by shared macros.
- Every division, country and gender value maps through a project seed; an unmapped value fails the build.
- Bad records are flagged, not dropped. Only true junk (headers, summaries) is dropped, and each dropped row is logged.
- Unknown values stay NULL; consent that was not captured is NULL, never FALSE.
- Row counts: staging equals raw (minus logged junk).

**Definition of done**
- Staging model, seed rows and tests merged; `make all` passes.
- Source added to `int_registrations_unioned` with a column-by-column mapping in the data dictionary.
- Source status set to `Staged`.

## Story 3: Document the source, its owner and its legal basis

> As the privacy and governance lead, I want each source's owner, PII fields, minors, consent fields and legal-basis assumption recorded, so that we know what we may do with the data before we use it.

**Acceptance criteria**
- `docs/source_inventory.md` has a complete entry: partner type, owner, delivery, cadence, grain, identifier stability, PII fields, presence of minors, consent fields, legal-basis assumption, known issues and onboarding status.
- Every column of the unioned model carries a PII classification (direct identifier, quasi-identifier or non-PII) in the dbt YAML.
- The source's consent fields are mapped to `consent_photo` / `consent_marketing`, and gaps (for example, a source that captures no marketing consent) are stated.

**Definition of done**
- Owner and legal-basis assumption reviewed by the governance lead.
- Data dictionary regenerated (`make docs`) and committed.

## Story 4: Prove the pipeline detects what is actually wrong

> As an analyst who will publish participation numbers, I want a new source's defect rates compared with what was injected or expected, so that I can trust that the pipeline sees the problems it claims to.

**Acceptance criteria**
- Each expected defect for the source has a row in `dq_defect_config` (rate, denominator, detectable in Phase 1 or not).
- `dq_summary` shows observed vs configured for each; detectable defects are within +/-50% relative or the build fails.
- Any flag the pipeline raises that is not in the config is reported as `NOT_CONFIGURED` and fails the build.

**Definition of done**
- `make test` passes with the new source's rates in the comparison.
- Defects marked not detectable are handed to the identity-resolution backlog (Phase 2) with the generator's defect manifest as the evaluation key.
