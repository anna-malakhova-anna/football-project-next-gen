# ADR-032: A map of the program markets at the top of the Global outlook tab

- **Status:** Accepted, 2026-10-26, at Anna's request: a map at the top of the tab, with the countries where NFL clubs hold rights highlighted and named, in the site's colours, and a view per continent. **The card's copy (G0) is `status: draft` until Anna approves it.**
- **Synthetic data.** The statuses and grades on the map are the project's synthetic results; the country outlines are real public geography.

## Decisions
1. **Country outlines are vendored, not fetched at page load.** The file is `site_src/geo/countries-50m.json`: world-atlas 2.0.2, from Natural Earth's public-domain 1:50m data, downloaded once with Anna's approval. It is kept with its ISC licence (`site_src/geo/LICENSE-world-atlas.txt`). The build copies it to `geo/countries.json`, the one non-dataset file a chart may read. It holds shapes only, no figures and no marks, and the brand-boundary check still refuses any image.
2. **Each market's label point and continent come from the outlines, not typed.** `scripts/build_gmp_map_points.py` matches each market to its outline by name and takes the centroid of its largest polygon, so islands and overseas parts do not pull a label off the mainland. It writes the seed `gmp_map_points`; `tests/test_gmp_map.py` keeps the seed equal to what the outlines give.
3. **The colours follow the tiles of card G1:**
   - markets with data carry their counting grade (A blue to D red);
   - markets where clubs report activity are grey-blue;
   - markets where nothing arrives are white with a dashed edge;
   - other countries are pale.

   Labels get a thin white halo, so they read on dark and pale fills alike. A few names are shortened on the map (UK, UAE, S. Korea), and Korea's label sits left of its point, so it stays clear of Japan's.
4. **One card, G0, spans the full width above the others.** Its thumbnail is the world. Its slides are four continent views: Europe, the Americas, Asia-Pacific, the Middle East and Africa. Each view fits a longitude and latitude box to the card, so it works at any width. The box must be wound clockwise: on the sphere, an anticlockwise ring means "everything but the box".
5. **The map computes nothing.** It joins each outline to its market by the outline's id (a lookup, not a calculation), and every status, grade and label comes from the `gmp_map` dataset, which reads DP6's regime market ports. The headline numbers (22 markets, 4 continents) come from the insight export.

## Consequences
- The page check (`site_check`) covers the card at three widths, and the copy review lists G0.
- Natural Earth draws borders as they stand in its data. The card's caution says the borders say nothing about who holds which rights.
