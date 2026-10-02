# ADR-002: Age cutoff convention (age as of December 31 of the season year)

- **Status:** Accepted (Phase 1)
- **Context:** Participation analysis needs a comparable age for every registration, and divisions by age drive
  who counts as a youth player. The three sources disagree: US leagues label divisions (`U10`, `10U`, `Under 10`)
  with no stated cutoff, Canadian clubs use bilingual program names, federations use their own categories, and
  the Canadian source gives **birth year only**. We have no cutoff rule from any partner.

## Decision

The project computes `age_at_cutoff` as **completed years of age on December 31 of the season year**, for every
source (`macros/age_at_cutoff.sql`, project variable `age_cutoff_month_day = '12-31'`).

- With a full DOB: `season_year - birth_year`, minus 1 if the birthday falls after the cutoff date. Under Dec 31,
  this reduces to `season_year - birth_year`.
- With birth year only (CA): `season_year - birth_year`. This is **exact** under a Dec 31 cutoff, which is the main
  reason for choosing it: it is the only common cutoff that birth year alone can reproduce.
- Spring and fall US seasons in the same calendar year get the same cutoff.
- `is_minor` is `age_at_cutoff < 18`. `is_impossible_dob` is `age_at_cutoff < 0 or > 80`.

**This is a project convention, not a claim about any real league's rule.** The synthetic generator assigns
division labels from the same convention (US) or from its own fictional program rules (CA, INTL).

## Trade-offs

- **Comparable and reproducible,** and it never needs information a source lacks. Birthday-aware logic still
  works if the cutoff variable changes (tested with `08-31`).
- **Not what happens on the field.** A player's age on game day differs from age at Dec 31 by up to a year; a child
  can be counted a year older (or younger) than the league treats them. Analyses that need game-day age must
  use another measure.
- **Division boundaries do not line up across sources,** because `canonical_division` comes from each source's own
  label, not from `age_at_cutoff`. Examples: CA `Atome` (ages 5-7) maps to `U8`, while the US puts age 5 in `U6`;
  an international `U15` maps to `U14`. These are recorded in `division_map` notes. Comparing `canonical_division`
  with `age_at_cutoff` is a useful data-quality check, not an error.
- **Birth-year-only precision:** a CA age is exact under Dec 31, but any other cutoff would make it an upper bound
  (`age_at_cutoff_from_birth_year` documents this). A 1-year birth-year error (1.5% injected) shifts the age by 1.
- **Edge cases covered by tests** (`dbt/tests/macro_age_at_cutoff.sql`): birthday on the cutoff day, leap-day birthdays,
  future DOBs (negative ages, left for the impossible-DOB flag), NULL DOB, and an alternative cutoff.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Age at registration date | Not available for INTL; differs by when in the window someone registered |
| Age at season start | Needs season start dates that no source provides consistently; CA has birth year only |
| School-year cutoff (e.g. Aug 31 / Sep 1) | Common in youth sport, but birth year alone cannot reproduce it, so CA would be approximate |
| Age at the end of the season in each source's own calendar | Sources do not state these dates |

## Consequences

- One definition, one macro, one variable. Changing the cutoff is a single variable change; every dependent model
  and the data dictionary text must be re-checked, because CA ages stop being exact.
- Phase 3 participation metrics (youth vs adult, minors masked) inherit this convention and must cite it in the
  methodology memo.
