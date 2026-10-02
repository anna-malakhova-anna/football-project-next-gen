# Demo script

> **Skeleton.** The structure, the order, the question each section answers and where each likely follow-up is answered are drafted. The talking points are Anna's to write:
> every `<!-- Anna: talking points -->` marker is empty on purpose. All data is synthetic; say so in the first sentence.

Setup before either walkthrough: `make all-phases && make site`, then serve `site/` (`python3 -m http.server -d site`) and keep `warehouse/flag.duckdb` open in a SQL client.

---

## The 5-minute walkthrough

| # | Show | The one question it answers | Time |
|---|---|---|---|
| 1 | **Overview page**: the data is synthetic and why, the architecture flow, the headline table | What is this and why should I trust a number from it? | 0:45 |
| 2 | **Participation page**: unique participants with the identity band; attributed vs present by country | How many people play, and how sure are you? | 1:15 |
| 3 | **Identity page**: threshold sweep; rules vs probabilistic; sibling merges | How do you know two records are the same child? | 1:15 |
| 4 | **Retention page**: naive vs censored for entrants aged 14 to 17 | Who stays, and why is "turned 18" not "quit"? | 1:00 |
| 5 | **Fandom page**: naive vs matched vs truth | Does playing change engagement, and how wrong can the easy answer be? | 1:00 |

<!-- Anna: talking points -->

Likely follow-ups, with where the answer lives:

| Follow-up | Where the answer is |
|---|---|
| Why is the participant count a range? | `docs/methodology/counting-a-participant.md` section 5; `mart_identity_uncertainty` |
| Why not tune the matcher until it is perfect? | ADR-003; the thresholds were chosen once, before the truth chart |
| Is this real data? | Overview banner; `docs/source_inventory.md`; README "If this were real" |
| Why is the matched estimate still above the truth? | ADR-010 "What the result says and does not say"; the Fandom page diagnostics table |

---

## The 15-minute walkthrough

Everything above, with these additions, in this order.

| # | Show | The one question it answers | Time |
|---|---|---|---|
| 1 | **Overview** and the architecture diagram in the README | What are the layers and where does the truth live? | 1:30 |
| 2 | **Sources and contracts**: `docs/source_inventory.md`, `contracts/US_LEAGUE.yml`, `make contracts` output | How does a new partner's data get in without anyone eyeballing it? | 2:00 |
| 3 | **Counting rules**: the C1 to C15 table in the memo; one SQL file (`fct_participant_year`) | Who counts, once, in which country? | 2:00 |
| 4 | **Identity**: the SQL for blocking and Fellegi-Sunter; the error categories | What does a wrong merge cost, and what did you do about it? | 2:30 |
| 5 | **Retention**: `retention_spells` (the censoring rules in one place) and the Kaplan-Meier model | How do you treat the end of the data and a 17th birthday? | 2:00 |
| 6 | **Fandom and the governance decision**: ADR-009, then the event study | May we link these at all, and what does it cost if we do? | 2:30 |
| 7 | **Governance page**: audience matrix, suppression example, restatement log | Who sees what, and what happens when a published number changes? | 1:30 |
| 8 | **Close**: README "If this were real" | What would you do differently in production? | 0:30 |

<!-- Anna: talking points -->

Likely follow-ups, with where the answer lives:

| Follow-up | Where the answer is |
|---|---|
| How do you stop ground truth leaking into the matcher? | `scripts/check_eval_isolation.py`; CLAUDE.md "Phase 2 conventions" |
| What is small-cell suppression and is it enough? | `dbt/macros/suppress_small_cells.sql`; ADR-006 (it is not formal disclosure control) |
| What happens when you add a year of data? | `docs/reports/restatement_demo.md` Example 2 |
| How do you keep a new KPI from rewriting history? | ADR-008 decision 3; Example 3 in the restatement demo |
| Why are the fan results only for linked households? | ADR-009; `linkage_link_bias` and the link-rate table |
| What would break first on real data? | README "If this were real"; ADR-003 limitations |
| How long does a full rebuild take? | About 2.5 minutes, `make all-phases` |
