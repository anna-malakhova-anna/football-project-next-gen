# ADR-010: Measuring the fandom effect of registering a child

- **Status:** Accepted for the default policy of ADR-009 (Phase 4). If ADR-009 is decided differently the inputs change, the design does not.
- **Context:** Does a household engage more with the sport after its first registration? All data is synthetic, with a known true effect
  (`sources.fan.true_uplift`, +15% events per month while a child is active, halving every 12 months after the last active season) and a known
  selection (households with higher latent fandom are more likely to enroll a child). The naive answer is wrong on purpose; the question is how
  far a reasonable design gets, with the truth used only to grade it.

## Design (fixed before the truth was read; nothing was tuned afterwards)
- **Unit and grain:** a fan unit is one account, by month (`fct_household_engagement_month`). A linked account stands for its participant household;
  every unlinked account is a comparison unit. Events count once per `event_id` and belong to the month of `event_ts`.
- **Event time:** the registration month of the household's first registration (`int_participant_household_timeline`). Most sources record no
  registration date, so the month comes from the term (spring and annual -> March, fall -> August; var `enrollment_month_by_term`, tested against the
  generator config). Households whose first registration is in the first data year are left-censored and excluded, as in the retention analysis.
- **Matching (coarsened exact matching, in SQL):** country, event month, pre-period tenure band, pre-period engagement band (quartile of events per month
  in the 12 months before event time, pooled). A comparison account is a candidate at every event month and is matched on its own pre-period at that month,
  with the matched household's event time as its pseudo event time. At least 6 pre months with an account and 6 post months inside the data are required.
  Comparison weights make each stratum's comparisons add up to its treated count. "Calendar month of event time" is implemented as the exact event month.
- **Estimate:** matched difference-in-differences (post - pre for participants minus post - pre for weighted comparisons), in events per household-month,
  then as a percentage of the participants' counterfactual post level. A ratio-of-ratios form is reported as a sensitivity check. The event study shows
  months -12 to +18 so the pre-trend is visible.
- **Uncertainty:** analytic standard errors in SQL (not a bootstrap): the difference between the participants' mean change and the comparisons' weighted
  mean change, 95% interval = estimate +/- 1.96 se.

## Result on the synthetic data (2021 to 2025)
| Estimator | Estimate | 95% interval | Truth | x truth |
|---|---|---|---|---|
| Naive (participants vs non-participants, same months) | +45.6% | +41.6% to +49.6% | +14.7% | 3.1x |
| Matched DiD (additive, headline) | +17.2% | +14.9% to +19.4% | +14.7% | 1.17x |
| Matched DiD (ratio, sensitivity) | +17.3% | not computed | +14.7% | 1.18x |

The truth column is the uplift the matched households actually received over the months averaged (below the configured +15% because of decay after
churn). All 1,098 eligible participant households found a comparison (match rate 100%) from 15,568 comparison accounts.

## Re-measured after the rework (rework step 3)
The rework regenerated the data (15,000 people, staggered rollout, revised fan source with lapse, reactivation, duplicate accounts and transactions) and made the truth exact: the
generator now records, for every participant account and month, the expected events as observed and with no programme (uplift, decay after churn, and reactivations the programme
caused). On the new data: **naive +30.4% (1.7x the truth), matched difference-in-differences +21.0% (95% interval +18.9% to +23.2%), true effect +18.2%** (1.16x; the truth sits just
outside the interval). 2,843 of 2,844 eligible participant households matched; the event-study pre-period is flat (largest gap 5.7%). The naive bias is smaller than in the table
below because account holders as a group are fandom-heavy in the new generator, so participants differ less from the other account holders. The truth is higher than the configured
15% because a registration can reactivate a lapsed fan. The earlier table is kept as the record of the first run. Rework step 8 re-scopes this analysis to existing and lapsed fans
and adds spend categories; the design itself was not changed.

## What the result says and does not say
- **Naive is inflated about threefold** by selection: participants are fandom-heavy before they enroll (mean latent fandom +0.38 vs -0.13).
- **Matching removes most of the bias, not all.** The matched estimate is 2.4 points above the truth, and the truth sits just outside its interval.
  Reasons, in order of what the diagnostics show:
  1. **Residual selection.** Matching on coarse pre-period engagement leaves matched comparisons less fandom-heavy than matched participants (latent
     fandom +0.22 vs +0.36), and a higher-level group gains more from the same seasonality in additive terms. The event study shows it: the pre period is
     not zero but about +3% (largest gap 8.8%).
  2. **Intervals are somewhat too narrow.** Comparison accounts repeat across event months, so the effective sample is smaller than the pair count.
  3. **Comparison contamination (the other direction).** 6.7% of the comparison weight is in fact a participant household whose account could not be
     linked. That biases the estimate toward zero, so without it the overshoot would be larger.
- **It describes linked households only.** Linked households are mostly North American and register with an email the app also holds (ADR-009).
- **Only the average post effect is estimated well.** The decay after churn is visible in the data but not separated out.

## What was tried
One design, one run, no iteration on the truth. The ratio form and the exact-month matching were decided before the comparison. Options **not** tried because
they would have been tuning against the truth: finer engagement bands, a different pre window, dropping strata until the pre-trend flattened. A finer
design is the obvious next step in a real analysis, judged on the pre-trend (label-free), never on distance from the truth.

## Consequences
- Nothing household-level leaves the `linkage` schema. The summary and the event study will reach `share_exec` and `share_analyst` only as suppressed
  aggregates (Phase 4 step 8), each with a caveat that the result describes linked households.
- The known truth makes these numbers properties of the generator. A real analysis would have no truth column; it would rely on the pre-trend,
  placebo tests and sensitivity checks.
