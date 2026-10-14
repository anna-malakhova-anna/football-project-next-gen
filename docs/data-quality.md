# Data quality, explained

> For the people who use the numbers, not the people who build them. All data in this project is **synthetic**. Where a statement is about how the real world works, it is labelled an assumption.

## The idea in one sentence
**Quality is fitness for a purpose.** The same registration can be good enough to count and not good enough to contact a family, so every score in this project is computed **per purpose**, never as one overall number.

## The five purposes
| Purpose | The question | What it needs |
|---|---|---|
| **Count** | How many people played? | One record per person, a recognizable organization and season, no duplicates |
| **Segment** | How many girls, and in which age band? | An age signal, a recorded sex, a recognizable division |
| **Geography** | Which market? | A usable postal code |
| **Retain** | Do players come back? | A stable identity across seasons |
| **Activate** | Can a club contact the family? | A valid contact **and** a recorded, evidenced consent that names the purpose |

## How a score is built
1. **Rules are data.** Every check is one row in a registry (`dq_rule_registry`) with an owner, a dimension, the purposes it matters to, a threshold and a severity. Checks from the original build, from the source data contracts, from the data standard and from this phase live in the same place; none is written twice.
2. **Seven dimensions** group the rules: completeness, validity, uniqueness, consistency, conformity, timeliness and consent provenance (what was agreed, when, on which wording, for which purpose).
3. **A purpose score is the weakest dimension, not the average.** An average lets a perfect score on spelling hide a missing consent. The minimum says: the data is only as fit as its worst dimension for that purpose (ADR-014).
4. **Small organizations get an interval.** An organization with fewer than 50 scored records carries a Wilson confidence interval and is graded on its **lower bound**, so a five-record league with one error is not graded like a five-hundred-record league.
5. **Grades** are letters on fixed bands (A at 95 and above, B at 85, C at 70, otherwise D). A letter always sits beside the number and a colour; meaning is never carried by colour alone.
6. **Trend with limits.** Each source's score is plotted against limits implied by its own earlier seasons (a P-chart), so a real shift can be told from noise. A point outside the limits says the change is large, not why it happened.

## What a score does not say
- It is a statement about **fitness of the records for a purpose**, not about any organization's effort or intent.
- A grade is only as good as the rules in the registry; a defect nobody wrote a rule for is invisible.
- Coverage is separate: organizations that sent **no file** have no records to score. They appear as a coverage estimate (an interval), not as a grade.

## What a fix list is
For each organization and season, the top fixes ranked by **impact in the KPI's own units**: the participants (or, for activation, households) a rule's failures remove from a count, a segment, a place, a cohort or the contactable set. Each fix is worded as an action with the number of records it affects and a named owner role. Records are counted, never listed. Fixing upstream raises an organization's own scores; it does not close the coverage gap, because organizations that send nothing have nothing to fix. A simulated example is in `docs/reports/fix_list_demo.md`.

## Where to look
| You want | Look at |
|---|---|
| Grades for a source or organization | Site page *Data quality*; `make dq` |
| What costs the most | The impact Pareto (`mart_dq_impact`) |
| Why there is a range, not one number | Site page *How sure are we*; ADR-015 |
| Your market | Site page *Club markets*; `make markets` |
| The rules themselves | `dbt/seeds/dq_rule_registry.csv`; ADR-014 |
