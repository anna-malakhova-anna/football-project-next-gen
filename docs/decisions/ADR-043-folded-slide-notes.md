# ADR-043: The notes in the slide view start folded and open upward

- **Status:** Accepted, 2026-10-27, at Anna's request. She confirmed the behaviour first (folded by default, slide view only).

## Decision
- **Folded by default:** in the full-screen slide view on every page, the notes under the chart (What this means / What to do / Be careful) start folded. A slim bar sits at the foot of each slide, reading "▲ What this means · What to do · Be careful".
- **Opening:** clicking the bar slides the notes up over the lower part of the chart, and the arrow flips. The choice holds as you move between slides. The bar is a real button (`aria-expanded`, `aria-controls`).
- **Labels:** the bold labels are green accents, a lighter green in dark mode.
- **Unchanged:** the cards on the page keep their notes open, as before.
