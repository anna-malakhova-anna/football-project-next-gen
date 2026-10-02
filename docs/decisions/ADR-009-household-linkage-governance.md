# ADR-009: May we link participant households to fan accounts at all?

- **Status:** Accepted (Phase 4), decided by Anna on 2026-10-02: restricted-zone linkage is the project policy, the phone fallback stays on, and nothing linked ever reaches marketing. The default described below is what is implemented.
- **Context:** Source D (a fan app and ticketing feed) holds adults' accounts and what they do in the app. The registration data holds
  guardians' contact details, collected to run leagues. Joining them lets us ask whether being in the program changes how a household engages
  with the sport (ADR-010). That is a **purpose beyond running leagues**, and the people concerned never agreed to it when they registered.
  All data in this project is synthetic. **This ADR is project policy for a portfolio exercise, not legal advice.** A real organization
  would put the same questions to its privacy counsel before building any of it.

## The question
Is it acceptable to use registration contact data to find fan accounts, and if so, under what limits?

## Purpose
**Aggregate program-impact analysis only**: how engagement differs for households before and after their first registration, and how that
differs from similar households that never registered. No individual household's behaviour is ever the output.

## Position taken for this project (the default, implemented)
A legitimate-interest-style rationale, **limited to aggregate analytics in a restricted zone**:

1. **Restricted `linkage` schema.** The household construction (`int_household`, `int_household_profile`), the links
   (`link_household_fan_account`) and everything computed on linked households live in schema `linkage`. It is the only place registration
   contacts and fan accounts meet. Nobody receives access to it through a share.
2. **Only aggregates leave it.** The only models outside `linkage` that may depend on it are named, aggregated and small-cell-suppressed outputs
   in `share_exec` and `share_analyst`. `scripts/check_share_policy.py` fails the build if any other share touches `linkage`
   (`LINKAGE_LEAK`), and a separate rule (`LINKAGE_IN_MARKETING`) fails it if `share_marketing` or `share_media` depends on `linkage` at all.
3. **Nothing linked is used for contact.** A linked account is never added to a marketing list. The path "marketing is allowed if
   `consent_marketing = TRUE` on **both** the registration and the fan account" is deliberately **not implemented**: it would be a second
   purpose again, with its own consent question. If it were built it would have to require both consents and fail closed on NULL
   (NULL means not captured, never yes).
4. **Deterministic, explainable links only.** Email equality, then phone equality, one to one, every link with its reason. No fuzzy matching
   (see "Why no fuzzy matching" below).
5. **Contacts stay inside.** `int_household_profile` holds contact values, so it is restricted. Reports of the linkage (`linkage_summary`,
   `linkage_link_bias`) are counts and shares only.
6. **The link rate is reported with its bias.** A linked household is not a typical household (see the numbers below). Analyses say so.

## Why no fuzzy matching
Phase 2 matches *records of the same person* where a wrong merge is a data-quality error that a steward can undo. A wrong link here puts a
family's fan behaviour next to their children's registrations, and nobody can see it was wrong. The risk profile is different, so the rule
must be one a person can check by eye: the same normalized email, or the same normalized phone. We would rather miss a link than invent one.

## What the default costs, measured on the synthetic data (2021 to 2025)
Observed households 5,186 (true 5,069 in the data; 98 true households split in two because their contacts never overlapped; no observed
household mixes two families). Of the 2,536 participant households that have a fan account:

| Measure | Value |
|---|---|
| Links made | 1,855 (1,742 by email, 113 by phone) |
| Precision | 98.7% overall; **100% by email, 78.8% by phone** (24 false links, all accounts that reuse a participant household's phone) |
| Recall (of participant households with an account) | 72.2%; 91.6% among accounts whose email matches the registration email |
| Link rate (correct links / all participant households) | 35.3% |
| Households with a link, by country | US 39.6%, CA 41.7%; international 14% to 21% (minors' emails are often blank on international returns, and those returns carry no phone) |

The unlinked are not a random sample. Linked households are mostly North American, so any result describes US and Canadian households that
use the fan app and register with a guardian email the app also holds.

**The phone fallback is the weak part.** It adds 89 correct links and 24 false ones. It is a project switch (`linkage_phone_fallback`, default
true, as the Phase 4 spec asks). Turning it off gives 100% precision and a lower link rate. This is a decision for the owner, not a tuning
knob: see the marker.

## Re-measured after the rework (the decision above was taken on the earlier numbers)
The fan-acquisition rework regenerated the data (15,000 people, staggered programme rollout, a revised fan source with duplicate accounts). On the new data: 13,043 observed
households (231 true households split in two, none mixed); of the 6,830 participant households that have a fan account, **4,682 were linked (35.9% of all participant households)**.
Email links are 100% precise (4,454); **phone links 88.4% precise (258 links, 30 false, all accounts that reuse a participant household's registration phone)**; overall precision 99.4%;
recall 68.6%, or 86.1% among accounts whose email matches the registration email. Link rate by country: US 40.2%, CA 40.2%, international 13% to 21%. The earlier figures
(phone precision 78.8%, link rate 35.3%) were measured on 6,000 people; the conclusion, that phone is the weaker key and the linked households are mostly North American, stands, and
the decision to keep the phone fallback was taken knowing it. The rework spec's household may link to several accounts (duplicates); that extension arrives in rework step 4.

## The alternative: explicit research / analytics consent at registration
Add a consent field ("may we use my registration details with my fan account for program research?") and link only households that said yes.
That is cleaner: the purpose is stated to the person, and a NULL means no link. The cost is **coverage**. Opt-in rates for such a field are
typically a fraction of registrants, existing registrations have no answer (NULL: not captured), so history 2021 to 2025 could not be used
and the analysis would start only when enough new registrations carry the field. It also changes three source contracts. It is the
better design if the program wants to publish findings about households; the default is the better design if it only wants aggregate
internal learning and accepts the restricted-zone controls above.

## Consequences
- Results from linked households are labelled as describing linked households (ADR-010 repeats the caveat).
- `share_exec` / `share_analyst` may carry only the approved aggregates listed in `scripts/check_share_policy.py`; each is suppressed with the
  same small-cell rule as the other shares.
- The synthetic nature of the data means the measured precision and link rate are properties of the generator (25% of participant households
  have an account email that differs from the registration email; 1% of non-participant accounts reuse a participant's phone number), not
  estimates for a real program.

<!-- DECISION: Anna (resolved 2026-10-02: see below) -->
**The three questions put to Anna, and the answers:**
1. Is aggregate linkage in a restricted zone acceptable for this project, or should the explicit-consent alternative be the policy?
2. If the default stands: keep the phone fallback (more links, 78.8% precise) or switch it off (email only, 100% precise)?
3. Is "nothing linked reaches marketing, even with both consents" the right position, or should the both-sides consent path be built?

**Decisions so far**
- **Question 2, phone fallback: keep it.** Decided by Anna, 2026-10-02. Phone links are 78.8% precise (24 false links out of 113, all accounts that reuse a
  participant household's number) against 100% for email, and add 89 correct links. The switch (`linkage_phone_fallback`) stays on; results from linked households
  carry this caveat.
- **Question 1, policy: restricted-zone linkage.** Decided by Anna, 2026-10-02. Aggregate program-impact analysis in the restricted `linkage` schema under the
  legitimate-interest-style rationale above (project policy, not legal advice). The explicit-consent alternative is **not** adopted; it stays documented as the option
  to move to if the program ever wants to publish findings about households, and it would cost the 2021 to 2025 history.
- **Question 3, marketing: keep "never".** Decided by Anna, 2026-10-02. Nothing linked reaches `share_marketing` or `share_media`, even where both the registration
  and the fan account have `consent_marketing = TRUE`. The both-sides consent path is not built; if it ever were, it would be a second purpose with its own consent question
  and would have to fail closed on NULL. `scripts/check_share_policy.py` enforces the position (`LINKAGE_IN_MARKETING`).

**Decision:** restricted-zone linkage as the policy; phone fallback kept; marketing never.  **Decided by:** Anna  **Date:** 2026-10-02
