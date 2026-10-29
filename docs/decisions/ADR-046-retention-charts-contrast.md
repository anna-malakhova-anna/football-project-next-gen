# ADR-046: The two retention charts on Participation: small multiples by age, and two contrasting colours by sex

- **Status:** Accepted, 2026-10-28, from Anna's review ("figures 4 and 5 don't have enough contrast"). Display only: no dataset, number or method changed.

## What was wrong
- **Retention by entry age band:** 8 bands on one plot shared the theme's 5 series colours, so pairs of bands had the same colour. The 8 overlapping 95% bands washed together. The legend drew its swatches from the bands (12% opacity), so it was nearly invisible.
- **Retention by sex:** two dark colours (green and blue) for two lines that nearly coincide, a legend drawn from the pale bands, and the codes "F" and "M".
- **Both:** the x-axis showed 1.1, 1.2 and so on, when years since entry are whole years.

## Decisions
1. **Age bands become small multiples:** one panel per band, four across (two on a phone), on a shared 0 to 100% scale. One colour (sky, `#3D7CC9`), so the panels are compared by height, not hue. A ninth colour is never generated; facets replace it.
2. **Sex uses orange (`#D9622B`) and sky (`#3D7CC9`).** Validated with the data-viz palette checks on the light (`#FFFFFF`) and dark (`#1B3149`) chart surfaces: both pass every check, with contrast at least 3:1 and colour-blind separation ΔE 22.7. The second line is dashed, so it shows where it lies on the first. The legend is drawn from the lines. The labels read "Female" and "Male".
3. **Years since entry is a whole-year axis.**
4. **The chart theme colours facet headers** with the text colour, so panel titles keep their contrast in dark mode.
