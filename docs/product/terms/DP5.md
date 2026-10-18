# Terms of use: DP5 Flag-to-Fan Conversion Insights

> Synthetic project; every role is fictional. Plain-language terms, not legal terms. Project policy informed by public rules, not legal advice.

## Permitted uses
- Reading how much more engaged families who already followed the NFL become, always with the range and the naive companion.
- Reading how many new fan accounts flag creates among families who were not fans.
- Counting households a guardian has agreed to be contacted, by the age tier of the youngest child.
- Approving or refusing club access using the aggregate funnel.

## Prohibited uses
- Any child-level targeting or marketing, including to 13 to 17 year olds: under project policy every minor is guardian-only.
- Fuzzy household linkage.
- Carrying a youth profile over to the adult: an adult becomes their own fan record only with fresh consent at 18.
- Treating analytics as activation: counting a linked household is not permission to contact it.
- Concluding whether a club is a third party under any law: that is an open question for counsel.

## Who can request access, and how
The privacy lead approves every reader. Fan and club marketing see aggregates only. Request through the feedback issue template (label dp5). Club access is aggregate-only, and is refused until the guardian consent for club marketing is captured at registration (the gate for DP5 v1).

## Retention
Household-level working tables live in the restricted zones and follow the age-out rule (ADR-017). Published outputs are counts only.

## What happens when a published number is restated
A change to the consent rules, the age rules (ADR-022) or the uplift method restates the affected numbers and bumps the major version. The canonical engagement-lift metric is fan_uplift_pct (matched estimate); incremental_fan_accounts is a separate metric (fans created by flag).

## How to report misuse
Tell the privacy lead and open an issue with the label dp5. Never include a name, email or phone number.

## Age tiers and guardian consent (summary)
- Four tiers by age on December 31 of the season year: under 13, 13 to 15, 16 to 17, 18 and over (`docs/product/age-consent-rules.md`, ADR-022).
- Every household is evaluated through its guardian, never the child, and the youngest child governs. A blank is never a yes.
- The rules are project policy; every jurisdiction row is unverified until the program owner checks it, and the strictest row applies where unsure.
