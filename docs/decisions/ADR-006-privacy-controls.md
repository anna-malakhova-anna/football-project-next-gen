# ADR-006: Privacy controls and audience data shares

- **Status:** Accepted (Phase 3)
- **Context:** Different audiences are entitled to different data. In the real world these records are minors' personal data;
  here they are synthetic, which is what lets the controls be built and shown openly. **These are project policies informed by
  regimes such as COPPA, CASL and GDPR, not legal interpretations**, and no legal review has happened.

## Decision

1. **A schema per audience** (`share_exec`, `share_analyst`, `share_ops`, `share_marketing`, `share_media`) because DuckDB has no per-user
   grants. Share models list **explicit columns** only; `select *` is banned and enforced.
2. **A column policy** (`audience_column_policy.csv`) lists every allowed column per share model, with its treatment, and notable
   columns that are explicitly denied. `scripts/check_share_policy.py` compares `information_schema.columns` with it and fails on any
   column not explicitly allowed (tests what is absent), on a denied column, on `select *` in compiled and source SQL, on a stale
   policy, and on a column tagged `pii: direct` in `share_exec` or `share_analyst`. It has unit tests, and was exercised against a
   deliberately added `dob` column in the analyst share: caught three ways.
3. **Consent is enforced at the point of use.** NULL consent is not consent.
   - *Marketing:* a contact address is included only if **every** participant who shares it has marketing consent TRUE. Of 4,770
     addresses, 1,281 qualify. 292 addresses are shared by siblings with mixed answers and are all excluded: a guardian's yes for one
     child is not assumed for the others. Participants in clusters with an open integrity issue are excluded (their consent may belong
     to someone else). For a minor the contact is the guardian; the list carries no child name, date of birth or attribute, and a first
     name appears only for a sole adult player.
   - *Media:* the roster means **cleared**. Only participants whose most recent captured photo consent is TRUE appear; NULL and FALSE
     are both absent.
   Both are tested by re-deriving eligibility independently from `dim_participant`, and the tests were shown to fail when the filters
   were deliberately loosened (292 and 526 violations).

## Pseudonymization (`pseudonymize` macro)

`analyst_key = sha256(participant_id || salt)`; the salt is the environment variable `FLAG_PSEUDO_SALT`, never committed. If unset a
documented **dev-only** default is used so a clean clone runs; a real deployment must set a secret salt. dbt writes compiled SQL with the
salt under `dbt/target/` (gitignored); do not publish it.

**A pseudonym is still personal data.** It stops a direct join to `participant_id` for someone without the salt, but it is
re-identifiable by combining quasi-identifiers (birth year, postal prefix, sex, country). Measured on the analyst share (9,952
participant-year rows):

| Quasi-identifier set | Equivalence classes | Smallest class | Rows in a class of 1 |
|---|---|---|---|
| year, birth year, postal prefix, sex, country | 8,413 | **1** | 7,378 (74%) |
| the same without the postal prefix | 1,267 | **1** | 568 (6%) |

Three quarters of the analyst rows are unique on those five columns. The share is therefore **pseudonymized, not anonymous**, which is
why analyst access still requires a stated purpose, why organization ids are left out, and why `share_analyst_k_anonymity_warning` raises
a visible warning in the build (expected; it should not be silenced). A production analyst share would generalize further (age band
instead of birth year, a coarser region) or add formal k-anonymity.

## Small-cell suppression (`suppress_small_cells` macro)

Applied to every `share_exec` table, on tables built as hierarchies of cells (year -> country -> age band, and so on):

- **Primary:** a count from 1 to `k_min - 1` (`k_min` = 10, from `privacy_params`) becomes NULL, labelled `PRIMARY`.
- **Secondary:** in a group of sibling cells with a published subtotal, if exactly one cell is primary-suppressed, the next smallest
  non-zero cell is also suppressed (`SECONDARY`), so the hidden value cannot be recovered by subtraction. Example: in 2024 the unknown-sex
  count is small, so the smaller of the female and male counts is hidden too.
- **Derived rates** (girls' share, retention) are NULL whenever a component count is small or suppressed, or their row is suppressed.
- **Deliberate deviation from "any count < k_min":** a **zero is not suppressed**. A published zero reveals no individual, and
  suppressing it would, through secondary suppression, hide a headline count (for example `reactivated = 0` would force the new or
  returning count to be hidden). The tests treat 1 to `k_min - 1` as the disclosive range.
- The checker (`suppression_group_violations`) re-derives both rules independently of the macro, and is itself tested against a table
  with known violations.

This is **simplified** disclosure control. A production system would use a statistical disclosure control method such as the
methods in sdcMicro or tau-Argus (cell-suppression optimization, controlled rounding), and would protect against differencing across
separate releases, which this does not.

## Snowflake mapping (design only; not implemented)

| Control here | Snowflake equivalent |
|---|---|
| Schema per audience | roles per audience, with secure views or data shares on a curated schema |
| Column policy seed | masking policies and tag-based masking policies |
| Marketing and media row filters (consent TRUE only) | row access policies |
| `meta: pii` tags on share columns | object tagging (`PII = DIRECT / QUASI / NONE`) |
| `check_share_policy.py` against `information_schema` | tag-reference and `ACCESS_HISTORY` queries, plus policy-reference views |
| `pseudonymize` salt in an environment variable | a secret, or a secure UDF that holds the salt |
| Small-cell suppression macro | a secure view or a governed aggregation layer; or a masking policy that nulls counts below a threshold |

## Consequences

The controls are testable and each is demonstrated to fail when broken. They are **not** engine-enforced: anyone with the warehouse
file can read every schema. The analyst share's re-identification risk is real and measured, and is stated rather than hidden.
