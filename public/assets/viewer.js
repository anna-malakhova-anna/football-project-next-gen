/* Chart cards and the full-screen viewer (Phase 5.1). It shows, hides, scrolls and renders the specs it is handed; it computes nothing. */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* blocked */ } }
  function read(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function config() { return window.cffVegaConfig ? window.cffVegaConfig() : {}; }
  function phone(spec, compact) { return window.cffPhoneSpec ? window.cffPhoneSpec(spec, compact) : spec; }
  function embed(box, spec, compact) { if (window.vegaEmbed && box) { window.vegaEmbed(box, phone(spec, compact), { actions: false, renderer: "svg", config: config() }); } }

  // a grid of small charts (one Vega chart per cell, so the grid can wrap: 3 columns wide, 1 on a phone)
  function renderMulti(box, items, small) {
    box.classList.add("vmulti"); if (small) { box.classList.add("vmulti-small"); }
    items.forEach(function (it) {
      var cell = document.createElement("div"); cell.className = "vmulti-cell";
      var t = document.createElement("div"); t.className = "vmulti-title"; t.textContent = it.title;
      var c = document.createElement("div"); c.className = "vmulti-chart";
      cell.appendChild(t); cell.appendChild(c); box.appendChild(cell); embed(c, it.spec);
    });
  }

  // ---- collect slides, in page order
  var slides = Array.prototype.map.call(document.querySelectorAll("script.vspec"), function (n) {
    var card = document.getElementById("card-" + n.dataset.card);
    return { kind: n.dataset.kind, id: n.dataset.id, cardId: n.dataset.card, title: n.dataset.title, headline: n.dataset.headline, spec: JSON.parse(n.textContent), card: card };
  });
  if (!slides.length) { return; }

  // ---- thumbnails (rendered once visible)
  var thumbs = document.querySelectorAll(".vcard");
  function renderThumb(card) {
    var spec = document.getElementById("thumb-" + card.dataset.card + "-spec");
    var box = document.getElementById("thumb-" + card.dataset.card);
    if (spec && box && !box.dataset.done) {
      box.dataset.done = "1";
      var obj = JSON.parse(spec.textContent);
      if (obj.multi) { renderMulti(box, obj.multi, true); } else { embed(box, obj, true); }     // a thumbnail keeps its fixed height: labels are shortened, not wrapped
    }
  }
  if ("IntersectionObserver" in window) {
    var thumbObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { renderThumb(en.target); thumbObs.unobserve(en.target); } });
    }, { rootMargin: "300px" });
    thumbs.forEach(function (c) { thumbObs.observe(c); });
  } else { thumbs.forEach(renderThumb); }
  // the rest render once the page is idle, and all of them before printing, so a printout or a PDF never has an empty chart (ADR-039)
  function renderAll() { thumbs.forEach(renderThumb); }
  window.addEventListener("load", function () { (window.requestIdleCallback || function (f) { return setTimeout(f, 800); })(renderAll); });
  window.addEventListener("beforeprint", renderAll);

  // segmented control (tile map): shows one of the precomputed panels
  document.querySelectorAll(".vseg").forEach(function (seg) {
    var card = seg.closest(".vcard"); var host = card && card.querySelector(".vtiles-host");
    seg.querySelectorAll("button").forEach(function (b) {
      b.addEventListener("click", function () {
        if (host) { host.setAttribute("data-active", b.dataset.seg); }
        seg.querySelectorAll("button").forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
      });
    });
  });

  // ---- the dialog
  var dlg = document.createElement("dialog");
  dlg.className = "viewer";
  dlg.setAttribute("aria-label", "Full-screen chart viewer");
  dlg.innerHTML =
    '<div class="vbar"><span class="vcount" aria-live="polite"></span>' +
    '<span role="group" aria-label="Choose a lens"><button type="button" data-v-lens="club" aria-label="Club lens">Club lens</button> <button type="button" data-v-lens="privacy" aria-label="Privacy lens">Privacy lens</button></span>' +
    '<button type="button" data-v="prev" aria-label="Previous slide">↑ Prev</button><button type="button" data-v="next" aria-label="Next slide">Next ↓</button>' +
    '<button type="button" data-v="full" aria-label="Full screen">Full screen</button><button type="button" data-v="close" aria-label="Close the viewer">Close ✕</button></div>' +
    '<nav class="vrail" aria-label="Slides"></nav><div class="vscroll" tabindex="-1"></div>';
  document.body.appendChild(dlg);
  var scroller = dlg.querySelector(".vscroll"), rail = dlg.querySelector(".vrail"), counter = dlg.querySelector(".vcount");
  var secs = [], railBtns = [], current = 0, opener = null, savedY = 0, built = false;

  function build() {
    if (built) { return; }
    built = true;
    var lastCard = null;
    slides.forEach(function (s, i) {
      var sec = document.createElement("section");
      sec.className = "vslide"; sec.dataset.index = i; sec.id = "slide-" + s.id;
      sec.setAttribute("aria-label", s.title);
      var h2 = document.createElement("h2"); h2.textContent = s.headline || s.card.querySelector(".vcard-headline").textContent;
      var sub = document.createElement("p"); sub.className = "vslide-sub";
      sub.textContent = s.card.querySelector(".vcard-question").textContent + " · " + s.title;
      var top = document.createElement("div"); top.appendChild(h2); top.appendChild(sub);
      var chart = document.createElement("div"); chart.className = "vslide-chart"; chart.setAttribute("role", "img"); chart.setAttribute("aria-label", h2.textContent + " " + s.title);
      var text = document.createElement("div"); text.className = "vslide-text";
      text.innerHTML = s.card.querySelector(".vcard-notes").innerHTML;
      sec.appendChild(top); sec.appendChild(chart); sec.appendChild(text);
      scroller.appendChild(sec); secs.push({ el: sec, chart: chart, done: false });
      if (s.cardId !== lastCard) {
        var g = document.createElement("div"); g.className = "vrail-group"; g.textContent = s.card.querySelector(".vcard-question").textContent; rail.appendChild(g); lastCard = s.cardId;
      }
      var b = document.createElement("button"); b.type = "button"; b.textContent = s.title; b.setAttribute("aria-label", "Go to slide: " + s.title);
      b.addEventListener("click", function () { go(i); }); rail.appendChild(b); railBtns.push(b);
    });
    var lazy = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) { return; }
        var rec = secs[+en.target.dataset.index];
        if (!rec.done) {
          rec.done = true;
          var sl = slides[+en.target.dataset.index];
          if (sl.kind === "html") { rec.chart.classList.add("vslide-html"); rec.chart.removeAttribute("role"); rec.chart.innerHTML = sl.spec.html; } else if (sl.kind === "multi") { rec.chart.classList.add("vslide-html"); renderMulti(rec.chart, sl.spec.multi, false); } else { embed(rec.chart, sl.spec); }
        }
      });
    }, { root: scroller, rootMargin: "100% 0px 100% 0px" });
    secs.forEach(function (r) { lazy.observe(r.el); });
  }

  function setCurrent(i) {
    current = Math.max(0, Math.min(slides.length - 1, i));
    counter.textContent = "Slide " + (current + 1) + " of " + slides.length + " · " + slides[current].card.querySelector(".vcard-question").textContent + " · " + slides[current].title;
    railBtns.forEach(function (b, k) { if (k === current) { b.setAttribute("aria-current", "true"); } else { b.removeAttribute("aria-current"); } });
    if (dlg.open) { history.replaceState(null, "", "#view=" + slides[current].id); }
  }
  function go(i) {
    i = Math.max(0, Math.min(slides.length - 1, i));
    secs[i].el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    setCurrent(i);
  }
  scroller.addEventListener("scroll", function () {
    var h = scroller.clientHeight; if (!h) { return; }
    var i = Math.round(scroller.scrollTop / h); if (i !== current) { setCurrent(i); }
  });

  function syncLens() {
    var scope = document.querySelector(".lens-scope");
    var lens = (scope && scope.getAttribute("data-lens-active")) || "club";
    dlg.setAttribute("data-lens-active", lens);
    dlg.querySelectorAll("[data-v-lens]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-v-lens") === lens ? "true" : "false"); });
  }
  dlg.querySelectorAll("[data-v-lens]").forEach(function (b) {
    b.addEventListener("click", function () {
      var page = document.querySelector('[data-set-lens="' + b.getAttribute("data-v-lens") + '"]');
      if (page) { page.click(); }
      syncLens();
    });
  });

  function indexOf(id) { for (var i = 0; i < slides.length; i++) { if (slides[i].id === id) { return i; } } return -1; }
  function open(id, from) {
    var i = indexOf(id); if (i < 0) { return; }
    build(); syncLens();
    if (!dlg.open) { savedY = window.scrollY; opener = from || document.querySelector('.vexpand[data-open="' + id + '"]'); dlg.showModal(); }
    secs[i].el.scrollIntoView({ behavior: "auto", block: "start" });
    setCurrent(i);
    scroller.focus({ preventScroll: true });
    requestAnimationFrame(function () { scroller.style.scrollBehavior = "auto"; secs[i].el.scrollIntoView({ behavior: "auto", block: "start" }); scroller.style.scrollBehavior = ""; });
  }
  function close() { if (dlg.open) { dlg.close(); } }
  dlg.addEventListener("close", function () {
    history.replaceState(null, "", location.pathname + location.search);
    window.scrollTo(0, savedY);
    if (opener) { opener.focus({ preventScroll: true }); }
    if (document.fullscreenElement) { document.exitFullscreen(); }
  });
  dlg.addEventListener("keydown", function (ev) {
    var k = ev.key;
    if (k === "ArrowDown" || k === "ArrowRight" || k === "PageDown") { ev.preventDefault(); go(current + 1); }
    else if (k === "ArrowUp" || k === "ArrowLeft" || k === "PageUp") { ev.preventDefault(); go(current - 1); }
    else if (k === "Home") { ev.preventDefault(); go(0); }
    else if (k === "End") { ev.preventDefault(); go(slides.length - 1); }
  });
  dlg.querySelector('[data-v="prev"]').addEventListener("click", function () { go(current - 1); });
  dlg.querySelector('[data-v="next"]').addEventListener("click", function () { go(current + 1); });
  dlg.querySelector('[data-v="close"]').addEventListener("click", close);
  dlg.querySelector('[data-v="full"]').addEventListener("click", function () { if (dlg.requestFullscreen) { dlg.requestFullscreen().catch(function () { /* optional */ }); } });

  document.querySelectorAll("[data-open]").forEach(function (b) {
    b.addEventListener("click", function () { open(b.dataset.open, b); });
    if (b.getAttribute("role") === "button") {
      b.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); open(b.dataset.open, b); } });
    }
  });

  function fromHash() {
    var m = /^#view=([A-Za-z0-9_-]+)$/.exec(location.hash);
    if (m) { open(m[1]); } else if (dlg.open) { close(); }
  }
  window.addEventListener("hashchange", fromHash);
  fromHash();
})();
