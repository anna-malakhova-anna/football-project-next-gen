/* Theme toggle, synthetic-notice dismissal, mobile menu and chart embedding. Nothing here computes a number. */
(function () {
  var root = document.documentElement;
  function store(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* storage may be blocked */ } }
  function read(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }

  var notice = document.getElementById("notice");
  if (notice && read("cff-notice") === "dismissed") { notice.hidden = true; }
  var dismiss = document.getElementById("notice-dismiss");
  if (dismiss) { dismiss.addEventListener("click", function () { notice.hidden = true; store("cff-notice", "dismissed"); }); }

  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var current = root.dataset.theme;
      if (!current) { current = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }
      var next = current === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      store("cff-theme", next);
    });
  }

  var menu = document.getElementById("menu-btn");
  var bar = document.getElementById("topbar");
  if (menu && bar) {
    menu.addEventListener("click", function () {
      var open = bar.classList.toggle("open");
      menu.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Grouped navigation: a button opens its menu; a click elsewhere or Esc closes it. On a phone every link is shown, so the buttons do nothing.
  var groups = document.querySelectorAll(".nav-group");
  function closeGroups(except) { groups.forEach(function (g) { if (g !== except) { g.classList.remove("open"); g.querySelector(".nav-trigger").setAttribute("aria-expanded", "false"); } }); }
  groups.forEach(function (g) {
    if (!g.querySelector(".nav-menu")) { return; }
    var t = g.querySelector(".nav-trigger");
    t.addEventListener("click", function (ev) { ev.stopPropagation(); var open = !g.classList.contains("open"); closeGroups(g); g.classList.toggle("open", open); t.setAttribute("aria-expanded", open ? "true" : "false"); });
  });
  document.addEventListener("click", function () { closeGroups(null); });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") { closeGroups(null); } });

  // Lens toggle (Phase 5 pages): shows one of two precomputed annotations/panels. It only sets an attribute; nothing is filtered or computed.
  var scope = document.querySelector(".lens-scope");
  var lensButtons = document.querySelectorAll("[data-set-lens]");
  function setLens(name) {
    if (!scope) { return; }
    scope.setAttribute("data-lens-active", name);
    lensButtons.forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-set-lens") === name ? "true" : "false"); });
    store("cff-lens", name);
  }
  var savedLens = read("cff-lens");
  if (scope && (savedLens === "club" || savedLens === "privacy")) { setLens(savedLens); }
  lensButtons.forEach(function (b) { b.addEventListener("click", function () { setLens(b.getAttribute("data-set-lens")); }); });

  var specs = document.querySelectorAll('script[type="application/json"][data-chart]');
  function css(name, fallback) { var v = getComputedStyle(root).getPropertyValue(name).trim(); return v || fallback; }
  // Vega theme from the site tokens (series palette, text and grid colours follow the light/dark theme). Styling only.
  function vegaConfig() {
    var text = css("--text", "#1B2733"), muted = css("--text-muted", "#4A5866"), grid = css("--border", "#D5DBE1");
    var narrow = window.matchMedia && window.matchMedia("(max-width: 599px)").matches;
    return {
      background: null, font: css("--font-body", "sans-serif"),
      range: { category: [css("--series-turf", "#2F6B4F"), css("--series-sky", "#3D7CC9"), css("--series-pylon", "#D9622B"), css("--series-plum", "#7D4E8E"), css("--series-sand", "#B8A06A")] },
      axis: { labelColor: muted, titleColor: text, domainColor: grid, gridColor: grid, tickColor: grid },
      // on a phone a legend sits under the chart in one column, so a row of long labels never runs off the screen (layout only: nothing is computed)
      legend: narrow ? { labelColor: muted, titleColor: text, orient: "bottom", direction: "vertical", columns: 1, labelLimit: Math.max(160, window.innerWidth - 80) } : { labelColor: muted, titleColor: text }, view: { stroke: null }
    };
  }
  window.cffVegaConfig = vegaConfig;
  // On a phone, every legend in a spec stacks in one column under the chart with labels that fit the screen, and long category labels down the side
  // wrap onto taller rows (`compact`, a card thumbnail with a fixed height: they are shortened instead). This rewrites layout settings only:
  // no data, field or number is touched (ADR-037).
  function phoneSpec(spec, compact) {
    if (!(window.matchMedia && window.matchMedia("(max-width: 599px)").matches)) { return spec; }
    var copy = JSON.parse(JSON.stringify(spec)), w = window.innerWidth, axisLimit = Math.round(w * 0.45), chars = Math.floor(axisLimit / 7);
    // a chart with category labels down the side: cap them, and the legend (which starts where the plot starts) gets what is left
    var sideLabels = JSON.stringify(spec).search(/"y":\{[^{}]*"type":"(nominal|ordinal)"/) >= 0;
    var limit = sideLabels ? Math.max(120, w - axisLimit - 90) : Math.max(160, w - 80);
    (function walk(node, key) {
      if (Array.isArray(node)) { node.forEach(function (n) { walk(n); }); return; }
      if (!node || typeof node !== "object") { return; }
      if (key === "y" && (node.type === "nominal" || node.type === "ordinal") && node.axis !== null) {
        // wrap long category labels onto lines of about `chars` characters instead of cutting them off (text layout only)
        node.axis = Object.assign({}, node.axis || {});
        if (!compact && !node.axis.labelExpr) { node.axis.labelExpr = "slice(split(replace(datum.label, /(.{1," + chars + "})(\\s+|$)/g, '$1|'), '|'), 0, -1)"; }
        if (!compact) { node.axis.labelLimit = Math.min(node.axis.labelLimit || axisLimit, axisLimit); node.axis.labelLineHeight = 13; }     // a thumbnail keeps its labels whole
      }
      if (key === "x" && (node.type === "nominal" || node.type === "ordinal") && node.axis !== null) {
        // category labels along the bottom wrap onto short lines, so neighbours do not run into each other
        node.axis = Object.assign({}, node.axis || {});
        if (!node.axis.labelExpr && !node.axis.labelAngle) { node.axis.labelExpr = "slice(split(replace(datum.label, /(.{1,11})(\\s+|$)/g, '$1|'), '|'), 0, -1)"; node.axis.labelAngle = 0; node.axis.labelLineHeight = 13; }
      }
      Object.keys(node).forEach(function (k) {
        var v = node[k];
        if (k === "legend" && v && typeof v === "object" && compact && sideLabels) {
          node[k] = null;     // a phone thumbnail with long side labels has no room for a legend: Expand shows the chart with it
        } else if (k === "legend" && v && typeof v === "object") {
          if (["top", "bottom", "left", "right", undefined].indexOf(v.orient) >= 0) { v.orient = "bottom"; }
          v.direction = "vertical"; v.columns = 1; v.labelLimit = Math.min(v.labelLimit || limit, limit);
        } else { walk(v, k); }
      });
    })(copy);
    // wrapped labels need taller rows: three lines per category (a chart with side labels simply gets taller on a phone)
    if (sideLabels && !compact && !copy.facet && !copy.hconcat && !copy.vconcat && !copy.concat && !copy.repeat) { copy.height = { step: 42 }; }
    return copy;
  }
  window.cffPhoneSpec = phoneSpec;
  function embedAll() {
    specs.forEach(function (node) {
      var spec = JSON.parse(node.textContent);
      var target = document.getElementById(node.dataset.chart);
      if (window.vegaEmbed && target) { vegaEmbed(target, phoneSpec(spec), {actions: false, renderer: "svg", config: vegaConfig()}); }
    });
  }
  embedAll();
  if (toggle) { toggle.addEventListener("click", embedAll); }
})();
