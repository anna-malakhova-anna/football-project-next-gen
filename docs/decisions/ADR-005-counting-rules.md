# ADR-005: Counting rules (methodology v1.0)

- **Status:** Accepted (Phase 3)
- **Context:** "How many people play flag football in our program, and how sure are we?" needs a counting methodology that is
  defined before it is computed, implemented once, and honest about what a count is. All data here is synthetic; every number
  below is from `make phase3` at the default configuration.

## Decision

Participants are counted from **one counting engine**: `fct_registration` (one row per registration) -> `fct_participant_year`
(one row per participant per year) and `fct_participant_us_season` (US only). Every mart, share, KPI and report reads from them; no
report has its own logic. The rules C1 to C15 are traceable to a model and column:

| Rule | Implemented in |
|---|---|
| C1 participant = resolved person with a valid registration in the period | `fct_participant_year` grain (participant x year); `mart_participation_global.unique_participants` |
| C2 valid registration; impossible DOBs count | `fct_registration.is_valid_registration`, `invalid_reason` (176 exact duplicates invalid; the 53 impossible-DOB records stay valid) |
| C3 participation year = calendar year | `reporting_periods` seed; `fct_registration.participation_year` (the season year) |
| C4 US spring / fall view, never blended | `fct_participant_us_season`; `fct_registration.us_season_term` |
| C5 two leagues in a year: once globally and once per org | `fct_participant_year.org_count`, `is_multi_org` |
| C6 two countries in a year: once globally; attributed (additive) and presence (non-additive) views | `countries_played`, `attributed_country_code`; `mart_participation_by_country`; additivity tests |
| C7 age at December 31 (birth year only for CA) | `fct_participant_year.age_at_cutoff` (macros `age_at_cutoff`, `age_at_cutoff_from_birth_year`; ADR-002) |
| C8 primary division = most registrations in the year, ties to the most recent; all divisions kept | `primary_division`, `all_divisions` |
| C9 sex from the participant; `U` is its own category, never imputed | `sex`; `mart_participation_segments` |
| C10 youth = 17 or under | `is_youth`; `privacy_params.youth_max_age` |
| C11 new participant; first data year censored | `status` NEW / CENSORED; tests `facts_first_year_is_censored`, `facts_status_matches_history` |
| C12 returning = valid this year and last | `status` RETURNING |
| C13 reactivated = valid now, none last year, some earlier | `status` REACTIVATED |
| C14 open-integrity-issue clusters counted and reported | `has_open_integrity_issue`; `mart_identity_uncertainty.participants_open_integrity_issue` |
| C15 a count is registered participants in onboarded sources | every report banner, the metric catalog definitions, the memo |

Alternatives considered (the memo explains each): counting registrations (overstates multi-league players), excluding flagged records
(undercounts), US-style seasons as the global period (not comparable with CA / INTL), attribution by first registration, oldest division,
proportional imputation of unknown sex, "ever played before" for returning.

## Results (methodology v1.0)

| Year | Unique participants | Valid registrations | Registrations per participant | New | Returning | Retention |
|---|---|---|---|---|---|---|
| 2023 | 2,639 | 3,776 | 1.43 | censored | censored | n/a |
| 2024 | 3,351 | 4,727 | 1.41 | 1,664 | 1,687 | 63.9% |
| 2025 | 3,962 | 5,610 | 1.42 | 1,699 | 2,263 | 67.5% |

Additivity holds exactly: for 2025 the attributed country counts sum to 3,962, the presence counts to 4,005 (43 people played in two
countries), registrations to 5,610. Every grouping set of the segments mart partitions the participants.

## Where the build differs from, or had to settle, the spec

- **Phase 2 shape.** `idr_match_edges` and `idr_clusters` carry `matcher`, `stage` and `scope` columns (and PROBABLE edges), so the
  spec's low / point / high bounds are the AUTO_PLUS_PROBABLE scope, the AUTO scope, and the AUTO scope minus the edges inside
  clusters flagged by `idr_cluster_integrity`. The clustering was refactored into the macro `connected_components(nodes, edges, keys)`
  with checksum-identical output; `mart_identity_uncertainty` calls it three times.
- **`is_junk_row` is always false** in the unioned model (junk is dropped in staging), so C2's "not a junk row" holds by construction.
  `registered_at` is NULL for INTL and is the consent capture time for CA, so "registration date within the period" cannot reject a
  record in this data; it is implemented as `REGISTERED_OUTSIDE_PERIOD` for the day a source supplies a real timestamp.
- **"Most recent registration in a year" is ordered by term, then time.** INTL has no registration time, so recency is
  SPRING < ANNUAL < FALL, then `registered_at`, then the key. A US spring followed by a Canadian season, or a Canadian season followed
  by US fall, are both ordered the way a move actually happens.
- **Unknown age stays unknown.** Four participant-years have only an impossible-DOB registration: they are counted, their age band is
  `UNKNOWN`, and nothing is imputed.
- **No annual REACTIVATED participants.** Churn in the generator is permanent, so nobody skips a whole year; reactivation appears only
  in the US spring / fall view (94 in 2025). The memo says so.
- **"Registrations failing DQ rules"** needed a definition: `dq_flag_severity` classifies every flag as AFFECTS_COUNT (duplicates,
  impossible or unparseable DOB, unmapped values), MISSING_VALUE or NORMALIZED. The KPI counts AFFECTS_COUNT over all registration
  records: 2.2% in 2025. A test fails if a new flag is raised that the seed does not classify.
- **Near-duplicates remain valid registrations.** Only exact duplicates are invalid, so the registration count carries about 100
  near-duplicate records; unique participants are unaffected.
- **Generator amendment (made for this phase).** Half the cross-border movers also register in both countries in the year they move.
  Without it only one participant-year spanned two countries and rule C6 and its additivity tests would have tested almost nothing;
  now 57 do. The amendment shifted every Phase 2 number slightly (ADR-003 states the amended figures).

## Dialect notes (DuckDB to Snowflake), new in Phase 3

| DuckDB | Snowflake |
|---|---|
| `GROUP BY GROUPING SETS (...)`, `grouping(a, b)` | the same (supported); `grouping()` returns the same bitmask |
| `count(*) FILTER (WHERE ...)`, `bool_or` | `COUNT_IF(...)`, `BOOLOR_AGG` |
| `(array_agg(x ORDER BY ...))[1]` | `MIN_BY(x, key)` or `ARRAY_AGG(x) WITHIN GROUP (ORDER BY ...)[0]` |
| `list(...)`, `list_distinct`, `list_sort`, `unnest(list)`, `len(list)` | `ARRAY_AGG`, `ARRAY_DISTINCT`, `ARRAY_SORT`, `LATERAL FLATTEN`, `ARRAY_SIZE` |
| `sha256(x)` | `SHA2(x, 256)` |
| `env_var('FLAG_PSEUDO_SALT', default)` (dbt) | a secret or a masking-policy function, not SQL text |
| `read_parquet(...)`, `COPY (...) TO ... (FORMAT parquet)` | `COPY INTO @stage ... FILE_FORMAT = (TYPE = PARQUET)` |
| `QUALIFY`, window functions | the same |

## Consequences

One definition per concept, one engine, and tests that re-derive the key counts independently (status from history, grain from
registrations, additivity across countries, partitions across grouping sets). The cost is a long list of small rules that a reader
has to hold; the memo and `docs/metrics.md` (generated from the metric catalog) exist to carry that.
