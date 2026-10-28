# ADR-040: One compact dark style for every clickable button

- **Status:** Accepted, 2026-10-27, at Anna's request: the buttons were too big, and all of them should be dark, turning grey only when clicked.

## Decision
Every clickable button that used to be green shares one style (`site_src/styles/site.css`). That covers:
- the walkthrough and one-page summary buttons;
- the Global outlook's link to Data products;
- the Club / Privacy lens toggle;
- the purpose buttons on the market and quality cards;
- the page links on the landing page.

The style:
- **Shape:** compact (a normal text size, 6px corners), sized to its label, not to its box.
- **Colour:** dark, with a light edge in dark mode so it stays visible.
- **Clicked:** grey while pressed; the selected option of a toggle stays grey.
- **Phones:** at least 44px tall, so they stay easy to tap (ADR-037).

The full-screen viewer's toolbar keeps its yellow highlight, which was never green.
