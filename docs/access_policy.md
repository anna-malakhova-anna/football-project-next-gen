# Access policy

> **Generated** from `dbt/seeds/audience_column_policy.csv` by `scripts/build_access_policy.py` (`make docs`). Edit the CSV and
> the rationale below in the script, not this file. All data in this project is synthetic.

**These are project policies informed by regimes such as COPPA, CASL and GDPR. They are not legal interpretations**, and no
legal review has taken place. DuckDB has no per-user grants, so each audience gets its own schema (`share_<audience>`) and the
controls below are enforced by tests and a policy check. ADR-006 maps them to Snowflake roles, masking policies and row access
policies (design only; not implemented).

## Principles

- **Least privilege by default.** Each audience receives only the columns and rows it needs, listed explicitly.
- **NULL consent is not consent.** A consent that was not captured is never treated as given: not for a contact list, not for a
  clearance roster. A conflict among people who share an address excludes the address.
- **A minor's own details are never shared with marketing.** For a minor the contact is the guardian.
- **Small numbers are not published.** Counts below the threshold are suppressed, with a second cell hidden where a published
  subtotal would otherwise reveal the first.
- **Tests check what is absent**, not only what is present.

## Audience by data

| Audience | Schema | Purpose | Grain | Identifiers | Rows |
|---|---|---|---|---|---|
| **exec** | `share_exec` | Program reporting | Aggregates only | None | All, with small-cell suppression (primary and secondary) |
| **analyst** | `share_analyst` | Analysis and modelling | Participant-year | Pseudonymous key only; no names or contact info; birth year, not DOB; postal prefix only | All |
| **ops** | `share_ops` | Running leagues, resolving data issues | Registration, participant, review queue | Full identifiers | All, plus the review queue |
| **marketing** | `share_marketing` | Outreach | Contact list (one row per email) | Contact email; first name only for a sole adult player | Only addresses where EVERY participant sharing it has marketing consent TRUE (NULL is not consent); never a minor's own details; clusters with an open integrity issue excluded |
| **media** | `share_media` | Photo and video clearance | Roster | Name, organization, season | Only participants whose most recent captured photo consent is TRUE; the list means cleared, anyone absent is NOT cleared, including NULL; clusters with an open integrity issue excluded |

## What each share contains

### exec

**`share_exec__participation_by_country`**

| Column | Treatment |
|---|---|
| `participation_year` | DIMENSION |
| `country_code` | DIMENSION |
| `participants_attributed` | AGGREGATE_SUPPRESSED |
| `participants_present` | AGGREGATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__participation_by_sex`**

| Column | Treatment |
|---|---|
| `participation_year` | DIMENSION |
| `sex` | DIMENSION |
| `participants` | AGGREGATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__participation_global`**

| Column | Treatment |
|---|---|
| `participation_year` | DIMENSION |
| `unique_participants` | AGGREGATE_SUPPRESSED |
| `registrations` | AGGREGATE_SUPPRESSED |
| `registrations_per_participant` | DERIVED_RATE_SUPPRESSED |
| `multi_org_participants` | AGGREGATE_SUPPRESSED |
| `retention_rate` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__participation_segments`**

| Column | Treatment |
|---|---|
| `participation_year` | DIMENSION |
| `country_code` | DIMENSION |
| `age_band` | DIMENSION |
| `participants` | AGGREGATE_SUPPRESSED |
| `girls_share_of_youth` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__participation_status`**

| Column | Treatment |
|---|---|
| `participation_year` | DIMENSION |
| `status` | DIMENSION |
| `participants` | AGGREGATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

Explicitly **not** available:

| Column | Why |
|---|---|
| `participant_id` | NOT_AVAILABLE: the exec audience receives aggregates only, never record-level data |
| `analyst_key` | NOT_AVAILABLE: the exec audience receives aggregates only, never record-level data |
| `first_name` | NOT_AVAILABLE: the exec audience receives aggregates only, never record-level data |
| `last_name` | NOT_AVAILABLE: the exec audience receives aggregates only, never record-level data |
| `dob` | NOT_AVAILABLE: the exec audience receives aggregates only, never record-level data |
| `birth_year` | NOT_AVAILABLE: the exec audience receives aggregates only, never record-level data |
| `contact_email` | NOT_AVAILABLE: the exec audience receives aggregates only, never record-level data |
| `contact_phone` | NOT_AVAILABLE: the exec audience receives aggregates only, never record-level data |
| `postal_code` | NOT_AVAILABLE: the exec audience receives aggregates only, never record-level data |
| `postal_prefix` | NOT_AVAILABLE: the exec audience receives aggregates only, never record-level data |
| `organization_id` | NOT_AVAILABLE: the exec audience receives aggregates only, never record-level data |
| `source_person_id` | NOT_AVAILABLE: the exec audience receives aggregates only, never record-level data |

### analyst

**`share_analyst__participant_year`**

| Column | Treatment |
|---|---|
| `analyst_key` | PSEUDONYMIZED: sha256(participant_id \|\| salt) |
| `participation_year` | DIMENSION |
| `valid_registration_count` | RECORD_LEVEL |
| `org_count` | RECORD_LEVEL |
| `is_multi_org` | RECORD_LEVEL |
| `attributed_country_code` | RECORD_LEVEL |
| `countries_played` | RECORD_LEVEL |
| `birth_year` | GENERALIZED: year only, never the DOB |
| `age_band` | DERIVED |
| `is_youth` | DERIVED |
| `primary_division` | RECORD_LEVEL |
| `sex` | RECORD_LEVEL: U kept as its own value |
| `postal_prefix` | GENERALIZED: first 3 characters only |
| `status` | RECORD_LEVEL |
| `resolution_confidence` | RECORD_LEVEL |
| `has_open_integrity_issue` | RECORD_LEVEL |

Explicitly **not** available:

| Column | Why |
|---|---|
| `participant_id` | REPLACED by analyst_key (salted hash) |
| `dob` | GENERALIZED to birth_year |
| `postal_code` | TRUNCATED to postal_prefix |
| `first_name` | DROPPED: direct identifier or quasi-identifier the analyst purpose does not need |
| `last_name` | DROPPED: direct identifier or quasi-identifier the analyst purpose does not need |
| `contact_email` | DROPPED: direct identifier or quasi-identifier the analyst purpose does not need |
| `contact_phone` | DROPPED: direct identifier or quasi-identifier the analyst purpose does not need |
| `source_person_id` | DROPPED: direct identifier or quasi-identifier the analyst purpose does not need |
| `organization_id` | DROPPED: direct identifier or quasi-identifier the analyst purpose does not need |
| `consent_photo` | DROPPED: direct identifier or quasi-identifier the analyst purpose does not need |
| `consent_marketing` | DROPPED: direct identifier or quasi-identifier the analyst purpose does not need |

### ops

**`share_ops__participant`**

| Column | Treatment |
|---|---|
| `participant_id` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `first_name` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `last_name` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `dob` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `birth_year` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `dob_precision` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `sex` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `home_country_code` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `home_region_code` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `contact_email` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `contact_phone` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `is_minor_current` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `consent_photo` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `consent_photo_captured_at` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `consent_photo_season_year` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `consent_marketing` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `consent_marketing_captured_at` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `consent_marketing_season_year` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `first_season` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `last_season` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `seasons_active` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `registration_count` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `source_systems` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `resolution_confidence` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `has_open_integrity_issue` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |

**`share_ops__registration`**

| Column | Treatment |
|---|---|
| `registration_key` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `participant_id` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `source_system` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `source_record_id` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `source_person_id` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `participation_year` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `season_term` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `organization_id` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `organization_name` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `country_code` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `region_code` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `first_name` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `last_name` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `dob` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `birth_year` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `sex` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `contact_email` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `contact_phone` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `postal_code` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `canonical_division` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `age_at_cutoff` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `is_valid_registration` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `invalid_reason` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `link_method` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `match_probability` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `consent_photo` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `consent_marketing` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `registered_at` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |
| `dq_flags` | FULL_IDENTIFIERS: operational need (running leagues, resolving data issues) |

**`share_ops__review_queue`**

| Column | Treatment |
|---|---|
| `priority` | REVIEW_QUEUE: both records side by side for the steward |
| `queue_item_id` | REVIEW_QUEUE: both records side by side for the steward |
| `matcher` | REVIEW_QUEUE: both records side by side for the steward |
| `item_type` | REVIEW_QUEUE: both records side by side for the steward |
| `cluster_id` | REVIEW_QUEUE: both records side by side for the steward |
| `record_a` | REVIEW_QUEUE: both records side by side for the steward |
| `record_b` | REVIEW_QUEUE: both records side by side for the steward |
| `match_probability` | REVIEW_QUEUE: both records side by side for the steward |
| `override_applied` | REVIEW_QUEUE: both records side by side for the steward |
| `suggested_action` | REVIEW_QUEUE: both records side by side for the steward |
| `integrity_issues` | REVIEW_QUEUE: both records side by side for the steward |
| `members` | REVIEW_QUEUE: both records side by side for the steward |
| `feature_levels` | REVIEW_QUEUE: both records side by side for the steward |
| `weight_breakdown` | REVIEW_QUEUE: both records side by side for the steward |
| `reason` | REVIEW_QUEUE: both records side by side for the steward |

### marketing

**`share_marketing__contact_list`**

| Column | Treatment |
|---|---|
| `contact_email` | CONSENTED_CONTACT_ONLY: every participant sharing the address has marketing consent TRUE |
| `contact_role` | DERIVED |
| `contact_first_name` | ADULT_ONLY: filled only for a sole adult player, never a child |
| `country_code` | RECORD_LEVEL |
| `consent_marketing` | ALWAYS_TRUE: row filter, kept for audit |
| `consent_marketing_captured_at` | AUDIT |
| `consent_marketing_season_year` | AUDIT |

Explicitly **not** available:

| Column | Why |
|---|---|
| `first_name` | NEVER: a minor's own details are never shared; for a minor the contact is the guardian |
| `last_name` | NEVER: a minor's own details are never shared; for a minor the contact is the guardian |
| `dob` | NEVER: a minor's own details are never shared; for a minor the contact is the guardian |
| `birth_year` | NEVER: a minor's own details are never shared; for a minor the contact is the guardian |
| `sex` | NEVER: a minor's own details are never shared; for a minor the contact is the guardian |
| `participant_id` | NEVER: a minor's own details are never shared; for a minor the contact is the guardian |
| `contact_phone` | NEVER: a minor's own details are never shared; for a minor the contact is the guardian |
| `postal_code` | NEVER: a minor's own details are never shared; for a minor the contact is the guardian |
| `consent_photo` | NEVER: a minor's own details are never shared; for a minor the contact is the guardian |

### media

**`share_media__roster`**

| Column | Treatment |
|---|---|
| `first_name` | CLEARED_ONLY: consent_photo TRUE; absent means not cleared |
| `last_name` | CLEARED_ONLY: consent_photo TRUE; absent means not cleared |
| `organization_id` | RECORD_LEVEL |
| `organization_name` | RECORD_LEVEL |
| `season_year` | RECORD_LEVEL |
| `season_term` | RECORD_LEVEL |
| `consent_photo` | ALWAYS_TRUE: row filter, kept for audit |

Explicitly **not** available:

| Column | Why |
|---|---|
| `dob` | NEVER: not needed for photo clearance |
| `birth_year` | NEVER: not needed for photo clearance |
| `sex` | NEVER: not needed for photo clearance |
| `participant_id` | NEVER: not needed for photo clearance |
| `contact_email` | NEVER: not needed for photo clearance |
| `contact_phone` | NEVER: not needed for photo clearance |
| `postal_code` | NEVER: not needed for photo clearance |
| `consent_marketing` | NEVER: not needed for photo clearance |

## How the policy is enforced

| Rule | Enforced by |
|---|---|
| Only listed columns exist in a share | `scripts/check_share_policy.py` compares `information_schema.columns` with this policy and fails on any column not explicitly allowed |
| No `select *` in a share model | the same check greps the compiled and source SQL under `models/shares/` |
| No direct identifier in exec or analyst | every share column carries a `meta: pii` tag; the check fails on `direct` in `share_exec` or `share_analyst` |
| Aggregates obey small-cell rules | `share_exec_obeys_suppression_rules` (independent of the suppression macro), `share_exec_derived_rates_follow_their_counts` |
| Only consented contacts are shared | `share_marketing_only_consented_contacts` re-derives eligibility from `dim_participant` |
| Only cleared participants are on the roster | `share_media_only_cleared_participants` re-derives the roster from `dim_participant` and the facts |
| The analyst share has no direct identifiers, names or DOB | `share_analyst_has_no_direct_identifiers`; `share_analyst_k_anonymity_warning` warns about re-identification risk |
