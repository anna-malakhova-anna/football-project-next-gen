# Demo script

> **Skeleton.** The structure, the order, the question each section answers and where each likely follow-up is answered are drafted. The talking points are Anna's to write:
> every `<!-- Anna: talking points -->` marker is empty on purpose. All data is synthetic; say so in the first sentence.

Setup before either walkthrough: `make all-phases && make site`, then serve `site/` (`python3 -m http.server -d site`) and keep `warehouse/flag.duckdb` open in a SQL client.

---

## The 5-minute walkthrough

The story is one business question, in order: **acquisition, then audience, then "and here is why you can trust these numbers"** (identity, governance). The Value page stays in the repo as detailed evidence for the fan-uplift number (DP5) but is off the walkthrough: it profiles households of child participants, which is the wrong signal for the privacy audience (ADR-021).

| # | Show | The one question it answers | Time |
|---|---|---|---|
| 1 | **Overview page**: the data is synthetic and why; the headline table (incremental fans, addressable audience, consent gap) | What is this, and what is the headline? | 0:45 |
| 2 | **Fan acquisition page**: the first chart (incremental vs naive vs truth), then the funnel by fan status; UNLINKED means unknown | How many fans did flag football create, and why is the easy count wrong? | 1:30 |
| 3 | **Audience & consent page**: audience over time, the consent gap, capture by capture point, the market quadrants | How many can we actually contact, and where do we look next? | 1:00 |
| 4 | **Data trust & governance page**: identity (threshold sweep, sibling merges), who sees what, restatement log | Why should I trust these numbers? | 0:45 |

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
| 4 | **Audience and consent**: the consent SCD2 (`fct_fan_consent_history`), `mart_addressable_audience`, the consent gap | How does governance set the size of the marketable audience? | 2:30 |
| 5 | **Identity and the linkage decision**: ADR-009, then the identity page | May we link registrations to fan accounts at all, and what does a wrong merge cost? | 2:30 |
| 6 | **Governance page**: audience matrix, suppression example, restatement log | Who sees what, and what happens when a published number changes? | 1:30 |
| 7 | **Close**: README "If this were real" | What would you do differently in production? | 0:30 |

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

---

## The two-audience 15-minute path (Phase 5): one club market

> **Skeleton.** Structure, order, questions and the numbers each step stands on are drafted. **Anna writes the talking points** (the markers are empty on purpose). All data is synthetic: say so first. Run `make p5-demo` (or `uv run python -m scripts.p5_demo --market CM-GA-02 --interactive`) to print the numbers in order; the site pages *Data quality*, *How sure*, *Club markets* and *Privacy by design* have the charts, with the Club lens / Privacy lens toggle on each. The market is a project approximation of ZIP3 groups, not any club's territory.

**The spine:** *How do you fix thin, messy youth participation data when privacy rules block the obvious fixes (collect more, buy enrichment, share more)?* Two audiences: a **clubs / analytics lead** (what can I see and trust in my market) and a **privacy lead** (minimization, purpose limitation, children's data, retention). Steps 2 and 5 are the two pauses.

| # | Step | The one question | Show | Time |
|---|---|---|---|---|
| 1 | **The mess** | What does the registration data actually look like? | Data quality page: the rules that fail most in the market (`make p5-demo` step 1) | 2:00 |
| 2 | **The scorecard** | Which data can I trust, for what? | Data quality page: purpose heatmap (same data, different grades) and the Pareto | 2:30 |
| | *Pause for clubs* | | | 1:00 |
| 3 | **The uncertainty decomposition** | Why can't you give me one number? | How sure page: three separate bars; the evaluation overlay says where the method misses | 2:00 |
| 4 | **The missingness bias** | Is the girls' trend real or an artefact? | How sure page: dumbbell by division; blanks are concentrated, not random | 1:30 |
| 5 | **The activation funnel** | Why can't I reach more families? | Club markets page: loss by cause, data quality vs privacy; the two lenses on one market | 2:00 |
| | *Pause for privacy* | | | 1:00 |
| 6 | **The minimization frontier** | What does each field buy us, and what does it cost? | Privacy page: the frontier; the standard cites V2 (ADR-018) | 1:30 |
| 7 | **The fix-list payoff** | What is the payoff of fixing upstream? | How sure page: simulated before/after; the coverage gap does not close | 1:00 |

<!-- DRAFT: Anna to write the talking points -->

Likely follow-ups, with where the answer lives:

| Follow-up | Where the answer is |
|---|---|
| Is a club a "third party" under COPPA? | Open question for the privacy lead; `docs/context/real-world-context.md`; `docs/questions-for-stakeholders.md`. The build does not decide it |
| Why is the grade the minimum, not the average? | `docs/data-quality.md`; ADR-014 |
| Why are the three uncertainties not added? | ADR-015 |
| Did the coverage estimate work? | The evaluation overlay: its interval misses the truth in some years; reported, not tuned (ADR-015) |
| Which retention period is right? | Open question; every period is a configurable assumption (ADR-017, `docs/retention.md`) |
| Why is there no participation rate? | Denominators are not loaded and never invented (`population_denominators`) |
| Are the markets real club territories? | No: a project approximation (ADR-016) |
| What would you change in production? | The README "If this were real"; raw-zone deletion is question 18 |
