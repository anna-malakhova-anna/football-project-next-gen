# Flag Football Project — Results Site UI Spec

**Goal:** Give the results site a confident, game-day broadcast feel, so it reads as built by someone who understands football media, while staying an **original design**.

**Scope:** Visual design, layout, and front-end build of `site/`. The data rules from earlier work are unchanged: static site, all numbers from `share_exec` or labelled evaluation summaries, no calculations in JavaScript.

---

## 0. Brand boundary (non-negotiable)

This is a personal portfolio project, not a league property. The site must not look like, or be mistakable for, an official league or team site.

- No league, team, or partner logos, shields, wordmarks, or mascots, including in favicons, images, or SVG
- No league or team names as visual branding (factual mentions in About or README prose are fine)
- No proprietary or licensed typefaces; Google Fonts only
- No copying of layouts, components, or page structures from any existing sports site
- Footer on every page: *"Independent portfolio project using synthetic data. Not affiliated with or endorsed by any league or team."*

A check script (section 9) enforces the text rules.

---

## 1. Design concept: "The drive chart"

Broadcast football has its own visual vernacular: yard lines, the drive chart, the highlighted line to gain, down-and-distance graphics. The site borrows that **vocabulary**, never anyone's specific graphics.

**The one bold element:** the fan acquisition funnel is drawn as a **drive chart**. A horizontal field runs from left to right. Each funnel stage (participant households → linked → contactable → active → monetized → retained) is a marker on the field, and the bar narrows as households drop off. The end zone is "retained fan." Everything else on the site stays quiet and disciplined so this lands.

**Supporting motif, used sparingly:** a single yellow **line to gain**, a reference line on charts marking the number that matters (a target, the true synthetic effect, the threshold chosen). Used at most once per chart, only when it carries meaning.

**Principles:**
1. Data first. Broadcast flavour lives in structure and type, not decoration.
2. Every number has a range or a caveat beside it. The data trust story is part of the design, not a footnote.
3. Sentence case throughout. No all-caps labels, no tracked-out eyebrow text.
4. Motion only on load of the drive chart (the bar fills left to right once), and respect `prefers-reduced-motion`.

---

## 2. Tokens

### 2.1 Color

| Token | Hex | Use |
|---|---|---|
| `--night-field` | `#14263B` | Top bar, drive chart field, dark surfaces |
| `--turf` | `#2F6B4F` | Primary data series, active nav state |
| `--chalk` | `#F4F6F1` | Page background (light) |
| `--line-to-gain` | `#F2C230` | Reference line, focus ring, the single key highlight per view |
| `--pylon` | `#D9622B` | Warnings, suppressed cells, naive-estimate series |
| `--slate-600` / `--slate-400` / `--slate-200` | `#4A5866` / `#8A96A3` / `#D5DBE1` | Text, gridlines, borders |

Dark mode: `--chalk` → `#0F1C2C` background, `--night-field` → `#1B3149` surfaces, text inverts to `#E9EEF2`; `--turf` lightens to `#4C9A73`. Define tokens on `:root`, redefine under `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`. Add a theme toggle in the top bar.

**Data viz series** (colorblind-checked): turf `#2F6B4F`, sky `#3D7CC9`, pylon `#D9622B`, plum `#7D4E8E`, sand `#B8A06A`. Never encode meaning in color alone; pair it with labels or line styles. Naive estimates are always pylon and **dashed**; incremental/DiD estimates are turf and solid; the synthetic truth is the yellow line to gain.

### 2.2 Type

- **Display:** *Barlow Condensed*, weights 600 and 700, **upright** (not italic), sentence case. Used for page titles, section titles, and KPI numbers.
- **Body and UI:** *Barlow*, weights 400 and 500.
- **Numbers:** `font-variant-numeric: tabular-nums lining-nums` everywhere numbers sit in tables or KPI blocks. Verify the font supports it; if not, fall back to the system UI font for numerals only.
- **Fallbacks:** `"Barlow Condensed", "Arial Narrow", "Roboto Condensed", sans-serif` and `"Barlow", system-ui, -apple-system, "Segoe UI", sans-serif`

Scale (rem): 3.0 page title · 2.0 section title · 1.5 card title · 1.0 body · 0.875 meta. KPI numbers: 2.75 (desktop) / 2.25 (mobile). Line length for prose ≤ 72ch.

### 2.3 Space, shape, depth

- 8px spacing grid
- Border radius **by hierarchy**: 2px on chips and inputs, 6px on cards, 0 on the drive chart field (it's a field)
- Elevation: one shadow level for floating elements only (menus, tooltips). Cards use a 1px `--slate-200` border, not shadows.

---

## 3. Global layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ Synthetic data notice (thin chalk-on-slate strip, dismissible)       │
├──────────────────────────────────────────────────────────────────────┤
│ Flag Football Project   Acquisition  Value  Audience  Participation  Trust     Methodology  GitHub  ◐ │  ← night-field top bar
├──────────────────────────────────────────────────────────────────────┤
│ Page title (display)                        Season  [2022][2023][2024][2025] │
│ One-sentence question this page answers                                │
├──────────────────────────────────────────────────────────────────────┤
│ Content (max-width 1200px, left-aligned, 12-col grid)                 │
├──────────────────────────────────────────────────────────────────────┤
│ Footer: disclaimer · methodology version · last build · repo link    │
└──────────────────────────────────────────────────────────────────────┘
```

- **Synthetic notice strip:** plain sentence, e.g. *"All figures come from synthetic data generated for this project. Read how it was built."* (links to the Overview). Dismissal is remembered with try/catch-guarded localStorage.
- **Top bar:** wordmark is plain text in Barlow Condensed 700. No logo. Nav links are sentence case; the active page gets a 3px turf underline. Secondary links (Methodology, GitHub) sit right, in body weight.
- **Season selector:** a segmented control. Switching seasons swaps between **pre-exported per-season JSON files**. No calculation, only file selection. The URL reflects the season (`?season=2025`) so links are shareable.
- **Within-page tabs** (where a page has views, e.g. Attributed vs Presence): a smaller segmented control under the section title, never a second nav bar.
- Content is left-aligned. Prose blocks never span the full grid.

Mobile (< 720px): the nav collapses to a menu button; the season control becomes a native `<select>`; KPI rows stack; the drive chart rotates to a vertical "field" (top = own goal line, bottom = end zone).

---

## 4. Components

### 4.1 Drive chart (funnel)
- A field rectangle in `--night-field` with faint chalk yard lines at each stage marker
- A turf bar enters from the left and narrows at each stage in proportion to the count
- Each stage marker shows the stage name, count, and step conversion (e.g. "Contactable · 3,120 · 61% of linked")
- The `UNLINKED` group appears as a separate, hatched lane **below** the field, labelled "Unknown fan status (no linked account)". It never merges into the drive.
- A toggle splits the drive by fan status (net-new / reactivated / existing), as stacked lanes
- **Accessibility:** a visually hidden `<table>` with the same numbers, plus a "Show as table" button that reveals it

Build it as inline SVG generated server-side (in `build_site.py` templates) from the exported counts, so geometry is precomputed, not calculated in the browser.

### 4.2 KPI block
```
Net-new fans from flag households        ▲ 12% vs 2024
4,280                                    Range 3,960 – 4,410
Identity confidence: high                ⓘ Definition
```
- Number in display type; delta as a small chip (turf for up, slate for flat, pylon for down, with arrow glyphs for non-color meaning)
- The range always shows when one exists
- The "Definition" popover pulls its text from `metric_catalog.csv`
- Suppressed values show "Suppressed (fewer than 10)" in pylon text, not a blank

### 4.3 Estimate comparison ("matchup") card
For naive vs incremental vs truth comparisons:
```
How many fans did flag programs create?
Naive count            ───────────────── 1,840   (dashed pylon bar)
Incremental estimate   ──────── 610              (solid turf bar)
Synthetic truth        ┊ 580                     (line to gain)
Naive overstates by 3.2× — here's why  (link to methodology section)
```

### 4.4 Chart frame
Every chart sits in a frame with:
- A title stated as a finding where the data supports it ("Girls' share of youth players rose each season"), else as a question
- One line: **What this shows**
- One line: **What it doesn't show**
- Source line: model name + methodology version
- Download data (CSV of the exported series)

Chart rules: Chart.js or Vega-Lite (pick one; pinned version from an allowed CDN). Gridlines in `--slate-200`, no chart borders, direct labels on lines instead of legends where possible, confidence bands at 20% opacity of the series color.

### 4.5 Market quadrant
A scatter of markets (flag participation per 1,000 households vs fan accounts per 1,000 households), with median lines dividing it into four labelled quadrants (Acquisition white space, Engagement play, Program growth, Long-term build). Points are synthetic market IDs only. Suppressed markets are rolled up and noted.

### 4.6 Data trust strip
On every results page, a slim row under the page title: identity range %, open review items, sources on contract, and the methodology version, each linking to the Trust page. It is part of the page, not hidden in a footer.

---

## 5. Pages

| Page | Question in the subtitle | Hero | Supporting content |
|---|---|---|---|
| **Overview** | What this project is and how to read it | Short pitch + 5-minute tour links | Architecture diagram (Mermaid), why synthetic, how it was built |
| **Acquisition** | How many families become fans, and how many are new? | **Drive chart** | KPI row (net-new, incremental range, link rate); matchup card; event study chart with the line to gain at zero |
| **Value** | How engaged and valuable are flag families? | KPI row (active fans, 12-month fan survival, LTV range) | RFM segment mix by fan status; fan survival curves; existing-fan value uplift matchup card |
| **Audience** | How many can we reach, and what are we missing? | Addressable audience trend | Consent capture by partner and capture point; consent gap; market quadrant |
| **Participation** | How many play, and how sure are we? | Global trend with identity bounds | Attributed vs presence tabs; girls' share; player retention curves |
| **Trust** | Why these numbers can be trusted | Identity evaluation headline | Threshold sweep; error categories; contracts by source; restatement log examples; access model; ADR links |

The first visible chart on each page must stand on its own, with a finding-style title.

---

## 6. Copy rules

- Sentence case everywhere, including nav and buttons
- Name things by what they mean to a fan marketing team, not by model names. "Contactable households", not `mart_addressable_audience`. Model names appear only in source lines.
- Buttons say what happens: "Show as table", "Download data", "Read the methodology"
- Empty or suppressed states explain why and what to do ("Fewer than 10 households in this market. See the regional total.")
- No marketing superlatives

---

## 7. Technical build

- `scripts/build_site.py` renders Jinja2 templates in `site_src/templates/` into `site/`; data JSON per page and season goes to `site/data/`
- One stylesheet, `site_src/styles/tokens.css` + `site.css`, with no CSS framework. If Tailwind is preferred, use it only with the tokens above mapped into its config.
- Fonts from Google Fonts with `display=swap`, plus the fallback stacks
- `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">` and safe-area padding on the top bar and footer
- Favicon: an original simple SVG (e.g. a yellow line on a turf square). No league or team marks.
- No external images; icons are inline SVG drawn for this project or from an open-source icon set (Lucide)
- Works fully without JavaScript except the season switch and tabs; those degrade to links to per-season pages

---

## 8. Accessibility and quality floor

- WCAG AA contrast for all text, including chart labels; verify `--line-to-gain` is never used for text on chalk
- Visible keyboard focus (`--line-to-gain` 2px outline with offset)
- Every chart has a text alternative (the "What this shows" line plus a data table toggle)
- `prefers-reduced-motion`: no drive chart fill animation
- Lighthouse: accessibility ≥ 95, performance ≥ 90 on the Acquisition page (mobile)

---

## 9. Checks (add to CI)

- `scripts/check_brand_boundary.py`: fails if any built HTML, SVG, or CSS contains league or team names in markup outside the About/Overview prose block, or references image files not generated by the build. The list of blocked terms lives in a config file.
- Footer disclaimer present on every page
- Every chart frame has "What this shows", "What it doesn't show", and a source line
- Every chart data file comes from `share_exec` or a whitelisted evaluation summary (existing check)
- No `font-family` outside the declared stacks
- HTML validation and broken-link check

---

## 10. Build order for Claude Code

1. Tokens, base layout, top bar, footer, synthetic notice, theme toggle. **Screenshot desktop + mobile, light + dark, and pause for Anna.**
2. KPI block, chart frame, data trust strip
3. **Drive chart** (static first, then the fan-status split, then the load animation). **Screenshot and pause for Anna.**
4. Acquisition page end to end
5. Matchup card, market quadrant
6. Value, Audience, Participation, Trust pages
7. Overview page
8. Mobile pass (vertical drive chart), accessibility pass, Lighthouse
9. Brand boundary check + CI wiring

After each step, take screenshots and review against this spec before continuing. Before finishing, remove one decorative element that doesn't carry information.
