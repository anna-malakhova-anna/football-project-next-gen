# Phase 6: why "naive" sits where it does, and the baselines behind the draft targets

Read-only diagnostics on the 2026-10-18 warehouse (the build that passed `make all-phases` on 2026-10-15). **Nothing was changed or tuned.** Synthetic data. Where the answer key was used it is marked "truth" (evaluation only).

## 1. The three "naive" figures: exactly how each is defined

| Figure | Definition (from the model) | Value | Truth |
|---|---|---|---|
| **Value page, naive uplift** (`mart_fan_naive`, estimator `NAIVE`) | For every **linked participant household's fan account** (existing accounts and net-new accounts alike), mean events per month from the household's first registration month on, divided by the mean of **all unlinked fan accounts in the same calendar months**, minus 1. Ratio of account-level sums, delta-method range. | 16.5% (13.6 to 19.5) | 17.6% for the population and window it averages over (`eval_fan_effect`) |
| **Value page, matched uplift** (`DID_ADDITIVE`) | Additive difference-in-differences on **accounts that have a pre-period** (2,697 treated households), matched to comparison accounts (coarsened exact matching), as a share of the counterfactual post level. | 20.0% (17.6 to 22.4) | 20.5% |
| **Acquisition, naive "observed"** (`naive_net_new_observed`) | Count of linked households whose fan status is `NET_NEW` (no account before the first registration) in the launch cohorts 2022 to 2024. Counts only **linked** households. | 743 | 1,111 fans created |
| **Acquisition, naive "scaled"** (`naive_net_new_scaled`) | The observed count divided by the link rate of the same cohorts (about 0.37). Corrects for the households that cannot be linked, but still counts every net-new account, **including ones that would have been opened anyway (organic)**. | 2,019 | 1,111 |
| **Incremental accounts** (the estimate) | Stacked cohort comparison of launching markets with not-yet-launched markets. | 1,264 (897 to 1,630) | 1,111 |

Note on the truth column: the earlier report said "truth 20.5%" for both uplift estimators. That is the **matched** truth. The naive estimator is graded against its own population and window (17.6%).

## 2. Is the selection-on-fandom parameter producing selection? Yes

Config: `fan.selection = {intercept -0.4, slope 0.9}`, so households with higher latent fandom are more likely to enroll a child.

| Check | Enrolling | Not enrolling | Reading |
|---|---|---|---|
| **Pre-period engagement** (label-free): events per account-month before the first registration, candidate accounts before matching | 0.987 (2,697 accounts) | 0.898 (126,558 accounts) | Enrolling households were already **about 10% more engaged** before enrolling |
| Pre-registration months of linked accounts vs unlinked accounts in the same calendar months | 1.020 | 0.920 | The same gap: **+10.9%** |
| **Latent fandom** (truth, evaluation only): mean over accounts | Existing active participant accounts 0.885; lapsed 0.59 to 0.66 | Non-participant accounts 0.486 | The selection is real |

## 3. So why is the naive uplift below the matched one?
Because the naive comparison **pools two different kinds of linked account**:
- **Existing accounts** (3,006 in the naive sample): naive uplift **+22.4%**. Selection pushes it up, as designed: above the matched truth (20.5%) by about two points. Here the naive does overstate.
- **Net-new accounts** (1,219): naive uplift **+2.7%**. These are accounts the programme itself caused, and their holders are low-fandom households (latent fandom 0.205, **below** the non-participant mean 0.486). They engage less than the average unlinked fan, and they pull the pooled figure down.
- Pooled across both, 16.5%. The matched estimator uses only accounts with a pre-period (existing accounts), so it is not diluted.

Conclusions
- The selection parameter works. The naive figure is not broken; it **mixes populations**. On its own population it is close to its own truth (16.5% against 17.6%).
- The two uplift figures are not comparable as "naive versus corrected" for the same households, which is why the direction looked wrong. This is a **definition issue, not a tuning issue**.
- Acquisition's two naive counts sit on opposite sides of the truth because each fixes a different bias: "observed" ignores households that cannot be linked (too low), "scaled" corrects for linkage but not for organic accounts (too high). Phase 4's design promised that the naive claim overclaims; only the scaled version does.

**Options, none applied (Anna decides):** (a) keep both, and label the Value naive as "all linked accounts, including accounts the programme created"; (b) add a naive companion on the same population as the matched estimate (existing accounts only, +22.4%), so the pair reads as selection overstating by about two points; (c) both. I would choose (c) and name the matched estimate the canonical one. Nothing in the generator needs to change.

## 4. Baselines for the draft targets (2025 unless stated)
| Draft target (Anna, 2026-10-18) | What exists today | Baseline | Meets the draft? |
|---|---|---|---|
| **X:** COUNT-fit at least 95% and GEO-fit at least 85% (US) | **Record level** (US league, `dq_record_fitness`): fit for counting **95.1%**, fit for the map **95.6%**. **Purpose score** (US league scorecard, the minimum of the check scores): COUNT **82.1** and GEO **82.1**, both grade C | Two different measures; see the question below | Record level: yes (counting only just). Score: no (C, below 85) |
| **Y:** identity range at most 3% | Identity range for the 2025 count: 7,405 to 7,437 around 7,430 | **0.43%** wide | Yes |
| **Z:** consent wording known for at least 80% of households | Households with known consent provenance in the activation funnel: 5,444 of 6,791 (**80.2%**); of households with any consent event, 83.3%. Share of consent events whose form is known: 100%; fully known (form, time and purpose): 50.2% across feeds | 80.2% on the household definition | Yes, by 0.2 points; "fully known" is 50.2% by events |
| **N:** at least 3 federations contracted | One contract (`contracts/INTL_FED.yml`) covers the federation workbook, one sheet per country. Six countries have organizations in the registry (AT, DE, GB, JP, MX, PA): 33 known organizations, 26 sent a file in 2025 (7 did not) | 1 contract, 6 countries, 26 of 33 organizations reporting | There is no per-federation contract in the data. If "federation" means a country with a reporting organization, 6 is already at least 3 |

Question for Anna: **X** reads like the purpose score (95 and 85 are the A and B grade lines), but the record-level fitness is already above both. Which do you mean? Likewise **Z** and **N** need a definition: Z by households (80.2%) or by fully known events (50.2%); N by contracts (1) or by countries reporting (6).
