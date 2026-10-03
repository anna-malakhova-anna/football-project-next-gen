# Flag football as fan acquisition

> **Synthetic data.** Every number in this memo describes a generated population, not a real program. **DRAFT SKELETON:** every heading, definition and number is in place; each prose paragraph is marked
> `<!-- DRAFT: Anna to rewrite -->` and is for Anna to write. Companion to [Counting a participant](counting-a-participant.md). Audience: a program executive and a privacy lead.
> Methodology version **2.0 (proposed: not yet approved or published; the pipeline still stamps 1.1, see the CHANGELOG).**

## 1. The question

<!-- DRAFT: Anna to rewrite -->
The first memo counts the children who register. This one asks what registering does for the sport's fan base: how many fans does flag football create, how engaged and valuable are they, and how many can the organisation contact. Fans here are fan-app account holders (adults). A child's own details never enter this analysis; every account holder is a guardian.

## 2. Fan status and why UNLINKED is not "non-fan"

<!-- DRAFT: Anna to rewrite -->
Each registered household has a fan status as of its first registration, from the linked fan account's engagement history. UNLINKED means no account could be linked: it is unknown, not a non-fan. In the latest cohort 2,158 of 3,171 registered households are unlinked, yet against the answer key about 23% of unlinked households actually have an account.

| Status | Definition (windows from `fan_params`) |
|---|---|
| NET_NEW | The linked account was created after the household's first registration |
| EXISTING_ACTIVE | Account existed and engaged within the last 90 days before registering |
| EXISTING_COOLING | Account existed, engaged within 180 days but not within 90 |
| LAPSED_REACTIVATED | No engagement for 180 days before registering, engaged again within 12 months after |
| LAPSED_DORMANT | No engagement for 180 days before registering and not again within 12 months |
| INSUFFICIENT_HISTORY | Account too new in the data to classify (left-censored) |
| UNLINKED | No account linked: unknown |

<!-- DRAFT: Anna to rewrite -->
Linking registrations to accounts is a governance decision (ADR-009): the linkage lives in a restricted schema, it is deterministic (email, then phone), one-to-one, and only aggregates leave it. Link precision is 99.2% (email 99.98%, phone 85.8%); recall is 71.7% of all participant households with an account, 91.2% of those whose emails match.

## 3. Acquisition is measured at market level

<!-- DRAFT: Anna to rewrite -->
Net-new households are not the programme's effect: some would have joined anyway, and households that are neither participants nor fans cannot be seen at household level. Markets launched in different years and some never launched, so launched and not-yet-launched markets can be compared (ADR-011).

| Estimate | Accounts | Against the truth (1,111) |
|---|---|---|
| Incremental, stacked cohort comparison (95% interval) | 1,264 (897 to 1,630) | 1.14x, truth inside the interval |
| Naive: net-new linked households | 939 | 0.85x |
| Naive: net-new scaled by link rate | 2,543 | 2.29x |

<!-- DRAFT: Anna to rewrite -->
The estimate is only as good as the assumption that launched and not-yet-launched markets would have moved together without the programme. The pre-launch cell is flat (about zero, interval -0.14 to +0.14 per 1,000 households), which supports it for the pre-years observed. In real data, markets are often chosen because they look promising, which this synthetic launch order does not reproduce.

## 4. Funnel, engagement and value

<!-- DRAFT: Anna to rewrite -->
The funnel counts registered households, then those linked to an account, active, contactable and monetized. Identity resolution is why the denominator is right: a child registered in several leagues is one household member, not several.

| Quantity | Definition | Result |
|---|---|---|
| Active | Engagement within the active window (90 days) | see site, Fan acquisition |
| Fan lapse | Gap of 6 months without engagement ends a spell; accounts active at the end of the data are censored | 12-month survival: existing fans 95%, net-new 89%, others 88% |
| Lifetime value | Net spend per active month x expected active months, 36-month horizon, synthetic currency | existing fans 387 (381 to 393), net-new via flag prompt 368 (352 to 383) |
| Value uplift | Matched before/after difference per household-month, existing fans | events +0.211 per month (truth +0.182); see the value page |
| Engagement uplift | Matched difference-in-differences, linked households | naive +17.5% (0.99x the truth), matched +22.6% (truth +20.5%) |

<!-- DRAFT: Anna to rewrite -->
Lifetime value is an illustrative expectation in synthetic currency, not revenue. Its assumptions: spend per active month is constant, the lapse curve is Kaplan-Meier from observed accounts, and the horizon is 36 months. A lapsed fan can return, so a lapse after a child stops playing is a rate (1.7x higher per account-month than while the child plays), not a certainty.

## 5. The addressable audience and the consent gap

<!-- DRAFT: Anna to rewrite -->
Governance determines the size of the marketable audience. A household is contactable when its guardian's account has at least one channel opted in; no consent record is not a "no" and is never counted as contactable. In December 2025, 3,511 of 13,043 registered households were contactable; 803 active households (about 25% of the active) had no opt-in at all, the consent gap, worth about 96,360 in synthetic currency at the median monetized household's spend (an opportunity size, not revenue).

<!-- DRAFT: Anna to rewrite -->
Consent history is resolved by timestamp, with an out-of-order flag. A residue remains: 58 of 96,660 account-channels resolve wrongly, all in the unsafe direction, 55 flagged and 3 not visible from the data. Any contact use must fail closed on flagged accounts. In this project nothing linked reaches marketing or media at all (ADR-009); the audience is shared as counts.

## 6. Guardians only

<!-- DRAFT: Anna to rewrite -->
Every fan account holder is an adult (an ERROR in the data contract and a dbt test). A minor's own contact details are never shared. The analysis describes households through their guardians' accounts and never profiles a child.

## 7. What this memo does not claim

<!-- DRAFT: Anna to rewrite -->
- It does not claim a real programme's effect: markets, households and accounts are synthetic.
- It does not claim the unlinked households are non-fans, or that linked households represent all households (they are mostly North American and register with an email the app also holds).
- It does not claim causal value for the groups it compares (existing, net-new, lapsed): they are not randomly assigned.
- Market launch timing in the generator is exogenous; real launches are not.

## 8. Version and changes

<!-- DRAFT: Anna to rewrite -->
Proposed version 2.0 adds the fan KPIs (net-new, incremental, funnel, audience, consent gap, fan survival, LTV, market quadrants), none of which restates a published participation number. See the CHANGELOG entry for what the bump would publish and what the restatement log would show.
