# Results site: fix list

The NFL shield in the top bar must be removed before anyone sees the link. The rest is ranked by how likely an interviewer is to notice.

## Blocking

- [ ] **Remove the NFL shield logo from the top bar on every page.** It's the league's trademark on an unaffiliated site, directly above a footer saying the site isn't affiliated. The brand-boundary check evidently scans text but not images or SVG. Replace the shield with an original mark (e.g. a yellow line on a turf square), and extend the check to images, inline SVG and favicons.
- [ ] **Remove "(draft)" from the Trust page** next to `docs/methodology/flag-as-fan-acquisition.md`. Finish that memo in your own words first.

## Fix before an interview

- [ ] **The Value page contradicts the project's main story.** Naive uplift is +17.5%, below the synthetic truth of +20.5%; the matched estimate is +22.6%, above it. Everywhere else, the site argues that naive comparisons overstate. The diagnostics table points to the likely cause: matched participants have latent fandom of 0.826 vs 0.635 for matched comparisons, so matching on observed engagement didn't balance the underlying fan inclination. Either explain this in a plain sentence on the page or fix the matching (e.g. match on a longer engagement history).
- [ ] **Replace raw code names in charts and tables with plain labels.** Examples: `EXISTING_ACTIVE`, `DID_ADDITIVE`, `UNLINKED_OR_NON_PARTICIPANT`, `audience_contactable_email`, and every column in the "Why the matched engagement estimate is where it is" table. Keep model names only in source lines.
- [ ] **The acquisition event study has only one pre-launch point.** "A flat pre-period supports the design" rests on year −2 alone. Either say so on the page, or extend the generator so more markets have two or three pre-launch years. Also change the x axis to whole years (it currently shows −1.8, −1.6, …).
- [ ] **The market quadrants split near-identical values.** Every market has 10–13 fan accounts per 1,000 households, so "fan base thin" vs "strong" is a difference of about 1. Either give the generator real variation in fan density, or zoom the y axis and state that the split is weak.
- [ ] **"What changed after publishing: No rows" reads as broken.** Show the worked restatement examples from `docs/reports/restatement_demo.md` instead.
- [ ] **The suppression example shows nothing suppressed.** Pick a cut (e.g. sex × small country) where primary and secondary suppression actually fire.
- [ ] **The drive-chart funnel isn't built.** The UI spec made it the site's signature element; the Acquisition page uses grouped bars instead. Build it, or drop it from how you describe the design.

## Polish

- [ ] **Funnel:** dormant households have no bars for Active and Monetized because they're zero by definition. Label it so it doesn't look like missing data.
- [ ] **Participation trend:** the identity band is too narrow to see. Add a note under the chart so readers don't assume it's missing.
- [ ] **Participation growth:** the jump from 1,408 to 8,959 comes from markets launching in successive years. Say so under the chart, or someone will ask whether flag grew 6x.
- [ ] **Retention by entry age:** the legend sorts as text (`0-7, 10-11, … 8-9`). Sort by age.
- [ ] **Chart colours:** charts use default Vega colours, not the spec palette, and naive series aren't dashed. Low priority, but it's what makes the site look designed.
- [ ] **Number formatting is mixed** (`13,043` vs `4665`). Use thousands separators everywhere.
