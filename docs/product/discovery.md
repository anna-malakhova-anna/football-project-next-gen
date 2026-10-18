# Discovery (Stage 0): who the products are for

> **There are no real users.** This is assumption-based discovery: one persona per consumer, what we assume about their pain, and the questions we would ask in real interviews before building more. Skipping the interviews is a gap, stated here, not hidden.

All roles are fictional. The league operator is a **supplier**, not a consumer (see below).

| Persona (fictional role) | Goal served | Job to be done | Current pain (assumption) | Validation questions |
|---|---|---|---|---|
| **International growth lead** | G1 | Decide which countries to invest in | Federation returns are inconsistent, so there are no comparable counts across countries | "Which decisions did you make last year without data?" "What would a country count have to look like for you to trust it?" |
| **NFL FLAG domestic operations lead** | G2 | Know where flag is growing and where leagues are struggling | League data is sparse and uneven; growth cannot be told apart from better reporting | "Which numbers do you distrust today, and why?" "What do you do when a league sends nothing?" |
| **Club youth and community manager** | G2, G3 | Grow flag in our market and connect families to the club | Cannot see their own market and do not know how much is missing | "What would you do differently with a market view?" "How would you want to hear about a gap?" |
| **Fan and club marketing analyst** | G3 | Show that flag creates fans, and reach families who agreed to be reached | Linkage gaps, unclear consent, and children's data is off limits | "What evidence would convince finance that flag drives fandom?" "What would you accept as 'consented'?" |
| **Privacy and compliance lead** | G3 (guardrail) | Make sure children's data is never misused | Consent wording varies, purposes blur together, and retention is unclear | "What would make you comfortable approving club access?" "Which purposes need their own consent?" |
| **League operator (volunteer)** | G2 (supplier) | Run the league and send the data that is asked for | Too many fields, and no clear reason for each | "What is the most you would fill in at registration?" "Which question would you drop first?" |

## Why the league operator matters even though they are not a consumer
The operator supplies every record. If registration asks for too much, data arrives late, partial or in the wrong shape, and every downstream product inherits the gap. The **minimum data standard** (Phase 5, `docs/data-standard.md`, ADR-018) exists because of this persona: it asks for the fewest fields that still let the products work. The league operator receives a **fix list** (Phase 5) in return, so supplying data has a visible benefit.

## What we would do with real interviews
1. Replace the "assumed pain" column with quotes, and drop any assumption interviews contradict.
2. Rank the validation questions by how much a wrong answer would change the roadmap.
3. Record the answers in this file with the date and role (never a name), and re-score `product_prioritization.csv` where they change a score.
