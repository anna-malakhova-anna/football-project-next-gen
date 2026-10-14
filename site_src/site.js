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

  // Lens toggle (Phase 5 pages): shows one of two precomputed annotations/panels. It only sets an attribute; nothing is filtered or computed.
  var scope = document.querySelector(".lens-scope");
  var lensButtons = document.querySelectorAll("[data-set-lens]");
  function setLens(name) {
    if (!scope) { return; }
    scope.setAttribute("data-lens-active", name);
    lensButtons.forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-set-lens") === name ? "true" : "false"); });
    store("cff-lens", name);
  }
  lensButtons.forEach(function (b) { b.addEventListener("click", function () { setLens(b.getAttribute("data-set-lens")); }); });

  var specs = document.querySelectorAll('script[type="application/json"][data-chart]');
  function css(name, fallback) { var v = getComputedStyle(root).getPropertyValue(name).trim(); return v || fallback; }
  // Vega theme from the site tokens (series palette, text and grid colours follow the light/dark theme). Styling only.
  function vegaConfig() {
    var text = css("--text", "#1B2733"), muted = css("--text-muted", "#4A5866"), grid = css("--border", "#D5DBE1");
    return {
      background: null, font: css("--font-body", "sans-serif"),
      range: { category: [css("--series-turf", "#2F6B4F"), css("--series-sky", "#3D7CC9"), css("--series-pylon", "#D9622B"), css("--series-plum", "#7D4E8E"), css("--series-sand", "#B8A06A")] },
      axis: { labelColor: muted, titleColor: text, domainColor: grid, gridColor: grid, tickColor: grid },
      legend: { labelColor: muted, titleColor: text }, view: { stroke: null }
    };
  }
  function embedAll() {
    specs.forEach(function (node) {
      var spec = JSON.parse(node.textContent);
      var target = document.getElementById(node.dataset.chart);
      if (window.vegaEmbed && target) { vegaEmbed(target, spec, {actions: false, renderer: "svg", config: vegaConfig()}); }
    });
  }
  embedAll();
  if (toggle) { toggle.addEventListener("click", embedAll); }
})();
