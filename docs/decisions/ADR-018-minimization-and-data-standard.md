# ADR-018: Minimization trade-off and the chosen data standard point

Status: **measured; the standard's point is NOT yet chosen** (Anna decides; see "Open decision"). Synthetic data throughout.

## Question
What does each field's granularity buy in identity accuracy and data fitness, and what does it cost in re-identification risk? (Phase 5 spec section 7.)

## How it is measured
- Seed `minimization_variants` (V0_FULL, V1_BIRTH_MONTH, V2_BIRTH_YEAR, V3_NO_PHONE, V4_HASHED_CONTACT). The dbt var `minimization_variant` applies the variant's treatments **once, in `idr_input_records`** (macros in `macros/minimization.sql`); the Phase 2 models are not forked. V0_FULL reproduces the default build exactly (a check in `eval_minimization_checks`).
- `scripts/p5_minimization_runs.py` (`make minimize`) rebuilds the identity chain and its evaluations once per variant (about 30 seconds each), writes one row per variant and matcher to `eval.minimization_runs`, and always restores the default build. `eval_minimization_tradeoff` (evaluation only) joins those with two label-free marts.
- **Nothing is tuned.** The m-probabilities are the reasoned ones from Phase 2 and are identical in every run; only the u-probabilities, which Phase 2 already estimates from the data without labels, adapt to the coarsened input.
- Headline matcher: Fellegi-Sunter, before review, automatic links only (the matcher alone, no steward). The rules matcher is reported beside it.
- Risk (`mart_reidentification_risk`, label-free): equivalence classes over (year, DOB at the variant's precision, postal at the variant's precision, sex, country), the analyst share's quasi-identifiers with the variant applied. Reported as the share of participant-years that are unique and the share in a class below `k_min`.
- Fitness (`mart_minimization_fitness`, label-free): see "Limits".

## What it found (answer key; report, not a recommendation)
| Variant | FS precision | FS recall | Sibling/twin merges | Count error | % unique | % k<k_min |
|---|---|---|---|---|---|---|
| V0 full | 0.9982 | 0.9969 | 7 | +0.2% | 99.0 | 100 |
| V1 birth month | 0.9982 | 0.9845 | 0 | +1.4% | 94.4 | 100 |
| V2 birth year, ZIP3 | 0.9992 | 0.9969 | 1 | +0.2% | 57.1 | 97.7 |
| V3 + no phone | 0.9936 | 0.9965 | 1 | +0.1% | 57.1 | 97.7 |
| V4 + hashed email | 0.9936 | 0.9965 | 1 | +0.1% | 57.1 | 97.7 |

- **Dropping the day of birth and the ZIP5 cost the matcher almost nothing here, and removed most of the uniqueness** (99.0% to 57.1% of participant-years alone in their class). Sibling/twin merges fell from 7 to 1. A plausible reading: a shared full DOB is strong evidence for the matcher, and twins share it; the coarser date stops it from outweighing the other evidence. One synthetic dataset and counts of 7 and 1: a pattern to look at, not a law.
- **Birth month alone is a poor stop**: it costs recall (0.9845) and buys little privacy (94.4% unique).
- **Dropping the phone is where accuracy is paid**: FS precision falls to 0.9936, and the rules matcher's recall falls from 0.926 to 0.849 (count error +12%), because the rules lean on the phone.
- **Hashing the email changes nothing for matching** (exact equality survives a hash) and costs the whole ACTIVATE purpose by construction.
- **No variant reaches `k_min`.** Even at birth year and ZIP3, 97.7% of participant-years sit in a class below 10: a small cell grid (year, birth year, ZIP3, sex, country) is still fine-grained. Coarsening the share further (age band, a wider geography) is a separate lever not tested here. This is also the standing k-anonymity warning of ADR-006.

## Limits (stated, not hidden)
- Fitness: a rule that needs a field at a precision the variant no longer holds (the cross-record day-level DOB check; email well-formedness on a hash) can no longer be evaluated. That *raises* measured fitness: lost detection, not gained quality. The seed lists those rules; `rules_no_longer_evaluable` says how many. Flag-based rules judge the value at collection and are taken as unchanged.
- V1 treats the month as the first of the month and uses the day-level comparison on it; the agreement levels were designed for full dates, and a purpose-built month level would need its own reasoned m-probability. Not done, to keep to "no tuning".
- The hashed email is a plain hash. **Assumption:** a real design would use a keyed hash held outside the analytics platform.
- Risk is measured on participant-year quasi-identifiers. Direct identifiers (email, phone) are counted apart (`contact_fields_held`), not folded into k.
- One synthetic dataset, one seed.

## Open decision (Anna)
Which point does the data standard cite? The measurements make V2 the natural candidate (most of the privacy gain, no accuracy loss on the headline matcher), V3 a trade of precision for one fewer direct identifier, and V4 a trade of the whole activation purpose for the same. The choice also depends on questions the data cannot answer (whether clubs need the phone; the activation purpose). Until it is chosen, `docs/data-standard.md` keeps its present field list and cites this ADR as pending.

## Consequences
- The frontier is a deliverable, not one answer. `make minimize` reproduces it; CI runs the reduced set V0/V2/V4 (`MIN_VARIANTS`).
- DuckDB-specific: `date_trunc` on a date and `md5` (both have Snowflake equivalents); logged in ADR-001.
