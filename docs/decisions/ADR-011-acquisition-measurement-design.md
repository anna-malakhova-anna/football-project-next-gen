# ADR-011: Measuring fan acquisition at market level

- **Status:** Accepted (rework step 7). The design was fixed before the ground truth was read and was not tuned afterwards.
- **Synthetic data.** Markets, households and accounts are all generated; the numbers below describe a generated world.

## The question
How many fan accounts exist because flag football exists? Counting households that opened an account after registering a child (net-new) answers a different question: some of them
would have joined anyway, and households that are neither fans nor participants are invisible to any household-level comparison. Acquisition has to be measured where the non-participants are
visible, and that is the market.

## Decision
Use the **staggered market launches** as the experiment. Markets launched in different years and some never launched, so at any date there are launched markets and not-yet-launched ones.

- **Outcome:** new fan accounts per 1,000 households in a market-year (`int_market_year_accounts`; accounts with duplicates collapsed; the household population is the market's synthetic universe).
- **Estimator:** a **stacked, cohort-specific** comparison (`mart_acquisition_incrementality`). For each launch cohort L and each year-since-launch k, the effect is the change from the year before launch
  (L-1) in the cohort's markets minus the same change in **control markets**: markets not yet treated in either year, plus markets that never launch.
  Incremental accounts are that effect times the cohort's households, summed over post-launch cells. Standard errors come from the market-level changes.
- **Checks:** pre-launch cells (k < 0) should sit near zero (a flat pre-period supports the comparison); the 2021 cohort has no pre-period inside the data and is not estimated.
- **Always shown beside the naive count:** net-new linked households, and the same count scaled up by the link rate.

## Why not a pooled two-way fixed-effects regression
With staggered adoption a pooled TWFE regression uses markets that were **already treated** as controls for later cohorts. When the effect grows or fades with time since launch, those comparisons
get negative weights and the pooled coefficient can be biased, even with the wrong sign. Cohort-specific comparisons against not-yet-treated and never-treated markets avoid the forbidden comparison
by construction, and every cell is readable on its own (and plotted as the event study). The cost is wider intervals: fewer markets stand behind each cell.

## Result on the synthetic data
| Estimate | Accounts | Against the truth (1,111) |
|---|---|---|
| Incremental (the estimator above), 95% interval | **1,264** (897 to 1,630) | 1.14x; the truth is inside the interval |
| Naive: net-new linked households | 939 | 0.85x |
| Naive: net-new scaled by the link rate | 2,543 | 2.29x |

The pre-launch cell is flat (-0.001 extra accounts per 1,000 households, interval -0.14 to +0.14). The truth is exact: the generator records which accounts exist only because of the programme.
The naive linked count is close to the truth by coincidence of two opposite errors (it ignores unlinked households and counts accounts that would have existed anyway); scaling it by the link rate
overstates 2.3x because unlinked households do not behave like linked ones.

## What this does not say
- **Market-level, not household-level.** It says how many accounts the programme added, not which households.
- **Few markets stand behind each cell** (79 market-years in total across 9 cells), hence wide intervals. The point estimate is above the truth by 14%.
- **It assumes launched and not-yet-launched markets would have moved together** without the programme. The flat pre-period tests this for the observed pre-years only.
- **Launch timing is an operational fact in the generator,** unrelated to market fan potential. In real data, markets are often chosen because they look promising, which would bias the comparison;
  the design would then need pre-trends per market and a sensitivity analysis.
- **Spillovers** (a launch raising accounts in neighbouring unlaunched markets) are not modelled and would bias the estimate toward zero.

## What was not tried
Nothing was adjusted after seeing the truth. Not tried, because it would be tuning: dropping cohorts or markets until the estimate matched, changing the base year, or choosing controls by
distance from the truth. A real next step is a doubly robust or synthetic-control estimator judged on the pre-trend.

## Consequences
- The headline of the project is the incremental range, and it is always shown next to the naive count.
- The eval models (`eval_acquisition`, `eval_acquisition_event_study`, `eval_acquisition_checks`) read the truth; nothing else does.
- `int_market_year_accounts` is also shared with analysts (`share_analyst__fan_market_year`) so the estimate can be re-run.
