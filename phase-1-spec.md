# Counting Flag Football — Phase 1 Spec

**Project:** A governed participation data platform for a (synthetic) global flag football program.
**Phase 1 goal:** Stand up the foundation: realistic messy source data, raw ingestion, SQL staging into a common schema, data quality profiling, and the first governance artifacts.
**Audience for this file:** Claude Code (build instructions) and Anna (owner / reviewer).

---

## 0. Project roadmap (context only — build Phase 1 only)

| Phase | Theme | Key outputs |
|---|---|---|
| **1 — Foundations** | Sources, ingestion, staging, DQ | 3 synthetic sources + hidden ground truth, DuckDB raw layer, dbt staging + unioned model, DQ profile, source inventory, data dictionary v1 |
| 2 — Identity | Who is the same person? | Blocking + fuzzy match in SQL, match-confidence tiers, `dim_participant` with survivorship rules, precision/recall evaluated against ground truth |
| 3 — Measurement & privacy | What counts as a participant? | Participation marts (unique participants vs registrations), methodology memo, consent-aware and minor-masked views, role-based access pattern |
| 4 — Outcomes & scale | Does playing create fans? | Season-over-season retention cohorts, participant→fan funnel, 2 more sources (fan engagement feed, school aggregate counts), source-onboarding playbook, README / demo polish |

Phase 1 must generate everything later phases need (consent fields, identity signals, ground truth), even if those fields aren't modelled yet.

---

## 1. Principles (apply throughout)

1. **SQL is the showcase.** Python generates data and loads it *as-is*. All cleaning, typing, standardizing, and profiling happens in SQL (dbt models). Do not clean data in Python.
2. **Raw is immutable.** Raw tables mirror source files exactly (strings in, strings stored). Typing happens in staging.
3. **Deterministic.** Single global random seed (`42`). Re-running the generator produces identical files.
4. **Synthetic and labelled as such.** Every generated file and the README state the data is synthetic. Real participant data here would be minors' PII; that's the reason, and it's stated in the README.
5. **Messiness is specified, not random noise.** Each defect is injected at a configured rate so DQ results can be checked against expectations.
6. **Ground truth is quarantined.** The person registry used to evaluate identity resolution is written to `data/ground_truth/` and is **never** loaded into the raw schema or referenced by dbt models (except a Phase 2 evaluation model, which is out of scope here).

---

## 2. Stack

- Python 3.11+, dependency management with `uv` (fallback: `pip` + `requirements.txt`)
- `faker` (locales: `en_US`, `en_CA`, `fr_CA`, `es_MX`, `en_GB`, `ja_JP`, `de_DE`)
- `duckdb` (local warehouse file: `warehouse/flag.duckdb`)
- `dbt-core` + `dbt-duckdb`
- `openpyxl` (to write the international xlsx)
- `pytest` (generator tests)
- `Makefile` for the main commands

No cloud services in Phase 1. Keep the dbt project portable, so that swapping to Snowflake later only means changing the profile plus a few dialect-specific functions. Document every DuckDB-specific function used in `docs/decisions/ADR-001-stack.md`.

---

## 3. Repo structure

```
counting-flag-football/
├── CLAUDE.md                     # short pointer to this spec + conventions
├── README.md
├── Makefile
├── pyproject.toml
├── config/
│   └── generation.yaml           # population sizes, defect rates, seed
├── generator/
│   ├── __init__.py
│   ├── population.py             # builds the true person registry
│   ├── sources/
│   │   ├── us_league.py
│   │   ├── ca_club_api.py
│   │   └── intl_federation.py
│   ├── defects.py                # reusable defect injectors
│   └── main.py
├── loader/
│   └── load_raw.py               # files -> duckdb raw schema, no transforms
├── data/
│   ├── raw/                      # generated source files (gitignored)
│   └── ground_truth/             # person registry (gitignored, never loaded)
├── warehouse/                    # flag.duckdb (gitignored)
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml.example
│   ├── seeds/
│   │   ├── division_map.csv
│   │   ├── country_map.csv
│   │   └── gender_map.csv
│   ├── models/
│   │   ├── sources.yml
│   │   ├── staging/
│   │   │   ├── stg_us_registrations.sql
│   │   │   ├── stg_ca_registrations.sql
│   │   │   ├── stg_intl_registrations.sql
│   │   │   └── _staging.yml
│   │   ├── intermediate/
│   │   │   ├── int_registrations_unioned.sql
│   │   │   └── _intermediate.yml
│   │   └── quality/
│   │       ├── dq_source_profile.sql
│   │       ├── dq_defect_log.sql
│   │       └── _quality.yml
│   ├── macros/
│   │   ├── normalize_email.sql
│   │   ├── normalize_name.sql
│   │   ├── parse_flexible_date.sql
│   │   └── age_at_cutoff.sql
│   └── tests/                    # singular tests
├── tests/                        # pytest for generator
└── docs/
    ├── source_inventory.md
    ├── data_dictionary.md
    ├── user_stories/
    │   └── onboard-new-source.md
    └── decisions/
        ├── ADR-001-stack.md
        └── ADR-002-age-cutoff-convention.md
```

---

## 4. Synthetic population (ground truth)

Build a registry of **true people** first, then derive source records from it. Each person has a hidden `true_person_id`.

**Size (configurable):** ~6,000 people.

| Segment | Share | Notes |
|---|---|---|
| US youth (ages 5–17) | 60% | |
| Canada youth (ages 5–17) | 18% | ~25% francophone (Québec, NB, ON) |
| International youth + adult | 17% | Mexico, UK, Japan, Germany, Austria, Panama; includes adult women's and men's players |
| Cross-border movers | ~2% of US+CA | Appear in both US and CA sources in different seasons |
| Adults in US/CA | remainder | Adult rec leagues, small share |

**Person attributes:** given name, family name, nickname (optional), true DOB, sex (F/M; documented as "registration-reported sex" — gender identity is out of scope and not collected), home country/region, primary guardian (name, email, phone) for minors, language preference, true consent preferences (marketing opt-in, photo consent).

**Households:** group minors into households sharing a guardian email (siblings). ~30% of youth have at least one sibling in the data. This matters in Phase 2: shared guardian email ≠ same person.

**Seasons:** 2023, 2024, 2025. US has Spring and Fall seasons; Canada and International use a calendar-year season.

**Participation behaviour (drives Phase 4 retention):**
- Each person has a first season and a churn probability per season (higher for ages 14+, lower for ages 8–11)
- ~5% of US youth register in **two leagues in the same season** (legitimate multi-league play, not duplicates)
- Girls' participation grows season over season (higher new-player rate for F in later seasons) so there's a real trend to find later

Write the registry to `data/ground_truth/person_registry.parquet` and a `registration_truth.parquet` mapping every generated source record ID → `true_person_id`.

---

## 5. Source specifications

Each source is generated from the registry, then defects are injected at the configured rates. Store defect rates in `config/generation.yaml`.

### 5.1 Source A — US league registrations (CSV)

- **Format:** One CSV per season export, e.g. `data/raw/us_league/registrations_spring_2024.csv`
- **Represents:** A national youth league operator exporting registrations across many regional leagues
- **Grain:** One row per registration (person × league × season)

| Column | Example | Notes |
|---|---|---|
| `registration_id` | `USR-2024S-004512` | Unique within file |
| `league_id` | `L-TX-0142` | |
| `league_name` | `North Austin FLAG` | |
| `season` | `Spring 2024` | |
| `division` | `U10` / `10U` / `Under 10` | Label varies by league |
| `player_first_name` | | |
| `player_last_name` | | |
| `player_dob` | `03/14/2015` or `2015-03-14` | Mixed formats |
| `player_gender` | `M`, `F`, `Boy`, `Girl`, `Female`, blank | |
| `guardian_name` | | |
| `guardian_email` | | |
| `guardian_phone` | `(512) 555-0142`, `512.555.0142`, `5125550142` | |
| `zip` | `07302` or `7302` | Leading zeros sometimes dropped |
| `team_name` | | |
| `registered_at` | `2024-02-11 19:42:03` | |
| `waiver_signed` | `Y`/`N`/`yes`/`TRUE` | |
| `photo_consent` | `Y`/`N`/blank | |
| `marketing_opt_in` | `Y`/`N`/blank | |

**Defects (default rates):**
- Name typos (1 char edit) on re-registration: 4%
- Nickname used instead of given name on re-registration (Robert→Bob, Elizabeth→Liz): 3%
- Exact duplicate rows (double submit): 1.5%
- Near-duplicate (same person, same league, same season, different `registration_id` and timestamp): 1%
- Impossible DOB (future date or age > 80): 0.5%
- DOB day/month swapped: 1%
- Guardian email case or whitespace variants: 8%
- Guardian email changed between seasons: 6%
- Missing `player_gender`: 3%
- Missing `photo_consent`: 10%

### 5.2 Source B — Canadian club registrations (JSON API dump)

- **Format:** Paginated JSON, mimicking API responses: `data/raw/ca_club/page_0001.json`, … (200 records per page, with `next_page` cursor fields)
- **Represents:** A club management platform used by Canadian clubs
- **Grain:** One record per member per season (calendar year)

```json
{
  "page": 1,
  "next_page": 2,
  "records": [
    {
      "member_uuid": "c5b1…",
      "club": {"club_code": "QC-MTL-07", "club_name": "Les Éclairs de Rosemont", "province": "QC"},
      "season_year": 2024,
      "program": "Flag 5v5 – Junior",
      "participant": {
        "prenom_first": "Élodie",
        "nom_last": "Tremblay",
        "birth_year": 2013,
        "sex": "F",
        "language": "fr"
      },
      "guardian": {"full_name": "…", "email": "…", "phone": "+1 514 555 0199"},
      "postal_code": "H1X 2B3",
      "consents": {"casl_marketing": true, "photo_media": null, "consent_captured_at": "2024-01-20T15:02:11Z"},
      "updated_at": "2024-03-01T10:00:00Z"
    }
  ]
}
```

**Key quirks:**
- **Birth year only** (no full DOB). This forces identity resolution to work with weaker signals.
- `member_uuid` is stable within a club but **a different UUID if the player switches clubs**
- `program` is free text mixing French and English (`Junior`, `Benjamin`, `Atome`, `U12`, `Senior Féminin`)
- Nested objects; some records missing the `consents` object entirely

**Defects:**
- Accents stripped on some records (Élodie→Elodie): 10%
- All-caps names: 5%
- Postal code without space or lowercase: 15%
- Missing `consents` object: 7%
- Same member appearing on two pages, i.e. a pagination overlap duplicate: 1%
- `birth_year` off by one vs truth: 1.5%

### 5.3 Source C — International federation returns (XLSX)

- **Format:** One workbook per season, `data/raw/intl/federation_returns_2024.xlsx`, **one sheet per country**
- **Represents:** National federations submitting player returns to an international body
- **Grain:** One row per registered player per season

| Column | Example | Notes |
|---|---|---|
| `Player ID` | `MEX-24-0091` | Federation-local, not stable across years for every country |
| `Full Name` | `María José Hernández López` | Single field; name order varies (JP sheets: family name first) |
| `Date of Birth` | `14/03/2009` | DD/MM/YYYY; some cells are Excel date serials |
| `Gender` | `W`, `M`, `F`, `Mujer`, `Hombre` | |
| `Category` | `U15`, `Juniors`, `Senior Women`, `Masters` | |
| `Club` | | |
| `Country` | `MEX`, `Mexico`, `MX` | Inconsistent within the workbook |
| `Email` | | Optional; often blank for minors |
| `Media Consent` | `Yes`/`No`/blank | |

**Defects:**
- 2 header rows (title row + blank) on some sheets: Germany and Austria
- Trailing summary row (`Total: 312`) on some sheets
- Excel date serials instead of strings: 20% of DOBs on the UK sheet
- Name order inverted vs expectation: Japan
- Country value inconsistency: 25%
- Player ID reissued each year for Panama (no stable ID)

---

## 6. Loading (raw layer)

`loader/load_raw.py` loads files into DuckDB schema `raw` with **no transformations** beyond what's needed to land the data:

- `raw.us_league_registrations`: all columns as VARCHAR, plus `_source_file`, `_loaded_at`, `_row_number`
- `raw.ca_club_records`: one row per record. Keep the nested JSON as a JSON column (`record_json`) plus `_page`, `_source_file`, `_loaded_at`. Flattening happens in SQL.
- `raw.intl_federation_returns`: all sheets stacked, all values as VARCHAR (Excel serials kept as their raw string), plus `_sheet_name`, `_source_file`, `_excel_row`, `_loaded_at`. Header-row junk and summary rows are **loaded as-is** and removed in staging.

Loading must be idempotent: drop and recreate raw tables on each run.

---

## 7. dbt models

### 7.1 Seeds (reference data owned by the project)

- `division_map.csv`: maps every source division/program/category label → canonical division (`U6`, `U8`, `U10`, `U12`, `U14`, `U17`, `ADULT_W`, `ADULT_M`, `ADULT_MIXED`). Columns: `source_system`, `source_label`, `canonical_division`, `notes`.
- `country_map.csv`: any country representation → ISO 3166-1 alpha-2
- `gender_map.csv`: any registration sex/gender value → `F` / `M` / `U` (unknown)

### 7.2 Macros

- `normalize_email(col)`: lowercase, trim. Gmail dot/plus handling is behind a flag, off by default; document why.
- `normalize_name(col)`: trim, collapse whitespace, title case. Also outputs an accent-stripped `*_key` version for matching.
- `parse_flexible_date(col)`: handles `MM/DD/YYYY`, `YYYY-MM-DD`, `DD/MM/YYYY` (source-aware), and Excel serials. Returns NULL rather than guessing when ambiguous, with an accompanying `*_parse_status` column.
- `age_at_cutoff(dob, season_year)`: age as of the project cutoff date. See ADR-002.

### 7.3 Staging (one model per source, 1:1 with raw grain)

Each staging model:
- Casts and standardizes types
- Normalizes names, emails, phones (digits-only E.164-ish), postal/zip
- Maps division, country, and gender through the seeds
- Computes `dob` (or `birth_year` only, for CA), `birth_year`, `age_at_cutoff`
- Standardizes consent fields to `TRUE` / `FALSE` / `NULL`. **NULL means "not captured" and must never be coerced to FALSE or TRUE.**
- Adds `source_system` (`US_LEAGUE`, `CA_CLUB`, `INTL_FED`) and `source_record_id`
- Flags (does not drop) bad records: `is_exact_duplicate`, `is_impossible_dob`, `is_junk_row`, `dob_parse_status`
- Drops only true junk (header and summary rows in INTL), logged in `dq_defect_log`

### 7.4 Intermediate

`int_registrations_unioned`: common schema across all three sources, one row per registration.

| Column | Type | Notes |
|---|---|---|
| `registration_key` | varchar | `source_system` + `source_record_id` hash |
| `source_system` | varchar | |
| `source_record_id` | varchar | |
| `source_person_id` | varchar | Source's own person identifier, if any (NULL for US) |
| `season_label` | varchar | Original label |
| `season_year` | int | |
| `season_term` | varchar | `SPRING` / `FALL` / `ANNUAL` |
| `organization_id` | varchar | League, club, or federation club |
| `organization_name` | varchar | |
| `country_code` | varchar(2) | |
| `region_code` | varchar | State or province where available |
| `first_name`, `last_name` | varchar | Display form |
| `first_name_key`, `last_name_key` | varchar | Match form (lowercase, accent-stripped) |
| `dob` | date | NULL for CA |
| `birth_year` | int | |
| `dob_precision` | varchar | `DAY` / `YEAR` |
| `sex` | varchar(1) | F/M/U |
| `age_at_cutoff` | int | |
| `canonical_division` | varchar | |
| `is_minor` | boolean | |
| `contact_email` | varchar | Guardian email for minors, own email for adults |
| `contact_phone` | varchar | |
| `postal_code` | varchar | |
| `consent_photo` | boolean | Nullable |
| `consent_marketing` | boolean | Nullable |
| `registered_at` | timestamp | |
| `dq_flags` | varchar[] / list | All flags raised on this record |

### 7.5 Quality models

- `dq_source_profile`: one row per source × column. Columns: row count, null rate, distinct count, top values, and parse-failure rate where applicable. Pure SQL; use `UNPIVOT` or a macro loop.
- `dq_defect_log`: one row per flagged record per flag. Columns: source, record id, flag, raw value, rule description.
- `dq_summary`: one row per source × flag with count and rate. Used to compare **observed** defect rates against **configured** injection rates (export config rates to a seed or table for this comparison).

### 7.6 Tests

Generic (in YAML):
- `unique` + `not_null` on `registration_key`
- `accepted_values` on `source_system`, `sex`, `canonical_division`, `season_term`, `dob_precision`
- `relationships`: every non-null `canonical_division` exists in `division_map`
- `not_null` on `country_code` (warn severity)

Singular (in `dbt/tests/`):
- No unmapped division labels (any staging label missing from `division_map` fails the build)
- `consent_*` is never FALSE where the raw value was blank (protects the NULL ≠ FALSE rule)
- `age_at_cutoff` is between 3 and 80 for all records not flagged `is_impossible_dob`
- Observed defect rates are within ±50% (relative) of configured rates. This is a sanity check that the pipeline detects what was injected.

---

## 8. Governance artifacts (Phase 1 versions)

### `docs/source_inventory.md`
One row per source:
- Source name and system code
- Represented partner type (league operator, club platform, federation)
- Owner (fictional role, e.g. "League Ops, US")
- Format and delivery mechanism
- Refresh cadence (assumed)
- Grain
- Stable person identifier? (yes / partial / no)
- PII fields
- Minors present? (yes/no)
- Consent fields captured, and their legal basis assumption (e.g. CASL for CA marketing)
- Known quality issues (link to DQ summary)
- Onboarding status: `Discovery` / `Profiling` / `Staged` / `Modelled` / `Production`

All three sources should end Phase 1 at `Staged`.

### `docs/data_dictionary.md`
Every column of `int_registrations_unioned`: definition, type, derivation logic, source mapping per system, nullable, PII classification (`Direct identifier` / `Quasi-identifier` / `Non-PII`).

Generate the column list from the dbt YAML so the two don't drift. A small script or dbt docs export is fine; descriptions live in YAML.

### `docs/user_stories/onboard-new-source.md`
3–4 user stories in standard form, each with acceptance criteria and a definition of done. For example:
> As the Flag Football data lead, I want each new registration source profiled before it's modelled, so that quality issues are known before they affect participation counts.

### ADRs
- **ADR-001 Stack:** why DuckDB + dbt locally, how it ports to Snowflake, and every DuckDB-specific function used
- **ADR-002 Age cutoff convention:** the project computes age as of **December 31 of the season year** for all sources. This is a project convention, not a claim about any real league's rule. It's needed because sources use different division boundaries and CA only provides birth year. Document the trade-offs.

---

## 9. Makefile commands

```
make setup      # install deps
make generate   # run generator -> data/raw + data/ground_truth
make load       # load raw files into duckdb
make build      # dbt seed + dbt run
make test       # pytest + dbt test
make all        # generate, load, build, test
make clean      # remove data/, warehouse/, dbt target/
```

---

## 10. Build order for Claude Code

1. Repo scaffold, `pyproject.toml`, Makefile, `.gitignore`, `CLAUDE.md`
2. `config/generation.yaml` with all sizes and defect rates
3. `population.py` + pytest checks (counts by segment, household sharing, multi-league share ≈ 5%)
4. Source generators one at a time (US → CA → INTL), each with a pytest asserting schema and approximate defect rates
5. `load_raw.py`, then verify row counts match generated files
6. dbt project, profile, seeds
7. Macros, each with at least one singular test exercising edge cases
8. Staging models (US → CA → INTL)
9. `int_registrations_unioned`
10. Quality models + tests
11. Docs: inventory, dictionary, user stories, ADRs
12. README: what this is, why it's synthetic, how to run, Phase 1 status, roadmap table

Stop after each numbered step that produces runnable output and confirm it runs before continuing.

---

## 11. Phase 1 definition of done

- [ ] `make all` runs clean from an empty clone in under 2 minutes
- [ ] Generator is deterministic (two runs → identical file hashes)
- [ ] Ground truth is never present in the DuckDB `raw` schema (add a test)
- [ ] All three sources land in raw with zero transformation
- [ ] All staging models and `int_registrations_unioned` build; all tests pass (warn-level allowed only on `country_code`)
- [ ] `dq_summary` shows observed vs configured defect rates for every injected defect type
- [ ] Every raw division/program/category label maps to a canonical division
- [ ] Consent NULL ≠ FALSE rule enforced by test
- [ ] Source inventory, data dictionary, user stories, and both ADRs written
- [ ] README states the data is synthetic and why

---

## 12. Explicitly out of scope for Phase 1

- Identity resolution / `dim_participant` (Phase 2)
- Participation metrics and the methodology memo (Phase 3)
- Masked or consent-filtered views (Phase 3)
- Fan engagement data and retention cohorts (Phase 4)
- Dashboards or any UI
- Cloud deployment
