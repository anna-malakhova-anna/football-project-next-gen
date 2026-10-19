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
| **club** | `share_club` | Club market view (Phase 5) | Club market x year aggregates | None: no participant, household, child or record key, no organization id | Aggregates only; primary and secondary small-cell suppression; derived columns hide with the count they come from; reads only approved aggregate marts |
| **privacy** | `share_privacy` | Privacy and compliance review (Phase 5) | Aggregates and configuration | None | Aggregates only: consent provenance, purpose coverage, minimization risk, retention versus deletion, share-policy results, analyst-share k-anonymity |
| **media** | `share_media` | Photo and video clearance | Roster | Name, organization, season | Only participants whose most recent captured photo consent is TRUE; the list means cleared, anyone absent is NOT cleared, including NULL; clusters with an open integrity issue excluded |

## What each share contains

### exec

**`share_exec__acquisition_incrementality`**

| Column | Treatment |
|---|---|
| `methodology_version` | DIMENSION |
| `incremental_fan_accounts` | AGGREGATE_SUPPRESSED |
| `incremental_fan_accounts_ci_low` | AGGREGATE_SUPPRESSED |
| `incremental_fan_accounts_ci_high` | AGGREGATE_SUPPRESSED |
| `net_new_linked_households` | AGGREGATE_SUPPRESSED |
| `net_new_households_scaled` | AGGREGATE_SUPPRESSED |
| `market_years_compared` | AGGREGATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |
| `caveat` | CAVEAT_LABEL |
| `participant_households_compared` | AGGREGATE_SUPPRESSED |
| `incremental_fan_accounts_per_100_households` | DERIVED_RATE_SUPPRESSED |
| `incremental_fan_accounts_per_100_households_ci_low` | DERIVED_RATE_SUPPRESSED |
| `incremental_fan_accounts_per_100_households_ci_high` | DERIVED_RATE_SUPPRESSED |

**`share_exec__addressable_audience`**

| Column | Treatment |
|---|---|
| `month` | DIMENSION |
| `household_group` | DIMENSION |
| `audience_registered` | AGGREGATE_SUPPRESSED |
| `audience_linked` | AGGREGATE_SUPPRESSED |
| `audience_contactable` | AGGREGATE_SUPPRESSED |
| `audience_contactable_email` | AGGREGATE_SUPPRESSED |
| `audience_contactable_sms` | AGGREGATE_SUPPRESSED |
| `audience_contactable_push` | AGGREGATE_SUPPRESSED |
| `audience_active` | AGGREGATE_SUPPRESSED |
| `consent_gap_households` | AGGREGATE_SUPPRESSED |
| `contactable_share_of_linked` | DERIVED_RATE_SUPPRESSED |
| `consent_gap_share_of_active` | DERIVED_RATE_SUPPRESSED |
| `consent_gap_value` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__consent_capture`**

| Column | Treatment |
|---|---|
| `consent_cut` | DIMENSION |
| `consent_dimension_value` | DIMENSION |
| `consent_channel` | DIMENSION |
| `consent_lines` | AGGREGATE_SUPPRESSED |
| `consent_opt_ins` | AGGREGATE_SUPPRESSED |
| `consent_opt_in_rate` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__fan_engagement_effect`**

| Column | Treatment |
|---|---|
| `estimator` | DIMENSION |
| `fan_uplift_pct` | DERIVED_RATE_SUPPRESSED |
| `fan_uplift_ci_low_pct` | DERIVED_RATE_SUPPRESSED |
| `fan_uplift_ci_high_pct` | DERIVED_RATE_SUPPRESSED |
| `fan_treated_households` | AGGREGATE_SUPPRESSED |
| `fan_match_rate` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |
| `caveat` | CAVEAT_LABEL |

**`share_exec__fan_funnel`**

| Column | Treatment |
|---|---|
| `cohort_year` | DIMENSION |
| `segment` | DIMENSION |
| `fan_status` | DIMENSION |
| `funnel_households` | AGGREGATE_SUPPRESSED |
| `funnel_linked` | AGGREGATE_SUPPRESSED |
| `funnel_contactable` | AGGREGATE_SUPPRESSED |
| `funnel_active` | AGGREGATE_SUPPRESSED |
| `funnel_monetized` | AGGREGATE_SUPPRESSED |
| `funnel_link_rate` | DERIVED_RATE_SUPPRESSED |
| `funnel_contactable_rate` | DERIVED_RATE_SUPPRESSED |
| `funnel_active_rate` | DERIVED_RATE_SUPPRESSED |
| `funnel_monetized_rate` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__fan_rfm`**

| Column | Treatment |
|---|---|
| `year` | DIMENSION |
| `fan_group` | DIMENSION |
| `segment` | DIMENSION |
| `rfm_accounts` | AGGREGATE_SUPPRESSED |
| `rfm_share` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__fan_survival`**

| Column | Treatment |
|---|---|
| `fan_group` | DIMENSION |
| `months_since_origin` | DIMENSION |
| `survival_at_risk` | AGGREGATE_SUPPRESSED |
| `fan_survival` | DERIVED_RATE_SUPPRESSED |
| `fan_survival_ci_low` | DERIVED_RATE_SUPPRESSED |
| `fan_survival_ci_high` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__fan_value`**

| Column | Treatment |
|---|---|
| `fan_group` | DIMENSION |
| `value_accounts` | AGGREGATE_SUPPRESSED |
| `net_spend_per_active_month` | DERIVED_RATE_SUPPRESSED |
| `expected_active_months` | DERIVED_RATE_SUPPRESSED |
| `fan_ltv` | DERIVED_RATE_SUPPRESSED |
| `fan_ltv_low` | DERIVED_RATE_SUPPRESSED |
| `fan_ltv_high` | DERIVED_RATE_SUPPRESSED |
| `horizon_months` | DIMENSION |
| `currency_label` | DIMENSION |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__fan_value_uplift`**

| Column | Treatment |
|---|---|
| `uplift_status_group` | DIMENSION |
| `uplift_outcome` | DIMENSION |
| `uplift_outcome_kind` | DIMENSION |
| `uplift_households` | AGGREGATE_SUPPRESSED |
| `uplift_per_month` | DERIVED_RATE_SUPPRESSED |
| `uplift_ci_low_per_month` | DERIVED_RATE_SUPPRESSED |
| `uplift_ci_high_per_month` | DERIVED_RATE_SUPPRESSED |
| `uplift_pct` | DERIVED_RATE_SUPPRESSED |
| `uplift_naive_pct` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__household_link_rate`**

| Column | Treatment |
|---|---|
| `country_code` | DIMENSION |
| `program_households` | AGGREGATE_SUPPRESSED |
| `linked_households` | AGGREGATE_SUPPRESSED |
| `household_link_rate` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__market_quadrants`**

| Column | Treatment |
|---|---|
| `market_id` | DIMENSION |
| `market_name` | DIMENSION |
| `country_code` | DIMENSION |
| `quadrant` | DIMENSION |
| `is_team_market` | DIMENSION |
| `launch_year` | DIMENSION |
| `household_population` | DIMENSION |
| `markets_in_row` | DIMENSION |
| `participant_households` | AGGREGATE_SUPPRESSED |
| `fan_accounts` | AGGREGATE_SUPPRESSED |
| `participation_per_1000` | DERIVED_RATE_SUPPRESSED |
| `fan_accounts_per_1000` | DERIVED_RATE_SUPPRESSED |
| `net_new_rate` | DERIVED_RATE_SUPPRESSED |
| `link_rate` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__participation_bounds`**

| Column | Treatment |
|---|---|
| `participation_year` | DIMENSION |
| `identity_participants_low` | DERIVED_RATE_SUPPRESSED |
| `identity_participants_point` | AGGREGATE_SUPPRESSED |
| `identity_participants_high` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

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

**`share_exec__reported_headcount`**

| Column | Treatment |
|---|---|
| `participation_year` | DIMENSION |
| `country_code` | DIMENSION |
| `reporting_programs` | AGGREGATE_SUPPRESSED |
| `reported_headcount` | DERIVED_RATE_SUPPRESSED |
| `voluntary_program_headcount` | DERIVED_RATE_SUPPRESSED |
| `combined_reach_low` | DERIVED_RATE_SUPPRESSED |
| `combined_reach_high` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__retention_cohorts`**

| Column | Treatment |
|---|---|
| `entry_year` | DIMENSION |
| `years_since_entry` | DIMENSION |
| `entry_cohort_size` | AGGREGATE_SUPPRESSED |
| `cohort_retention_pct` | DERIVED_RATE_SUPPRESSED |
| `cohort_retention_among_eligible_pct` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__retention_survival`**

| Column | Treatment |
|---|---|
| `segment_type` | DIMENSION |
| `segment_value` | DIMENSION |
| `years_since_entry` | DIMENSION |
| `entry_cohort_size` | AGGREGATE_SUPPRESSED |
| `km_at_risk` | AGGREGATE_SUPPRESSED |
| `km_survival` | DERIVED_RATE_SUPPRESSED |
| `km_survival_ci_low` | DERIVED_RATE_SUPPRESSED |
| `km_survival_ci_high` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_exec__roadmap_gates`**

| Column | Treatment |
|---|---|
| `gate_id` | DIMENSION |
| `product_id` | DIMENSION |
| `kind` | DIMENSION |
| `definition` | DIMENSION |
| `plain_name` | DIMENSION |
| `comparison` | DIMENSION |
| `target` | DIMENSION |
| `unit` | DIMENSION |
| `baseline_2025` | DIMENSION |
| `gate_for` | DIMENSION |
| `source_model` | DIMENSION |
| `source_field` | DIMENSION |
| `current_value` | DERIVED |
| `status` | DIMENSION |
| `bar_fill_pct` | DERIVED |
| `target_marker_pct` | DIMENSION |
| `n_gates` | DERIVED |
| `n_met` | DERIVED |
| `blocking_gate_plain` | DIMENSION |
| `status_text` | DIMENSION |
| `value_text` | DIMENSION |

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

**`share_analyst__fan_acquisition_event_study`**

| Column | Treatment |
|---|---|
| `years_since_launch` | DIMENSION |
| `launch_cohorts` | DIMENSION |
| `acquisition_treated_markets` | AGGREGATE_SUPPRESSED |
| `acquisition_effect_per_1000` | DERIVED_RATE_SUPPRESSED |
| `acquisition_effect_se` | DERIVED_RATE_SUPPRESSED |
| `acquisition_effect_ci_low` | DERIVED_RATE_SUPPRESSED |
| `acquisition_effect_ci_high` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_analyst__fan_event_study`**

| Column | Treatment |
|---|---|
| `months_since_event` | DIMENSION |
| `fan_treated_households` | AGGREGATE_SUPPRESSED |
| `fan_treated_mean_events` | DERIVED_RATE_SUPPRESSED |
| `fan_comparison_mean_events` | DERIVED_RATE_SUPPRESSED |
| `fan_event_study_effect_pct` | DERIVED_RATE_SUPPRESSED |
| `fan_event_study_diff_se` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_analyst__fan_market_year`**

| Column | Treatment |
|---|---|
| `market_id` | DIMENSION |
| `country_code` | DIMENSION |
| `is_team_market` | DIMENSION |
| `launch_year` | DIMENSION |
| `panel_year` | DIMENSION |
| `household_population` | DIMENSION |
| `market_new_accounts` | AGGREGATE_SUPPRESSED |
| `market_new_accounts_per_1000` | DERIVED_RATE_SUPPRESSED |
| `market_is_treated` | DIMENSION |
| `suppressed` | SUPPRESSION_FLAG |

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

**`share_ops__league_fix_list`**

| Column | Treatment |
|---|---|
| `season_year` | AGGREGATE_BY_ORGANIZATION |
| `source_system` | AGGREGATE_BY_ORGANIZATION |
| `org_id` | AGGREGATE_BY_ORGANIZATION |
| `org_name` | AGGREGATE_BY_ORGANIZATION |
| `fix_rank` | AGGREGATE_BY_ORGANIZATION |
| `is_systemic` | AGGREGATE_BY_ORGANIZATION |
| `rule_id` | AGGREGATE_BY_ORGANIZATION |
| `problem_plain` | AGGREGATE_BY_ORGANIZATION |
| `what_to_do_plain` | AGGREGATE_BY_ORGANIZATION |
| `records_affected` | AGGREGATE_BY_ORGANIZATION |
| `records_basis` | AGGREGATE_BY_ORGANIZATION |
| `suppressed` | AGGREGATE_BY_ORGANIZATION |

**`share_ops__league_scorecard`**

| Column | Treatment |
|---|---|
| `season_year` | AGGREGATE_BY_ORGANIZATION |
| `source_system` | AGGREGATE_BY_ORGANIZATION |
| `org_id` | AGGREGATE_BY_ORGANIZATION |
| `org_name` | AGGREGATE_BY_ORGANIZATION |
| `channel` | AGGREGATE_BY_ORGANIZATION |
| `purpose` | AGGREGATE_BY_ORGANIZATION |
| `score` | AGGREGATE_BY_ORGANIZATION |
| `grade` | AGGREGATE_BY_ORGANIZATION |
| `record_count` | AGGREGATE_BY_ORGANIZATION |
| `reported` | AGGREGATE_BY_ORGANIZATION |
| `limiting_dimension` | AGGREGATE_BY_ORGANIZATION |
| `top_problems_plain` | AGGREGATE_BY_ORGANIZATION |

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

### club

**`share_club__activation_funnel`**

| Column | Treatment |
|---|---|
| `participation_year` | DIMENSION |
| `club_market_id` | DIMENSION |
| `step_no` | DIMENSION |
| `step` | DIMENSION |
| `unit` | DIMENSION |
| `funnel_count` | AGGREGATE_SUPPRESSED |
| `funnel_lost_dq` | AGGREGATE_SUPPRESSED |
| `funnel_lost_privacy` | AGGREGATE_SUPPRESSED |
| `loss_type` | DIMENSION |
| `suppressed` | SUPPRESSION_FLAG |

**`share_club__chart_insights`**

| Column | Treatment |
|---|---|
| `chart_id` | DIMENSION |
| `lens` | DIMENSION |
| `field` | DIMENSION |
| `value_display` | DIMENSION |
| `value_raw` | AGGREGATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_club__market_missingness`**

| Column | Treatment |
|---|---|
| `club_market_id` | DIMENSION |
| `participation_year` | DIMENSION |
| `youth_participants_in_cell` | AGGREGATE_SUPPRESSED |
| `unknown_gender_participants` | AGGREGATE_SUPPRESSED |
| `girls_share_known_only` | DERIVED_RATE_SUPPRESSED |
| `girls_share_bound_low` | DERIVED_RATE_SUPPRESSED |
| `girls_share_bound_high` | DERIVED_RATE_SUPPRESSED |
| `missingness_verdict` | DIMENSION |
| `suppressed` | SUPPRESSION_FLAG |

**`share_club__market_year`**

| Column | Treatment |
|---|---|
| `club_market_id` | DIMENSION |
| `market_name` | DIMENSION |
| `participation_year` | DIMENSION |
| `participants_allocated` | AGGREGATE_SUPPRESSED |
| `youth_participants_allocated` | AGGREGATE_SUPPRESSED |
| `orgs_known` | AGGREGATE_SUPPRESSED |
| `orgs_reporting` | AGGREGATE_SUPPRESSED |
| `orgs_dark` | AGGREGATE_SUPPRESSED |
| `participants_not_reported_estimate` | AGGREGATE_SUPPRESSED |
| `participants_allocated_interval_low` | AGGREGATE_SUPPRESSED |
| `participants_allocated_interval_high` | AGGREGATE_SUPPRESSED |
| `pct_records_geo_fit` | DERIVED_RATE_SUPPRESSED |
| `grade_count` | DIMENSION |
| `grade_segment` | DIMENSION |
| `grade_geo` | DIMENSION |
| `grade_retain` | DIMENSION |
| `grade_activate` | DIMENSION |
| `denominator_status` | DIMENSION |
| `participation_rate` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

### privacy

**`share_privacy__analyst_k_anonymity`**

| Column | Treatment |
|---|---|
| `participation_year` | DIMENSION |
| `participant_years` | AGGREGATE_SUPPRESSED |
| `equivalence_classes` | AGGREGATE_SUPPRESSED |
| `smallest_class` | AGGREGATE_SUPPRESSED |
| `average_class_size` | DERIVED_RATE_SUPPRESSED |
| `pct_unique` | DERIVED_RATE_SUPPRESSED |
| `pct_rows_below_k_warn` | DERIVED_RATE_SUPPRESSED |
| `pct_rows_below_k_min` | DERIVED_RATE_SUPPRESSED |

**`share_privacy__chart_insights`**

| Column | Treatment |
|---|---|
| `chart_id` | DIMENSION |
| `lens` | DIMENSION |
| `field` | DIMENSION |
| `value_display` | DIMENSION |
| `value_raw` | AGGREGATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_privacy__consent_provenance`**

| Column | Treatment |
|---|---|
| `participation_year` | DIMENSION |
| `source_system` | DIMENSION |
| `consent_text_version` | DIMENSION |
| `provenance_grade` | DIMENSION |
| `consent_events` | AGGREGATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_privacy__conversion_funnel_by_tier`**

| Column | Treatment |
|---|---|
| `age_tier` | DIMENSION |
| `step_no` | DIMENSION |
| `step` | DIMENSION |
| `kind` | DIMENSION |
| `tier_funnel_households` | AGGREGATE_SUPPRESSED |
| `share_of_registered` | DERIVED_RATE_SUPPRESSED |
| `suppressed` | SUPPRESSION_FLAG |

**`share_privacy__minimization_frontier`**

| Column | Treatment |
|---|---|
| `variant_id` | DIMENSION |
| `variant_label` | DIMENSION |
| `participant_years` | AGGREGATE_SUPPRESSED |
| `pct_unique` | DERIVED_RATE_SUPPRESSED |
| `pct_rows_below_k_min` | DERIVED_RATE_SUPPRESSED |
| `smallest_class` | AGGREGATE_SUPPRESSED |
| `average_class_size` | DERIVED_RATE_SUPPRESSED |
| `contact_fields_held` | AGGREGATE_SUPPRESSED |
| `fit_for_count` | DERIVED_RATE_SUPPRESSED |
| `fit_for_segment` | DERIVED_RATE_SUPPRESSED |
| `fit_for_geo` | DERIVED_RATE_SUPPRESSED |
| `fit_for_retain` | DERIVED_RATE_SUPPRESSED |
| `fit_for_activate` | DERIVED_RATE_SUPPRESSED |
| `rules_no_longer_evaluable` | AGGREGATE_SUPPRESSED |

**`share_privacy__policy_checks`**

| Column | Treatment |
|---|---|
| `check_name` | DIMENSION |
| `violations` | VALUE |
| `columns_checked` | VALUE |
| `share_tables_checked` | VALUE |

**`share_privacy__purpose_coverage`**

| Column | Treatment |
|---|---|
| `consent_text_version` | DIMENSION |
| `purpose` | DIMENSION |
| `purpose_label` | DIMENSION |
| `form_names_purpose` | DIMENSION |
| `separate_consent_required` | DIMENSION |
| `counts_for_club_activation` | DIMENSION |

**`share_privacy__retention_vs_deletion`**

| Column | Treatment |
|---|---|
| `metric` | DIMENSION |
| `metric_label` | DIMENSION |
| `baseline` | VALUE |
| `facts_only` | VALUE |
| `identity_rebuilt` | VALUE |
| `facts_only_change` | VALUE |
| `identity_rebuilt_change` | VALUE |
| `survives_facts_only` | DIMENSION |
| `survives_identity_rebuilt` | DIMENSION |
| `tolerance` | VALUE |

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
| No direct or quasi-identifying column in the club and privacy shares; the club share reads only approved aggregate marts; every metric column is in the catalog | `scripts/check_share_policy.py` (QUASI_IN_CLUB_PRIVACY, CLUB_LINEAGE, METRIC_NOT_IN_CATALOG); `share_club_obeys_suppression_rules` re-derives the suppression independently |
| The analyst share has no direct identifiers, names or DOB | `share_analyst_has_no_direct_identifiers`; `share_analyst_k_anonymity_warning` warns about re-identification risk |
