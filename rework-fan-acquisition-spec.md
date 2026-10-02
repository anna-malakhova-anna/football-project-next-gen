# Counting Flag Football — Rework Spec: Flag Football as a Fan Acquisition Channel

**Purpose:** Reorient the project from *"how many people play?"* to *"how many fans does flag football create, how engaged are they, how many can we contact, and what are they worth?"*

Participation measurement, identity resolution, and privacy controls stay as the foundation. The fan and revenue side becomes the headline.

**Supersedes:** Phase 4 sections 4 (Source D), 5 (Source E), 6.2 (retention drivers and transitions), 7 (fandom outcomes), and 8 (showcase structure). Everything else in Phase 4 still applies unless stated here.

**New headline question for the README and site:**
> Flag football reaches families the league may not reach any other way. How many of them become fans, how valuable are they, and how many can we actually talk to?

---

## 0. Pre-flight: inventory before changing anything

The project may be anywhere in Phase 4. Before writing code:

1. Run the full build (`make phase3`, or `make all-phases` if it exists). Everything must pass.
2. Produce `docs/rework_inventory.md`: a table of every Phase 4 component with its build status (`not started` / `partial` / `done`) and its disposition under this spec:

| Phase 4 component | Disposition |
|---|---|
| Data window extension (2021–2025) | **Keep** |
| Playbook + contracts + validation | **Keep** |
| Source E (school headcounts) | **Demote to stretch.** If done, keep it but remove it from the site's main pages and the exec report headline. If not started, skip it. |
| Methodology v1.1 (headcounts) | Keep only if Source E is done; otherwise fold into v2.0 (section 9) |
| Player retention: cohorts + Kaplan–Meier | **Keep**, repositioned as an input to fan value (section 6.4) |
| Retention transitions + drivers | **Cut** (remove if built) |
| Source D (fan feed) as specified in Phase 4 | **Replace** with section 3 of this spec. If already built, extend it rather than rewriting from scratch. |
| Household linkage + ADR-009 | **Keep**; extend per section 4 |
| Fan DiD (household spend uplift) | **Keep**, repositioned as "value uplift among existing fans" (section 5.3) |
| Results site | **Restructure** per section 8 |

3. **Pause for Anna** to review the inventory before continuing.

---

## 1. Principles (in addition to earlier phases)

1. **Acquisition, not just association.** "Families who play are big fans" is not an acquisition claim. Distinguish fans flag football **created** from fans it **enrolled**.
2. **Unknown is not "no".** A participant household with no linked fan account may still be a fan under a different email. Never classify unlinked households as non-fans; give them their own `UNLINKED` status.
3. **Contactability is a measured outcome.** Consent is a funnel stage with a size and a gap, not just a filter.
4. **Guardians only.** All fan and marketing logic operates on adult accounts. No minor's data reaches any fan or marketing output.
5. **Synthetic money stays synthetic.** Revenue figures are labelled synthetic and use round, obviously illustrative scales. Never present them as NFL figures.
6. **Geography, not demographics.** Population profiling uses markets, regions, program types, and household shape. No race or ethnicity, not even synthetic.

---

## 2. Markets (new reference data)

`dbt/seeds/market_map.csv`: maps US zip3 and Canadian FSA prefixes to **synthetic markets** (`MKT-01` … `MKT-40`).

Columns: `market_id`, `market_name` (synthetic, e.g. "Market 07 (Southwest)"), `country_code`, `region_code`, `is_team_market` (Y/N), `household_population` (synthetic), `notes`.
- About 40% of markets are team markets.
- Add matching synthetic markets for INTL countries (one or two per country).
- **Label everything synthetic.** Don't attempt real metro boundaries or real population figures.

Add `market_id` to `fct_registration`, `fct_participant_year`, `int_household`, and fan accounts.

---

## 3. Source D, revised: fan ecosystem

### 3.1 Files

| File | Grain | Notes |
|---|---|---|
| `fan_accounts.csv` | Account | `account_id`, `email`, `phone`, `postal_prefix`, `country`, `created_at`, `acquisition_source` (`organic`, `ticketing`, `app_store`, `partner_referral`, `flag_registration_prompt`), `birth_year` (holder; adults only) |
| `fan_consent_events.jsonl` | Consent change | `account_id`, `channel` (`email`, `sms`, `push`), `status` (`opt_in` / `opt_out`), `event_ts`, `capture_point` (`signup`, `checkout`, `preference_center`, `flag_registration`) |
| `fan_events_YYYY_MM.jsonl` | Engagement event | As in Phase 4: `app_open`, `content_view`, `game_stream`, `newsletter_click`, plus `fantasy_activity` and `flag_content_view` |
| `fan_transactions_YYYY_MM.jsonl` | Transaction | `txn_id`, `account_id`, `txn_ts`, `category` (`ticket`, `merch`, `subscription`, `other`), `amount` (synthetic currency), `is_refund` |

### 3.2 Built-in mechanics (all parameters in `config/generation.yaml`; truth in `data/ground_truth/fan_truth.parquet`)

- **Latent fandom** per household (as in Phase 4)
- **Selection:** higher fandom → more likely to enroll a child (as in Phase 4)
- **Staggered program rollout:** flag programs launch in different markets in different years (2021–2024). Some markets never launch. **This is a generator change upstream:** registrations in a market start only after its launch year. Re-run Phases 1–3 and update their expected values. This rollout is what makes acquisition incrementality measurable (section 5.2).
- **True acquisition effect:** after a household's first registration, non-fan households have a configured probability of creating a fan account above the organic baseline (`true_acquisition_lift`). Some do it via the `flag_registration_prompt` source.
- **Organic account creation:** non-participant households in every market create accounts at a baseline rate, with NFL-season seasonality
- **Reactivation:** lapsed fan accounts reactivate after first registration with a configured lift
- **Engagement and spend uplift** after registration (as in Phase 4's `true_uplift`), by category. Ticket uplift is stronger in team markets.
- **Consent dynamics:** opt-in rates differ by capture point. `flag_registration` capture is configurable. Some opt-outs happen after heavy email volume.

### 3.3 Defects (in addition to Phase 4's)
- Account email ≠ guardian email: 25% (keep). This drives the `UNLINKED` status.
- Duplicate accounts for the same household: 3%
- Refunds without a matching original transaction: 0.5%
- Consent events out of order (an opt-out timestamped before the opt-in): 1%

### 3.4 Contract
Write `contracts/fan_*.yml` following the playbook. **Consent and transaction rules are `ERROR` severity.**

---

## 4. Fan data models

### 4.1 Staging and core
- `stg_fan_accounts`, `stg_fan_consent_events`, `stg_fan_events`, `stg_fan_transactions`: typed, deduplicated, with defects flagged
- `dim_fan_account`: deduplicated accounts. Collapse duplicate household accounts with deterministic rules (same normalized email or phone + postal prefix) and keep an xref table.
- **`fct_fan_consent_history`:** an SCD Type 2 table per account × channel, with `valid_from`, `valid_to`, `status`, `capture_point`. Resolve out-of-order events by timestamp and flag them. **No overlapping intervals** (tested). This is a strong SQL showcase.
- `fct_fan_engagement_month`: account × month (Phase 4 logic)
- `fct_fan_transaction`: net of refunds; orphan refunds flagged and excluded from revenue

### 4.2 Household-level fan view
- `int_household_fan_link`: extends the Phase 4 linkage; a household may link to multiple accounts
- **`fct_household_fan_status`**: one row per participant household, with status **as of the month of first registration**:

| Status | Rule |
|---|---|
| `EXISTING_ACTIVE` | Linked account with engagement in the 90 days before first registration |
| `LAPSED_REACTIVATED` | Linked account, no engagement in the 180 days before, engagement within 12 months after |
| `LAPSED_DORMANT` | Linked account, inactive before, still inactive after |
| `NET_NEW` | Linked account **created** after first registration |
| `UNLINKED` | No linked account. **Unknown, not "non-fan".** |

Add a `net_new_via_flag_prompt` flag (acquisition_source = `flag_registration_prompt`).

Windows (90, 180, 12 months) come from `fan_params.csv`, not hardcoded values.

---

## 5. Analyses

### 5.1 Fan acquisition funnel: `mart_fan_funnel`
By registration cohort year × market type × segment (girls' household, international, adult player household, multi-child household):

Participant households → **linked** → **contactable** (≥1 channel opted in, guardian account) → **active** (engaged in the last 90 days) → **monetized** (≥1 net purchase) → **retained** (active 12 months after the first registration)

- Show counts and step conversion rates
- Split the top of the funnel by fan status, so net-new fans can be followed separately
- Report `UNLINKED` as its own line, never dropped
- **Test:** each stage ≤ the previous stage

### 5.2 Acquisition incrementality: `mart_acquisition_incrementality`
**The key analysis.** Household-level comparison can't measure acquisition, because households that are neither fans nor participants are invisible. So measure it at **market level** using the staggered rollout:
- Outcome: new fan accounts per 1,000 households per year, using synthetic `household_population`
- For each launch cohort (markets launching in year L), compare against **not-yet-treated and never-treated markets** over the same years (a stacked, cohort-specific comparison; no pooled two-way fixed effects). Document why in ADR-011: pooled two-way fixed effects estimates are known to be biased with staggered timing.
- Event study: effect by years relative to launch (−2 to +3). Pre-periods should be flat.
- Output: incremental new fan accounts per launch market per year, and the total incremental fans attributable to flag programs, with a range
- **Evaluation:** `eval_acquisition`, comparing against `true_acquisition_lift`, plus a naive version ("count every account created after a registration") to show the overclaim

### 5.3 Value uplift among existing fans: `mart_fan_value_uplift`
The Phase 4 household-level matched DiD, now explicitly scoped to `EXISTING_ACTIVE` and `LAPSED_*` households, by spend category and engagement type. Keep the naive vs DiD vs truth comparison.

### 5.4 Fan value and activeness
- `mart_fan_activeness`: active / at-risk / lapsed counts and transitions by month, by fan status
- `mart_fan_rfm`: recency, frequency, and monetary quintiles via `NTILE(5)` over a trailing 12 months, with named segments in `rfm_segment_map.csv` (e.g. Champions, Loyal, Promising, At risk, Hibernating). Compare segment mix: net-new flag fans vs existing fans vs non-participant fans.
- `mart_fan_survival`: **Kaplan–Meier for fan activeness**, i.e. time from first engagement to lapse, by fan status. Reuse the Phase 4 KM macro or SQL pattern.
- **Conditional analysis:** does a household's fan lapse rate change when its child stops playing? Compare fan survival for households whose child churned vs stayed (association only; say so).
- `mart_fan_ltv`: simple 3-year value = average monthly net spend × expected active months (from fan survival), by fan status and market type. A range comes from the KM confidence interval. **Labelled synthetic and illustrative.**

### 5.5 Addressable audience and consent: `mart_addressable_audience`
- Contactable participant households by channel, over time (from consent SCD2 as of month-end)
- **Consent capture rate** by capture point and by registration source/partner. Which partners' registration flows capture consent best?
- **Engaged but not contactable:** active households with no channel opted in → the "consent gap." Value it at the median monetized household's spend as an illustrative opportunity size.
- Opt-out rate after contact
- **Hard rule:** guardian accounts only. No minor's data.

### 5.6 Population and market profile: `mart_market_profile`
Per market:
- Flag participation per 1,000 households
- Fan accounts per 1,000 households
- Net-new fan rate among participant households
- Girls' share of participants; consent capture rate; team market flag

Then classify each market into a **quadrant** using medians or thresholds from `market_quadrant_params.csv`:
- **Flag strong / fan base thin** → *acquisition white space*
- **Flag strong / fan base strong** → *retention and engagement play*
- **Flag weak / fan base strong** → *program growth opportunity*
- **Flag weak / fan base thin** → *long-term build*

Add a household-shape profile: kids per household, years active, and adult-player households vs youth households, against fan status and value.

---

## 6. Repositioning existing work

- **Player retention (KM)** feeds two things: the participation story (still on the participation page), and the conditional analysis in 5.4 ("do families stay fans when kids stop playing?")
- **Identity resolution** is now presented as the reason the funnel's denominator is right: without it, multi-league kids inflate households and deflate conversion rates. Add one line to the funnel page with this message.
- **Consent rules from Phases 1–3** connect directly to the addressable audience. "Governance determines the size of the marketable audience" is the bridge line.

---

## 7. Shares and privacy

- **`share_exec`**: funnel, incrementality summary, LTV ranges, addressable audience counts, and market quadrants, all with small-cell suppression. Markets with fewer than `k_min` participant households are suppressed or rolled up to region.
- **`share_marketing`**: extend it with the addressable audience **list** (guardian contact + channel + fan status + RFM segment). Only currently opted-in channels as of the run date, from SCD2. Never minors. Never `UNLINKED` households (they have no fan account consent).
- **`share_analyst`**: pseudonymized household-month and market-year panels
- **Linkage schema** rule from Phase 4 still applies: household-linked data leaves only through approved aggregates or the consent-filtered marketing list
- Extend `check_share_policy.py` and the isolation check to cover the new tables and truth files

---

## 8. Site and README restructure

### Site pages (new order)
1. **Overview:** the headline question, why the data is synthetic, the architecture diagram, the 5-minute tour
2. **Fan acquisition:** funnel by fan status; incremental new fans (naive vs incremental vs truth); event study chart
3. **Fan value & activeness:** RFM segment mix by fan status; fan survival; LTV ranges; existing-fan value uplift
4. **Audience & consent:** addressable audience over time; consent capture by partner and capture point; consent gap; market quadrant chart
5. **Participation:** the Phase 3 content, condensed (trend with bounds, country views, player retention)
6. **Data trust & governance:** identity evaluation, contracts, restatements, access model

The first chart on page 2 must stand alone. Most viewers won't scroll past it.

### README
- New first paragraph built around the headline question
- Results table now leads with: net-new fans, incremental fans (range), addressable audience, consent gap; then participation and identity metrics
- The rest as in Phase 4

### Demo script
Restructure around the business question: acquisition → value → audience → "and here's why you can trust these numbers" (identity, governance). **Anna writes the talking points.**

---

## 9. Methodology v2.0

- New memo, `docs/methodology/flag-as-fan-acquisition.md`, as a companion to the participation memo. It covers fan status definitions, why `UNLINKED` ≠ non-fan, why acquisition is measured at market level, LTV assumptions, and the guardians-only rule.
- **Claude Code drafts the skeleton and numbers with DRAFT markers. Anna writes the prose.**
- Bump the methodology version, add a CHANGELOG entry, publish, and capture the `METHODOLOGY_CHANGE` restatement.

---

## 10. Metric catalog additions

Net-new fans; net-new fans via flag prompt; incremental new fans (range); funnel stage counts and conversions; contactable households by channel; consent capture rate; consent gap households and illustrative value; active, at-risk, and lapsed fans; RFM segment shares; fan survival at 12 months; LTV (range); market quadrant counts. Each with its definition, grain, additivity, and owner.

---

## 11. Tests (additions)

- Fan status: exhaustive and mutually exclusive; `UNLINKED` is never reclassified as a non-fan status
- Funnel stages are non-increasing
- Consent SCD2: no overlapping intervals per account × channel; every interval has `valid_from < valid_to` (or open-ended)
- Addressable audience and marketing share: only guardian accounts, only channels opted in as of the run date, no `UNLINKED` households
- Net transactions: orphan refunds are excluded and counted in a DQ log
- RFM: each quintile is roughly 20% of scored accounts (tolerance documented)
- KM fan survival: same validity tests as player KM
- Incrementality: comparison markets are never already treated in the comparison years
- No literal window lengths or thresholds in models (they come from params seeds)
- Isolation: `fan_truth` is referenced only in `models/evaluation/`
- Site: every chart's data comes from `share_exec` or a labelled evaluation summary

---

## 12. Build order for Claude Code

1. Pre-flight inventory (section 0). **Pause for Anna.**
2. Remove cut components (transitions, drivers) and demote Source E per the inventory. Rebuild and confirm green.
3. Market seed + generator changes (staggered rollout, revised Source D). Full rebuild of Phases 1–3; update expected values; capture the restatement.
4. Fan contracts → staging → `dim_fan_account` → consent SCD2 → engagement and transaction facts
5. Household fan link → `fct_household_fan_status`. **Print the status distribution and pause for Anna.**
6. Funnel
7. Acquisition incrementality + `eval_acquisition`. **Print naive vs incremental vs truth and pause for Anna.**
8. Value uplift (adapt the Phase 4 DiD), activeness, RFM, fan survival, LTV
9. Addressable audience and consent gap
10. Market profile and quadrants
11. Shares + policy checks
12. Site restructure, README, methodology v2.0 skeleton, demo script skeleton, ADR-011 (acquisition measurement design), inventory updates
13. CI green

Stop after each step and confirm it runs and tests pass.

**Cut order if time runs short:** Source E (already stretch) → conditional "kid churn vs fan lapse" analysis → RFM named segments (keep the quintiles) → event study chart (keep the incremental estimate) → LTV (keep spend per household).

**Never cut:** fan status with `UNLINKED`, the funnel, market-level incrementality with the naive comparison, the addressable audience and consent gap, and the guardians-only rule.

---

## 13. Definition of done

- [ ] Rework inventory reviewed by Anna; cut items removed; Phases 1–3 green after the generator changes
- [ ] Consent SCD2 built and tested
- [ ] Fan status per participant household, with `UNLINKED` kept distinct
- [ ] Funnel, with conversions by fan status and segment
- [ ] Market-level acquisition incrementality, with naive vs incremental vs truth and visible pre-trends
- [ ] Existing-fan value uplift, RFM, fan survival, and LTV range
- [ ] Addressable audience, consent capture by partner, and consent gap
- [ ] Market quadrants
- [ ] Shares extended; guardians-only and consent tests pass
- [ ] Site reordered with fan acquisition first; README and demo script reframed
- [ ] Methodology v2.0 memo with **Anna's prose**; ADR-011 written; restatement captured
