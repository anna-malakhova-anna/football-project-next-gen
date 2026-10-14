# Phase 5 demo: one club market, two lenses

**Run it:** `make p5-demo` (builds the feeds, the scorecard and the retention run, then prints the story), or `uv run python -m scripts.p5_demo --market MKT-06` once everything is built. About 15 minutes with the pauses.
All data is synthetic; the club and market are invented. Everything printed is a count or a rate; no child, parent or record is shown.

**The spine:** *How do you fix thin, messy youth participation data when privacy rules block the obvious fixes (collect more, buy enrichment, share more)?* Two audiences: a **privacy lead** (minimization, purpose limitation, children's data, retention) and a **clubs / analytics lead** (what can I see and trust in my territory). Every step answers a question one of them would ask; steps 4 and 6 answer both.

| # | Step | Talk track | Output to point at |
|---|---|---|---|
| 1 | **The mess** | "Five feeds reach this market, each with its own schema and defects. League names are free text, dates are in four formats, consent is a yes, a code, a sentence or nothing." | Registrations per feed, defect pass rates |
| 2 | **Resolution** | "We reuse the Phase 2 identity engine, one extension for feeds with no date of birth. Duplicates within a file are 0.6% of rows; after resolution it is 6%: the same child arriving through more than one door." | Rows to children; precision and recall (answer key); the sibling false merges we still make |
| 3 | **Scorecard** | "Each league is graded on six dimensions, and fit for two different purposes: counting needs a lower bar than contacting." Top fix per league is phrased for the operator. | League grades, `fit_reporting` vs `fit_activation`, fix list |
| | *Pause, clubs lead* | "Here is what you can trust: counts by market and age band, yes. Contacting households, not yet." | |
| 4 | **Consent provenance funnel** | "Participants, to households, to households where we know what the parent agreed to, when, on which wording, to households eligible for the club to contact." The drop at *known provenance* is the data quality story; the drop at *eligible* is the privacy story. A consent email is not a marketing opt-in: league-email consent alone would have admitted 2,258 more households. | Funnel; reasons for the drop; purpose limitation |
| | *Pause, privacy lead* | "Here is what never leaves the league: the child's name and birth year, the parent's email. The child and parent sides are separate; no marketing join touches the child. And here is the deletion job." | Retention counts for this market; `retention_log` has counts only |
| 5 | **Market estimate** | "We do not buy data about children. We count what we can place, allocate what we cannot, and say how unsure that leaves us." Participation rate against a *synthetic stub* of the Census youth population, with a band and a confidence label. | Estimate, band, rate, confidence, data gaps; (answer key) true count |
| 6 | **The data standard** | "The one-page ask for next season. Less data (birth year, ZIP3, flag only) and cleaner data (canonical league id, consent with when, which wording, which purposes). Asking for less costs about four points of recall and no precision." | Standard fields each feed misses; `docs/data-standard.md` |

## If asked
- *"Is the estimate right?"* It runs high (about 8% mean error on the synthetic answer key, against 5% for the naive count) because the matcher misses some duplicates. The first band missed the truth in 11 of 20 markets; the revised band was designed after seeing that, so its 20 of 20 is not evidence. Say so.
- *"Are the clubs real?"* No. Names, territories and the youth population are synthetic.
- *"Is a club a third party under COPPA?"* An open question for the privacy lead (question 1 in [questions-for-stakeholders.md](questions-for-stakeholders.md)); the build does not decide it.
- *"Which retention period is right?"* An open question (question 3); the periods are configuration and assumptions.
- *"What about a real deployment?"* The Phase 5 SQL runs on the operational stores; the retention job runs there, not on the immutable landing; the Census stub is replaced with ACS aggregated to ZIP3.
