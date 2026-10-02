# Identity resolution: turning registrations into people

> **All data here is synthetic.** The people, families and results below describe a generated population, not a real
> program. Numbers come from `make phase2` (seed 42) and are repeatable.

## The problem

The program receives registrations, not people. One child can show up as a US league registration in spring, another in
fall, a Canadian club record after a move, and a federation return abroad. Every participation number we publish depends
on deciding which of those records are the same child.

There are two ways to get it wrong, and they are not equally bad:

- **Counting one child twice** (under-merging) inflates participation and makes it look as if children drop out and
  new ones arrive. It is a reporting error.
- **Counting two children as one** (over-merging) undercounts participation. Worse, we could attach one child's consent
  (photos, marketing) to a sibling who never gave it. That is a privacy incident.

**Twins are the hardest case.** Two children in one family can share a guardian email, a phone number, a last name, a
birthday, a league and a season. Only a first name differs. A matcher that adds up "everything matches" will merge them.

## How matching works

1. **Blocking.** Comparing every record with every other would mean 97 million comparisons. We only compare records that
   share something plausible (the same birth year and the start of a surname, the same email, the same phone, the same
   name). That leaves 66,826 pairs to compare, and in this data it loses only 6 of the 27,951 true matches.
2. **Comparing.** For each pair we record how well each detail agrees: the first name (exact, a known nickname like
   Robert and Bob, close, different), the surname, the date of birth (including a swapped day and month, or only the
   year known), the email, the phone, the postal code, the sex, and whether the two were registered in the same league
   and season.
3. **Scoring.** Two matchers do this. A **rules baseline** applies six simple rules. A **probabilistic matcher**
   (Fellegi-Sunter) adds up evidence: each agreement is worth more if it is rare among unrelated pairs (a shared birthday
   is strong, a shared sex is almost worthless). Every score comes with a plain-language reason and a line-by-line
   breakdown.
4. **Guardrails.** Some evidence is too important to leave to a sum. Two different first names in the same league and
   season, or the same contact details with clearly different first names, can never be merged automatically. A date of
   birth that disagrees can never be merged automatically either.
5. **Reviewing.** Pairs the matcher is unsure about, and merged groups that look suspicious, go to a review queue for a
   person to decide.

## Results

Measured against the answer key the generator kept (the matcher never saw it). "Pair" accuracy asks, for every two
records, whether they were put together correctly.

| Matcher | Right when it merges | Finds the true matches | Sibling/twin groups merged in error | People counted vs actual |
|---|---|---|---|---|
| Rules baseline | 99.94% | 92.3% | 2 | 6,513 vs 6,000 |
| Probabilistic, as first built | 96.3% | 100.0% | **86** | 5,906 vs 6,000 |
| **Probabilistic, final** | **99.91%** | **99.96%** | **2** | **6,000 vs 6,000** |

*(automatic merges only; before any human review. 755 of the 6,000 people have a brother or sister in the data.)*

- The first probabilistic version failed in exactly the way described above: email, phone and postal code all say "same
  household", so it counted one fact three times and merged 86 sibling or twin groups. We fixed the model structure and
  said so openly; the history is in [ADR-003](decisions/ADR-003-identity-resolution.md).
- The rules baseline almost never merges a sibling (the same two as below), but it misses 7.7% of true matches (anyone with a misspelled surname, a
  swapped birth date or an unreadable birth date) and so **overcounts people by 8.6%**.
- The final matcher counts 6,000 people against the true 6,000, partly by luck: four wrongly separated people and four wrongly
  merged groups happen to cancel out.
- **Extending the data from three to five years exposed a limit.** Two groups of Canadian siblings with the same first and last
  name, born in the same year, were merged. Canada records only a birth year, so nothing tells them apart; both matchers do it. We
  report it, and did not tune anything to hide it.

## Why we chose to be careful rather than complete

We would rather leave a child's records apart than merge them wrongly. That is a **consent-protection** decision: a wrong
merge can apply one child's choices to another, while a missed match only means a child is counted twice until a person
confirms it. It is also a **trustworthy-counts** decision: a merge we cannot explain is a number we cannot defend. So the
guardrails above deliberately accept a small loss. The cost shows up in the results: five genuinely matching pairs (people
whose first name differs between registrations, usually a mistyped first letter, but whose contact details are identical) are kept apart.

## What a data steward does

The review queue lists, in priority order, groups of records that look suspicious ("split this cluster") and pairs the
matcher is unsure about ("confirm match" or "confirm non-match"), each with both records side by side, the reasons for the
score and a suggested action. The steward's decision, **match** or **no match**, is saved to a small table and applied
the next time the pipeline runs: a match merges the two records, a no-match removes the link. Decisions stay in a
separate stage, so we can always report accuracy before and after human review.

> In this project the steward is **simulated**: a script resolves the top queue items using the answer key, only to
> demonstrate the loop. After the simulated steward resolved the top 20 queue items (246 decisions), the groups merged in error at the automatic
> setting fell from 4 to 2 (the two same-name sibling groups are not among those items). Those after-review numbers are **not** the matcher's accuracy and should never be quoted as such.

## What it can and cannot do

- **Name changes.** Three adult women appear under a new surname in a later season, with a new federation ID. Most are found, because
  first name plus an exact date of birth is strong evidence; a woman with a completely new surname and no contact details may never
  even be proposed as a candidate pair, so nothing can match her.
- **Families with the same details and the same birthday.** Twins, or siblings with the same first name and the same birth
  year (especially in Canada, where only the year is recorded), cannot be told apart by any of these signals. The matcher
  cannot send these to a steward, because it is confident.
- **Look-alikes with no contact details.** Two children with the same first name, a near-identical surname and the
  same birth year, one with only a birth year and the other with no email or phone, were merged in error (four pairs). Nothing
  in the data tells them apart.
- **No real-world validation.** Every number above is measured on a synthetic population in which phone numbers never
  change and one nickname list covers every case. Real data would score lower; the value of this work is that the method,
  the guardrails and the measurement are in place to find out by how much.
