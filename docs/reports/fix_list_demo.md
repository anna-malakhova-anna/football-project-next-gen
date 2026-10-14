# Feedback-loop demo: what if the fix list were acted on?

> **SIMULATED.** Synthetic data and a made-up scenario: this shows what the engine would report if organizations acted on their fix list, not that any organization does or would.
> In the final season (2025) 50% of the STRUGGLING organizations (8 of them) behave like TYPICAL ones (`org_quality.fix_list_adoption`, off by default).
> Reproduce with `make fix-list-demo`. The warehouse is not changed: everything is rebuilt in a copy.

## Purpose scores of the organizations that acted, final season

Mean PURPOSE_SCORE (0 to 100) of organizations that reported in the season. *Before* is the current build, *after* the scenario. The STRUGGLING organizations that did not act are the comparison, because switching the scenario on reshuffles where defects fall (overall rates unchanged).

| Purpose | Adopters before | Adopters after | Change | Comparison before | Comparison after | Change |
|---|---|---|---|---|---|---|
| COUNT | 97.2 | 99.1 | +1.9 | 98.0 | 98.1 | +0.1 |
| SEGMENT | 94.2 | 98.6 | +4.4 | 97.6 | 96.7 | -0.9 |
| GEO | 91.3 | 95.5 | +4.2 | 94.1 | 91.8 | -2.3 |
| RETAIN | 88.4 | 97.3 | +8.9 | 94.9 | 93.5 | -1.5 |
| ACTIVATE | 59.5 | 63.2 | +3.8 | 64.8 | 64.3 | -0.5 |

Organizations scored: 6 adopters that reported, 9 comparison organizations.

## The nuance layer, final season

| Measure | Before | After |
|---|---|---|
| DQ-exclusions component: participants lost if only COUNT-fit records are counted | 25 | 24 |
| Girls' share of youth: participants with unknown gender | 36 of 6592 | 31 of 6590 |
| Girls' share of youth: width of the bounds (no imputation) | 0.0054 | 0.0047 |

## How to read this

- A fix at the source shows up clearly in the organizations' own scores (the retention and segmentation purposes most) and narrows the missingness bounds and the DQ-exclusions component only slightly, because the headline uncertainty is mostly coverage (organizations that sent no file), which a fix list does not touch. The cheapest way to improve an organization's numbers is upstream; it does not close the coverage gap.
- What is simulated: that organizations act, and that acting makes them look like TYPICAL organizations for one season. What is not: any real organization, any real effect size.
- The scenario regenerates the data, so small movements elsewhere are noise from where defects fall. Read the adopters against the comparison column, and read changes of a point or two as noise.
- Whether a real fix list changes behaviour is an open question for the program owner; this demo cannot answer it.
