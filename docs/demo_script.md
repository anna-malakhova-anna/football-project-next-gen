# Demo script

> **Skeleton.** The structure, the order, the question each section answers and where each likely follow-up is answered are drafted. The talking points are Anna's to write:
> every `<!-- Anna: talking points -->` marker is empty on purpose. All data is synthetic; say so in the first sentence.

Setup before either walkthrough: `make all-phases && make site`, then serve `site/` (`python3 -m http.server -d site`) and keep `warehouse/flag.duckdb` open in a SQL client.

---

## The 5-minute walkthrough

The story is one business question, in order: **acquisition, then value, then audience, then "and here is why you can trust these numbers"** (identity, governance).

| # | Show | The one question it answers | Time |
|---|---|---|---|
| 1 | **Overview page**: the data is synthetic and why; the headline table (incremental fans, addressable audience, consent gap) | What is this, and what is the headline? | 0:45 |
| 2 | **Fan acquisition page**: the first chart (incremental vs naive vs truth), then the funnel by fan status; UNLINKED means unknown | How many fans did flag football create, and why is the easy count wrong? | 1:30 |
| 3 | **Fan value & activeness page**: fan survival, LTV ranges, value uplift for existing fans | How engaged and valuable are they? | 1:00 |
| 4 | **Audience & consent page**: audience over time, the consent gap, capture by capture point, the market quadrants | How many can we actually contact, and where do we look next? | 1:00 |
| 5 | **Data trust & governance page**: identity (threshold sweep, sibling merges), who sees what, restatement log | Why should I trust these numbers? | 0:45 |

<!-- Anna: talking points -->

Likely follow-ups, with where the answer lives:

| Follow-up | Where the answer is |
|---|---|
| Why is the incremental number lower than the naive scaled one? | ADR-011; `docs/methodology/flag-as-fan-acquisition.md` section 3 |
| What does UNLINKED mean, and could they be fans? | Methodology (fan memo) section 2; `eval_fan_status` (about 23% of unlinked households do have an account) |
| Why not a regression with market and year effects? | ADR-011 "Why not a pooled two-way fixed-effects regression" |
| Why is there no marketing list? | ADR-009; `scripts/check_share_policy.py` (nothing linked reaches marketing or media) |
| Is this real data? | Overview banner; `docs/source_inventory.md`; README "If this were real" |
| Why is the participant count a range? | `docs/methodology/counting-a-participant.md` section 5; `mart_identity_uncertainty` |
| Why not tune the matcher until it is perfect? | ADR-003; the thresholds were chosen once, before the truth chart |
| Why is the matched engagement estimate above the truth? | ADR-010 "What the result says and does not say"; the value page diagnostics table |

---

## The 15-minute walkthrough

Everything above, with these additions, in this order.

| # | Show | The one question it answers | Time |
|---|---|---|---|
| 1 | **Overview** and the architecture diagram in the README | What are the layers and where does the truth live? | 1:30 |
| 2 | **Acquisition**: `mart_acquisition_incrementality` (the stacked cohort comparison in SQL) and the event-study chart | How do you measure what the programme caused when most households are invisible? | 3:00 |
| 3 | **Funnel and fan status**: `fct_household_fan_status`, `mart_fan_funnel` | How is a household's fan status decided, and what is the denominator? | 2:00 |
| 4 | **Value**: `mart_fan_ltv`, `mart_fan_survival`, the value uplift | What is a fan worth, and how sure are you? | 2:00 |
| 5 | **Audience and consent**: the consent SCD2 (`fct_fan_consent_history`), `mart_addressable_audience`, the consent gap | How does governance set the size of the marketable audience? | 2:30 |
| 6 | **Identity and the linkage decision**: ADR-009, then the identity page | May we link registrations to fan accounts at all, and what does a wrong merge cost? | 2:30 |
| 7 | **Governance page**: audience matrix, suppression example, restatement log | Who sees what, and what happens when a published number changes? | 1:30 |
| 8 | **Close**: README "If this were real" | What would you do differently in production? | 0:30 |

<!-- Anna: talking points -->

Likely follow-ups, with where the answer lives:

| Follow-up | Where the answer is |
|---|---|
| How do you stop ground truth leaking into the matcher or the estimates? | `scripts/check_eval_isolation.py`; CLAUDE.md "Phase 2 conventions" |
| What is small-cell suppression and is it enough? | `dbt/macros/suppress_small_cells.sql`; ADR-006 (it is not formal disclosure control) |
| What happens when you add a year of data? | `docs/reports/restatement_demo.md` Example 2 |
| How do you keep a new KPI from rewriting history? | ADR-008 decision 3; Example 3 in the restatement demo |
| Why are the fan results only for linked households? | ADR-009; `linkage_link_bias` and the link-rate table |
| Are consent changes resolved safely? | `eval_consent_checks`: 3 of 58 unsafe mismatches are invisible from the data; contact use must fail closed on flagged accounts |
| What would break first on real data? | README "If this were real"; ADR-003 limitations; ADR-011 (real market launches are not random) |
| How long does a full rebuild take? | About 8 minutes, `make all-phases` (most of it the test suite) |
