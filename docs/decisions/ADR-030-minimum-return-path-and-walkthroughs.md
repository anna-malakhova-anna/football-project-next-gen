# ADR-030: The minimum return has a path into market status; the Canada and Italy walkthroughs

- **Status:** Accepted for step 8 of the Phase 7 spec, 2026-10-26. Applies Anna's decision D8: walk Canada (a market with a signal) and Italy (no signal) through the playbook; Italy's onboarding runs on a copy of the warehouse.
- **Synthetic data.** Italy's federation and its first return are generated. The published build and tab keep Italy dark.

## Context
Italy's Discovery decision is to ask only for the minimum return: counts by region, age band and sex, never player-level records (ADR-027). Market status (ADR-025) only knew player-level sources, which have a counting grade. A market that sent the minimum return would therefore have stayed dark, which is wrong.

## Decisions
1. **A path for minimum returns into market status**, part of the published pipeline:
   - **Raw table:** `raw.gmp_minimum_return`, landed by `loader/load_phase7.py` from `minimum_return_<country>_<season>.csv` files. When none exists (the published build), the table is created **empty**, so every model always has it.
   - **Staging:** `stg_gmp_minimum_return` takes the market from the file name and re-runs the template's checks as flags. It is aggregate-only in `check_lineage`.
   - **Status:** a market whose only data is a minimum return for the latest season reads **Partial**. The reason says why: counts only, no counting grade, no like-for-like direction yet, and how many rows fail the template checks, if any. The participation source reads `GMP_MINIMUM_RETURN`.

   This adds a branch to the Partial rule of ADR-025. It changes nothing for the 22 markets today, and the published status counts are unchanged (5, 2, 9, 6).
2. **Privacy risk in the draft priority rubric is keyed to player-level sources** (`INTL_FED`, `CA_CLUB`), not to "any source". A market sending only the minimum return scores the aggregate level (2), not the player-level level (4). The experiment exposed this: Italy's risk had jumped to 4 on counts only.
3. **The Italy experiment** (`scripts/p7_italy_experiment.py`, `make p7-italy-experiment`) runs on a **copy** of the warehouse, and the script checks that the published file is unchanged:
   - a synthetic first return for the latest season is generated (`generator/phase7/italy_return.py`; its total is the answer key's count);
   - it is checked against the template contract with the same validator as every contract;
   - the global-outlook models are rebuilt on the copy;
   - Italy is compared before and after.

   The report (`docs/reports/p7_italy_experiment.md`) and CSV (`docs/eval/p7_italy_experiment.csv`) are generated. The experiment is not part of `make all-phases`.
4. **The walkthroughs** (`gmp_walkthrough_stages`, then `share_exec__gmp_walkthrough`, DP6 port `global_walkthroughs`): each market's six playbook stages, Discovery to Production, with:
   - the state: done, experiment (on the copy) or not started;
   - the artifact (a test checks each one exists);
   - what happened, in plain words;
   - the market's **live** status and grade from the published build.

   Italy's Discovery decisions and regime questions are in `docs/playbook/onboarding_log_IT_minimum_return.md`.

## What the experiment showed
- **Checks:** all 10 template checks passed.
- **Status:** Italy moved from **Dark to Partial**, and the market counts became 5 Measured, 3 Partial, 9 Proxy-only, 5 Dark.
- **Direction:** "not detectable" (one season of counts).
- **Scenario:** retired, since the market now has data.
- **Priority:** the draft rose from 3 (rank 16) to 6 (rank 7), with feasibility going from 1 to 4.
- **Size:** the return reports **396 players**. Italy's planning scenario was **29 to 79**, so the scenario missed by a factor of about 5. This is the same story as the evaluation (ADR-026), told for one market.
- **Not shown:** a real federation's return would carry its own errors. This one is built to pass, so the walkthrough shows the path, not the friction. Italy's board gate stays "proxy return filed" until Anna moves it to "seasons of minimum return".
