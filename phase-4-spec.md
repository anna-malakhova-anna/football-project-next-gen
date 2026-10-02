# Counting Flag Football — Phase 4 Spec: Outcomes, Scale & Showcase

**Phase 4 goal:** Prove three things, then package the project so a hiring manager understands it in five minutes.
1. **Scale:** New partner sources can be onboarded through a repeatable, contract-driven process, not one-off code.
2. **Retention:** Who keeps playing, who leaves, and when, measured correctly (censoring, age-outs).
3. **Fandom outcomes:** Does playing flag football connect to fan engagement? Measured honestly, with a method that beats the naive comparison and is validated against a known synthetic effect.
4. **Showcase:** A static results site, a polished README, CI, and a demo script.

**Builds on:** Phases 1–3 (facts, marts, shares, scorecard, publish/restatement, memo v1.0).

---

## 0. Pre-flight

1. Run `make phase3`. All tests, the eval-isolation check, and the share-policy check must pass.
2. Confirm Anna has written the memo prose (Phase 3 DoD). If any `<!-- DRAFT -->` markers remain, **stop and flag it.** Phase 4 bumps the methodology to v1.1, and that change should be made to a finished v1.0.
3. Publish the current scorecard for every year (`make publish`) so Phase 4 changes show up in the restatement log.
4. Read the actual Phase 1–3 model names and use them. Record any deviations in `ADR-008`.

---

## 1. Principles

1. **Onboard through the front door.** The two new sources are added **only** by following the playbook written in step 1 of the build order. Friction found along the way gets fixed in the playbook, not worked around.
2. **Contracts before code.** Every source has a data contract. Raw data is validated against it, and violations are logged rather than silently fixed.
3. **Censoring is not churn.** Players who age out, and players in the final observed year, are censored, not counted as lost.
4. **Association is not effect.** The fan analysis reports the naive comparison, a better-designed estimate, and (in evaluation only) the true synthetic effect, side by side.
5. **Household, not child.** Fan accounts belong to adults. The fan analysis is about **households**, and it says so.
6. **Every public number comes from `share_exec`.** The results site uses the same suppressed, versioned outputs as the exec report.

---

## 2. Data window extension (do first, after pre-flight)

Three seasons are too thin for retention curves. Extend the generator to **2021–2025** (five participation years).
- 2021 becomes the left-censored year (it inherits the Phase 3 rule that applied to 2023). Make the censored year **config-driven** (`first_observed_year`), not hardcoded. Grep for literal `2023` and replace it.
- Keep the churn and girls' growth dynamics from Phase 1, applied across five years.
- Rebuild end to end. All Phase 1–3 tests must pass unchanged, apart from expected-value updates in the defect-rate checks.
- The restatement log should now flag previously published years with `NEW_SOURCE_DATA` (the regenerated data changed them). **Capture this output** as a second restatement example in `docs/reports/restatement_demo.md`.

Treat this as a robustness test. If extending the window breaks anything beyond expected-value updates, that's a defect to fix and document.

---

## 3. Source onboarding playbook and data contracts

### 3.1 `docs/playbook/onboard-a-source.md`
Written **before** onboarding sources D and E. Stages map to the inventory statuses:

| Stage | Exit criteria | Artifacts |
|---|---|---|
| **Discovery** | Owner named, purpose stated, legal basis and consent fields identified, minors-present flag set | Inventory row, contract draft |
| **Profiling** | Raw sample loaded, `dq_source_profile` run, issues listed | Profile output, issue list |
| **Contracted** | Contract agreed (schema, grain, keys, refresh, PII classes, quality thresholds) | `contracts/<source>.yml` |
| **Staged** | Staging model + tests pass; contract validation passes or violations are accepted with a reason | Staging model, tests |
| **Modelled** | Integrated into identity resolution and/or facts; evaluation is re-run | Updated eval results |
| **Production** | Included in published scorecard; methodology updated if counting changes | Publish + CHANGELOG entry |

Include a RACI per stage (partner, data lead, data engineering, privacy, analytics) and a checklist that can be copied into an issue.

### 3.2 `contracts/*.yml`
One per source, **including retrofitted contracts for sources A–C**. Fields:
- `source_system`, `owner_role`, `partner_type`, `delivery` (format, mechanism, cadence)
- `grain`, `primary_key`, `person_identifier` (quality level)
- `schema`: column, type, required, allowed values / pattern, `pii` class
- `quality`: thresholds per rule (e.g. max null rate for `dob` 5%, max duplicate rate 2%)
- `consent_fields` and what each permits
- `minors_present`
- `version` and `effective_date`

### 3.3 Contract validation
- `scripts/validate_contracts.py` generates dbt tests from the contracts, or a macro does it. Either way, validation runs against **raw** tables.
- Results go to `dq_contract_results` (source, rule, threshold, observed, status, run_at).
- Threshold breaches: `WARN` by default, `ERROR` for PII or consent rules (e.g. a consent column missing entirely).
- Add `contract_status` and `contract_version` to `source_inventory.md`.

### 3.4 Onboarding log
For each new source, keep `docs/playbook/onboarding_log_<source>.md`, recording stage dates, issues found, playbook changes made, and decisions. **Playbook changes go in the playbook's own changelog.** "The playbook improved while being used" is a story worth telling.

---

## 4. Source D — fan engagement feed

### 4.1 Generation
- **Accounts:** fan app/ticketing accounts. Holders are adults: guardians of participants, adult players, and a larger population of **non-participant fan households** (~3× the participant household count) in the same regions.
- **Format:** JSON Lines event stream, partitioned by month: `data/raw/fan/events_YYYY_MM.jsonl`, plus an accounts snapshot `fan_accounts.csv`
- **Account fields:** `account_id`, `email`, `phone` (optional), `postal_prefix`, `country`, `created_at`, `marketing_opt_in`
- **Event types:** `app_open`, `content_view`, `game_stream`, `ticket_purchase`, `merch_purchase`, `newsletter_click`. Event fields: `event_id`, `account_id`, `event_type`, `event_ts`, `value` (purchase amount for purchase events)

### 4.2 Built-in causal structure (for evaluation)
Generate engagement with **known parameters** in `config/generation.yaml`:
- **Baseline engagement** varies by household (a latent "fandom" score)
- **Selection:** households with higher latent fandom are **more likely to enroll** a child. This is what makes the naive comparison overstate the effect.
- **True effect:** after a household's first registration, engagement rises by a configured `true_uplift` (e.g. +15% events per month), decaying if the child churns
- **Seasonality:** an NFL-season peak (autumn into winter), applied to all households

Write the latent score, enrollment propensity, and true uplift to `data/ground_truth/fan_truth.parquet`. **Never loaded outside `eval`.**

### 4.3 Defects
- Account email differs from the registration guardian email: 25% of participant households. This caps the linkage rate, deliberately.
- Duplicate events (same `event_id` delivered twice): 0.5%
- Late-arriving events (land in a later month's file): 2%
- Clock skew on `event_ts`: 1%

### 4.4 Linkage (participant household → fan account)
- Model `int_household`: group participants by normalized guardian contact (email/phone) from `fct_registration`. Adult players form their own households.
- `link_household_fan_account`: deterministic links on normalized email, then phone. No fuzzy matching. It's a different risk profile, and ADR-009 explains why.
- Report the **link rate** and its bias: linked households differ from unlinked ones. Compare them on region, years active, and number of children.
- Evaluation: precision and recall of household linkage against ground truth.

### 4.5 Governance decision: may we link these at all? (ADR-009)
The linkage uses registration data for a purpose beyond running leagues. The ADR must:
- State the purpose (aggregate program-impact analysis) and the policy position taken for this project (e.g. aggregate analytics in a restricted zone under a legitimate-interest-style rationale), clearly marked as **project policy, not legal advice**.
- Implement it as follows: linkage happens in a restricted `linkage` schema; only **aggregated, suppressed** outputs reach `share_exec` / `share_analyst`; nothing linked reaches `share_marketing` unless `consent_marketing = TRUE` on **both** sides.
- Describe the alternative (an explicit research/analytics consent field at registration) and what it would cost in coverage.
- Add a `<!-- DECISION: Anna -->` marker. **Anna makes the final call**; Claude Code implements the default above until then.

---

## 5. Source E — school and rec program aggregate headcounts

### 5.1 Generation
- **Format:** CSV per year, `data/raw/school/headcounts_YYYY.csv`
- **Grain:** program × year (no individuals)
- **Columns:** `district`, `school_or_program`, `country`, `region`, `program_type` (`PE_UNIT`, `INTRAMURAL`, `AFTER_SCHOOL`), `grade_band`, `girls_count`, `boys_count`, `total_count`, `reported_by`, `report_date`
- **Built-in overlap:** some of these kids are also registered participants. The overlap rate is written to ground truth.
- **Defects:** `total ≠ girls + boys` (8%), missing grade band (5%), the same program reported twice by different reporters (3%), and suspiciously round numbers (`100`, `250`) at 10%

### 5.2 Treatment: methodology v1.1
- New fact `fct_reported_headcount` (program × year), deduplicated across reporters, with `dq_flags`
- **Never added to resolved participants.** The scorecard gets a new KPI, **Reported program headcount (not deduplicated)**, shown as a separate line.
- **Overlap range:** report `combined_reach_low = max(resolved, headcount)` and `combined_reach_high = resolved + headcount`. In plain words: total reach lies somewhere between those two numbers. No point estimate, since there's no way to deduplicate aggregates.
- Evaluation only: where the true overlap falls in that range
- Also distinguish `PE_UNIT` (exposure during class) from voluntary programs. They are different kinds of participation, and the memo says so. Exposure can be reported, but it is never called "players".

### 5.3 Methodology bump
- Update the memo to **v1.1**: add a section on reported headcounts and combined reach. Claude Code drafts the factual changes with DRAFT markers; Anna edits.
- CHANGELOG entry
- Publish → the restatement log should show `METHODOLOGY_CHANGE` for KPIs whose definitions changed. Capture this as the third restatement example.

---

## 6. Retention analytics

All in SQL, from `fct_participant_year`.

### 6.1 Definitions (add to `metric_catalog.csv`)
- **Entry cohort:** first observed participation year (excluding the censored first year)
- **Retained in year t+k:** a valid registration in year t+k
- **Churn event:** no registration in year t+1 **and** still youth-eligible in t+1. Players who don't return as adults after ageing out are separate.
- **Age-out:** the participant was 17 in year t → **censored** for youth retention, not churned. Adult continuation is tracked as its own metric ("youth-to-adult transition rate").
- **Right censoring:** the last observed year has unknown follow-up → censored
- **Reactivation:** already defined in Phase 3. The survival analysis treats the first gap as the event, and reactivation is reported separately.

### 6.2 Models
- `mart_retention_cohorts`: cohort × years-since-entry, with active count and retention % (a classic triangle), by country (attributed) and sex.
- `mart_retention_survival`: **Kaplan–Meier** survival by segment, computed in SQL:
  - At each year since entry: number at risk, churn events, censored
  - `S(t) = Π (1 − events / at_risk)` via `exp(sum(ln(...))) over (order by t)`
  - Include Greenwood standard errors and 95% CIs (also in SQL)
  - Segments: sex, entry age band, entry country, multi-org in entry year, entry division
- `mart_retention_transitions`: division-to-division flow year over year (playing up, steady, aging forward), plus youth-to-adult transitions
- `mart_retention_drivers`: descriptive one-year retention rates by segment, with counts and CIs. **No causal language.** Optional stretch: a logistic regression in Python reading `share_analyst`, with coefficients reported as associations.

### 6.3 Evaluation
`eval_retention`: compares KM curves against the generator's true churn parameters per segment. Then **deliberately computes a naive version** that counts age-outs as churn, and shows how much it understates retention for older entrants. That comparison is the reason the censoring rules exist, so show it.

---

## 7. Fandom outcomes analysis

Grain: **household-month**, for linked households and non-participant fan households.

### 7.1 Models (in the `linkage` schema)
- `fct_household_engagement_month`: household × month, with event counts by type, purchases, spend. Deduplicate events by `event_id`, and assign late arrivals to the correct month by `event_ts`.
- `int_participant_household_timeline`: first registration month, active periods, churn month
- `mart_fan_naive`: average engagement of participant households versus non-participant fan households over the same months. **This is the wrong answer, and it's computed on purpose.**
- `mart_fan_did`: **difference-in-differences** with matched comparisons:
  - Each participant household's "event time" = its first registration month
  - Comparison households are matched by **coarsened exact matching** in SQL, on region, account tenure band, **pre-period engagement band** (the 12 months before event time), and calendar month of event time
  - Comparison households get a pseudo event time equal to their matched participant's
  - Uplift = (post − pre for participants) − (post − pre for matched comparisons)
  - Event-study version: the effect by month relative to event time (−12 to +18), so pre-trends are **visible**. A flat pre-period supports the design.
- `mart_fan_outcomes_summary`: naive estimate, DiD estimate, CI (bootstrap in Python reading `share_analyst` aggregates, or analytic SEs in SQL; pick one and document it), match rate, and number of households matched

### 7.2 Evaluation
`eval_fan_effect`: `true_uplift` versus the naive and DiD estimates. Expected result: naive is badly inflated, DiD is close. If DiD is far off, investigate (matching quality, pre-trends) and document it. **Do not tune the design against the truth.** Record what was tried in ADR-010.

### 7.3 Exposure in shares
- `share_exec`: the summary with suppression applied, plus a one-line caveat column
- `share_analyst`: the event-study series at aggregate level
- Nothing household-level leaves the `linkage` schema. Add a policy check for this.

---

## 8. Showcase

### 8.1 Results site (`site/`)
A static site generated by `scripts/build_site.py` from `share_exec` exports plus evaluation summaries (clearly labelled as such). Deployable to GitHub Pages. Vega-Lite or Chart.js is fine, but **no number may be computed in JavaScript.**

Pages:
1. **Overview:** what this is, why the data is synthetic, the architecture diagram, and a "5-minute tour" path
2. **Participation:** global trend with identity bounds, attributed vs presence country views, girls' share trend, and combined reach range
3. **Identity:** threshold sweep chart, rules vs probabilistic comparison, sibling/twin merges, error categories
4. **Retention:** KM curves by segment with CIs, cohort triangle, and the naive-vs-censored comparison
5. **Fandom:** naive vs DiD vs true uplift, plus the event-study chart with its pre-period
6. **Governance:** audience matrix, suppression example, contract status per source, restatement examples, and links to ADRs and the memo

Each chart has a one-sentence "what this shows" and a one-sentence "what it doesn't show."

### 8.2 README rewrite
- One-paragraph pitch, with the link to the site first
- Architecture diagram (Mermaid): sources → contracts → raw → staging → identity → facts → marts → shares → site
- Results table (from `make eval` and the scorecard)
- "Design decisions" list linking each ADR, one line each
- "If this were real": Snowflake + dbt Cloud, orchestration, partner contracts as a governance process, a persisted ID registry, real access control (from ADR-006), attendance data
- How to run: `make all-phases`

### 8.3 CI
GitHub Actions on push: setup → `make all-phases` (including isolation, share policy, and contract checks) → build the site → deploy Pages on `main`. Cache the uv environment. It must finish in under 10 minutes.

### 8.4 `docs/demo_script.md`
A 5-minute and a 15-minute walkthrough for interviews: what to show, in what order, the one question each section answers, and the likely follow-up questions with where the answer lives. **Claude Code drafts the structure; Anna writes the talking points.**

---

## 9. Tests (additions)

- Contract validation runs for all five sources; any `ERROR` status fails the build
- `fct_household_engagement_month`: no duplicate `event_id` counted; late events land in the month of `event_ts`
- `fct_reported_headcount` is never joined into participant counts (lineage check: no path from it to `fct_participant_year` or the participant KPIs)
- `combined_reach_low ≤ combined_reach_high`; `combined_reach_low ≥ resolved participants`
- KM: `S(t)` is non-increasing, and 0 ≤ S ≤ 1. At-risk at t+1 = at-risk at t − events − censored.
- Age-outs are never counted as churn events
- Matched DiD: every matched participant household has ≥1 comparison; matching variables are identical within strata
- Nothing from the `linkage` schema appears in any share except via approved aggregate models (extend `check_share_policy.py`)
- Isolation check covers `fan_truth` and the overlap truth
- Site build fails if any chart's data file isn't sourced from `share_exec` or a whitelisted evaluation summary
- The censored year comes from config: no literal year values remain in models (grep check)

---

## 10. Build order for Claude Code

1. Pre-flight (section 0). **Pause for Anna** if memo DRAFT markers remain.
2. Data window extension to 2021–2025; full rebuild; capture the restatement output
3. Write the playbook + retrofit contracts for A–C + contract validation
4. **Onboard Source E** (simpler, aggregate) by following the playbook; keep the onboarding log; methodology v1.1 draft; publish → restatement
5. Retention: definitions → cohorts → KM → transitions → drivers → `eval_retention`. **Print the KM vs truth and naive comparison, and pause for Anna.**
6. **Onboard Source D** by following the playbook. Generation → contract → staging → households → linkage. ADR-009 with the DECISION marker. **Pause for Anna's decision.**
7. Fan models: engagement month → timeline → naive → matched DiD → event study → summary → `eval_fan_effect`. **Print the naive vs DiD vs true comparison, and pause for Anna.**
8. Shares and policy-check extensions
9. Site build
10. README, ADR-008/009/010, demo script skeleton, inventory updates
11. CI

Stop after each step and confirm it runs and tests pass.

**If time runs short, cut in this order:** retention drivers stretch → transitions → event study (keep the DiD point estimate) → the Governance site page (link to docs instead). Never cut: censoring, the naive-vs-better comparisons, contracts, or the linkage governance decision.

---

## 11. Phase 4 definition of done

- [ ] Five years of data; all earlier tests pass; the censored year is config-driven
- [ ] Playbook written first; both new sources onboarded through it, with onboarding logs and playbook changelog entries
- [ ] Contracts for all five sources; validation in the build
- [ ] Methodology v1.1 (headcounts, combined reach), with Anna's prose; three restatement examples captured (new data, identity change, methodology change)
- [ ] KM retention with CIs, correct censoring for age-outs and the final year; naive comparison shown
- [ ] Linkage ADR decided by Anna; linkage confined to the restricted schema
- [ ] Naive vs DiD vs true uplift reported; pre-trends shown
- [ ] Results site live on GitHub Pages, sourced only from shares + labelled evaluation summaries
- [ ] README rewritten; CI green; demo script talking points written by Anna

---

## 12. Out of scope

- Real data, real partners, or real population denominators unless Anna adds them (Phase 3 rule)
- ML churn prediction beyond the optional logistic regression
- Fuzzy household-to-fan linkage
- Real-time or streaming ingestion (monthly batch files only)
- A persisted participant ID registry (still design-only, in ADR-004)
- Any interactive app with a backend; the site is static
