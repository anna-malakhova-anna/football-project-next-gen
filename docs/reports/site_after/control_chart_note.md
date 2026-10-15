# Control chart (Q2): are the limits too narrow? A note for Anna

Status: **investigated, nothing changed.** The chart is built on the current limits and labelled provisional until you choose the method (ADR-020 will record it).

## What I measured (latest warehouse, all five seasons, purpose score)

| Points | Judged (at least 1 earlier season) | Flagged "out of control" | Share |
|---|---|---|---|
| Sources | 130 | 26 | 20% |
| Organizations | 2,550 | 525 | 21% |
| Sources, at least 3 earlier seasons | 50 | 9 | 18% |
| Organizations, at least 3 earlier seasons | 790 | 190 | 24% |

By size, the sources with 5,000 or more records are flagged most: 9 of 30 points (30%).

That is at your "about 20%" line, and the biggest sources are over it. A chart that flags one point in five is not telling you which changes are real.

## Why

The limits are a binomial P-chart: prior mean plus or minus 3 sqrt(p(1-p)/n), with n this season's record count. For a source with thousands of records the limits are a few points wide (US league, contacting families: 66.2 to 69.4). But the score moves 1 to 2 points a year for reasons that are not sampling noise (the mix of leagues and defects changes), so it keeps stepping outside. Small organizations are the opposite: limits about 45 points wide, so nothing is flagged.

## Options

1. **Keep the P-chart**, show only points with at least 3 earlier seasons. Honest to the current method; still flags 18% of source points.
2. **Individuals (XmR) chart on the score** (what the handover proposed): mean plus or minus 2.66 times the average season-to-season move. It ignores record counts. On the same points it flags 8 of 50 source points (16%) and 129 of 790 organization points (16%). Better, but with only 3 earlier seasons it rests on 2 moves, so it is noisy.
3. **Laney P-prime** (P-chart widened by the observed extra variation). The textbook fix for very large n; needs about the same number of seasons as XmR.

## Recommendation

Option 2 for sources, labelled "early read" until a source has 8 seasons, and no limits for organizations (too few seasons, too many points). Draw nothing for seasons with fewer than 3 earlier ones, as the handover says. This is a methodology change to `dq_trend`, so it needs your OK; it would also change the Q2 headline numbers.

Sources compared: `quality.dq_trend` (current), and an ad hoc XmR query run read-only on it.
