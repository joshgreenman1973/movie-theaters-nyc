(function () {
  "use strict";

  var MIN_YEAR = 1900, MAX_YEAR = 2026;
  var metric = "seats";
  var year = MIN_YEAR;
  var playing = false;
  var timer = null;
  var TT = [];           // theaters on the timeline (have an opening year)
  var pts = [];          // drawn screen positions for hit-testing
  var map, glow, ctx, canvas, dpr = 1;

  var el = function (id) { return document.getElementById(id); };
  var fmt = function (n) { return (n || 0).toLocaleString("en-US"); };

  fetch("data/theaters.json").then(function (r) { return r.json(); }).then(init);

  function init(payload) {
    var theaters = payload.theaters || [];
    TT = theaters.filter(function (t) { return t.timeline; });

    var minOpen = TT.reduce(function (m, t) { return Math.min(m, t.opened); }, 9999);
    MIN_YEAR = Math.min(1900, Math.floor(minOpen / 10) * 10);
    year = MIN_YEAR;
    var scrub = el("scrub");
    scrub.min = MIN_YEAR; scrub.max = MAX_YEAR; scrub.value = MIN_YEAR;

    setupMap();
    buildRails();
    wireControls(payload);
    render(MIN_YEAR);
  }

  function setupMap() {
    map = L.map("map", {
      zoomControl: false, minZoom: 10, maxZoom: 17, zoomSnap: 0.25,
      attributionControl: false
    }).setView([40.715, -73.94], 11);
    L.control.zoom({ position: "bottomright" }).addTo(map);

    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png", {
      subdomains: "abcd", maxZoom: 19
    }).addTo(map);

    var box = document.querySelector(".mapbox");
    canvas = document.createElement("canvas");
    canvas.className = "glow-canvas";
    box.appendChild(canvas);
    ctx = canvas.getContext("2d");
    sizeCanvas();

    map.on("move zoom moveend zoomend resize viewreset zoomanim", function () { redraw(); });
    map.on("mousemove", onHover);
    map.on("click", onClick);
    window.addEventListener("resize", function () { sizeCanvas(); redraw(); });
  }

  function sizeCanvas() {
    var box = document.querySelector(".mapbox");
    dpr = window.devicePixelRatio || 1;
    canvas.width = box.clientWidth * dpr;
    canvas.height = box.clientHeight * dpr;
    canvas.style.width = box.clientWidth + "px";
    canvas.style.height = box.clientHeight + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function radiusFor(t, zoom) {
    var norm, val;
    if (metric === "count") { norm = 0.5; }
    else if (metric === "screens") { val = t.screens || 1; norm = Math.sqrt(val / 20); }
    else { val = t.seats || 300; norm = Math.sqrt(val / 6000); }
    if (norm > 1.25) norm = 1.25;
    var base = 3 + norm * 15;
    var zs = 1 + (zoom - 11) * 0.42;
    zs = Math.max(0.55, Math.min(3.2, zs));
    return base * zs;
  }

  function redraw() {
    if (!ctx) return;
    var w = canvas.width / dpr, h = canvas.height / dpr;
    ctx.clearRect(0, 0, w, h);
    var zoom = map.getZoom();
    pts = [];
    var embers = [], lights = [];
    for (var i = 0; i < TT.length; i++) {
      var t = TT[i];
      if (t.opened > year) continue;
      var dead = t.gone != null && t.gone <= year;
      var p = map.latLngToContainerPoint([t.lat, t.lng]);
      if (p.x < -40 || p.y < -40 || p.x > w + 40 || p.y > h + 40) continue;
      var r = radiusFor(t, zoom);
      pts.push({ t: t, x: p.x, y: p.y, r: Math.max(r, 6), dead: dead });
      if (dead) embers.push({ x: p.x, y: p.y, r: r }); else lights.push({ x: p.x, y: p.y, r: r });
    }
    // embers first (faint cold marks where a theater stood)
    ctx.globalCompositeOperation = "source-over";
    for (var e = 0; e < embers.length; e++) {
      var em = embers[e], er = Math.max(2.4, em.r * 0.44);
      var eg = ctx.createRadialGradient(em.x, em.y, 0, em.x, em.y, er * 2.6);
      eg.addColorStop(0, "rgba(196,132,78,0.62)");
      eg.addColorStop(0.5, "rgba(150,100,60,0.26)");
      eg.addColorStop(1, "rgba(120,80,45,0)");
      ctx.fillStyle = eg; ctx.beginPath(); ctx.arc(em.x, em.y, er * 2.6, 0, 6.2832); ctx.fill();
    }
    // living lights bloom additively
    ctx.globalCompositeOperation = "lighter";
    for (var l = 0; l < lights.length; l++) {
      var li = lights[l];
      var g = ctx.createRadialGradient(li.x, li.y, 0, li.x, li.y, li.r);
      g.addColorStop(0, "rgba(255,245,222,0.95)");
      g.addColorStop(0.42, "rgba(255,181,90,0.55)");
      g.addColorStop(1, "rgba(224,127,31,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(li.x, li.y, li.r, 0, 6.2832); ctx.fill();
    }
    ctx.globalCompositeOperation = "source-over";
  }

  function buildRails() {
    var live = TT.slice().sort(function (a, b) { return a.opened - b.opened || a.name.localeCompare(b.name); });
    var dead = TT.filter(function (t) { return t.gone != null; })
      .sort(function (a, b) { return a.gone - b.gone || a.name.localeCompare(b.name); });

    var lr = el("liveRail"), dr = el("deadRail");
    var lf = document.createDocumentFragment(), df = document.createDocumentFragment();
    live.forEach(function (t) {
      var d = railItem(t, t.opened);
      t._liveNode = d; d.style.display = "none"; lf.appendChild(d);
    });
    dead.forEach(function (t) {
      var d = railItem(t, t.gone);
      t._deadNode = d; d.style.display = "none"; df.appendChild(d);
    });
    lr.appendChild(lf); dr.appendChild(df);
  }

  function railItem(t, yr) {
    var d = document.createElement("div");
    d.className = "ritem";
    d.innerHTML = '<span class="ry">' + yr + "</span>" + escapeHtml(t.name);
    d.title = t.name + (t.seats ? " · " + fmt(t.seats) + " seats" : "");
    d.addEventListener("click", function () { flyTo(t); });
    return d;
  }

  function render(y) {
    year = y;
    el("yrOut").textContent = y;
    el("scrub").value = y;

    var liveCount = 0, deadCount = 0, sum = 0;
    for (var i = 0; i < TT.length; i++) {
      var t = TT[i];
      var appeared = t.opened <= y;
      var dead = t.gone != null && t.gone <= y;
      var alive = appeared && !dead;
      if (alive) { liveCount++; sum += metricVal(t); }
      if (dead) deadCount++;

      var liveShow = alive;
      if (t._liveNode && t._liveShown !== liveShow) {
        t._liveNode.style.display = liveShow ? "" : "none"; t._liveShown = liveShow;
      }
      if (t._deadNode && t._deadShown !== dead) {
        t._deadNode.style.display = dead ? "" : "none"; t._deadShown = dead;
      }
    }
    el("liveCount").textContent = fmt(liveCount);
    el("deadCount").textContent = fmt(deadCount);
    el("metricOut").textContent = fmt(sum);
    redraw();
    if (playing) {
      var ds = el("deadRail"); ds.scrollTop = ds.scrollHeight;
    }
  }

  function metricVal(t) {
    if (metric === "count") return 1;
    if (metric === "screens") return t.screens || 0;
    return t.seats || 0;
  }

  function wireControls(payload) {
    el("play").addEventListener("click", togglePlay);
    el("scrub").addEventListener("input", function () {
      stop(); render(parseInt(this.value, 10));
    });
    el("metricSeg").addEventListener("click", function (ev) {
      var b = ev.target.closest("button"); if (!b) return;
      metric = b.getAttribute("data-m");
      Array.prototype.forEach.call(this.querySelectorAll("button"), function (x) { x.classList.remove("on"); });
      b.classList.add("on");
      el("metricLbl").textContent = metric === "count" ? "theaters lit" : metric === "screens" ? "screens lit" : "seats lit";
      render(year);
    });
    el("aiBtn").addEventListener("click", function () { el("aiPop").classList.toggle("open"); });
    el("detailX").addEventListener("click", function () { el("detail").classList.remove("open"); });

    var st = payload.stats || {};
    if (st.undated) {
      el("footnote").innerHTML += " &middot; " + fmt(st.undated) +
        " theaters have no reliable opening year and are omitted from the animation.";
    }
    if (payload.generated_provisional) {
      el("footnote").innerHTML = "<b style='color:#d98a4e'>Provisional preview</b> &mdash; years not yet enriched. " + el("footnote").innerHTML;
    }
  }

  function filmBurst(ms) {
    var f = el("filmfx"); if (!f) return;
    f.classList.remove("on"); void f.offsetWidth; f.classList.add("on");
    if (f._t) clearTimeout(f._t);
    f._t = setTimeout(function () { f.classList.remove("on"); }, ms);
  }

  function togglePlay() {
    if (playing) { stop(); return; }
    if (year >= MAX_YEAR) { year = MIN_YEAR; render(MIN_YEAR); }
    playing = true; el("play").innerHTML = "&#10073;&#10073;";
    filmBurst(1100);
    step();
  }
  function stop() {
    playing = false; el("play").innerHTML = "&#9654;";
    if (timer) { clearTimeout(timer); timer = null; }
  }
  function step() {
    if (!playing) return;
    render(year + 1);
    if (year >= MAX_YEAR) { stop(); filmBurst(1400); return; }
    var sp = parseInt(el("speed").value, 10);
    var ms = 280 - sp * 24;
    timer = setTimeout(step, ms);
  }

  function nearest(cp) {
    var best = null, bd = 16 * 16;
    for (var i = 0; i < pts.length; i++) {
      var d = (pts[i].x - cp.x) * (pts[i].x - cp.x) + (pts[i].y - cp.y) * (pts[i].y - cp.y);
      var rr = Math.max(14, pts[i].r); rr = rr * rr;
      if (d < rr && d < bd) { bd = d; best = pts[i]; }
    }
    return best;
  }

  function onHover(e) {
    var hit = nearest(e.containerPoint);
    var tip = el("tip");
    if (!hit) { tip.style.display = "none"; canvas.style.cursor = ""; return; }
    var t = hit.t;
    var span = t.opened + (t.gone ? "&ndash;" + t.gone : t.open_now ? "&ndash;now" : "");
    tip.innerHTML = "<b>" + escapeHtml(t.name) + "</b> &middot; " + span +
      (t.seats ? " &middot; " + fmt(t.seats) + " seats" : "");
    tip.style.left = hit.x + "px"; tip.style.top = hit.y + "px"; tip.style.display = "block";
  }

  function onClick(e) {
    var hit = nearest(e.containerPoint);
    if (!hit) { el("detail").classList.remove("open"); return; }
    showDetail(hit.t);
  }

  function showDetail(t) {
    el("detailName").textContent = t.name;
    var life = t.opened + (t.gone ? " &ndash; " + t.gone : t.open_now ? " &ndash; still open" : " &ndash; ?");
    var bits = [];
    bits.push(boroughName(t.borough) + " &middot; " + life);
    var sc = [];
    if (t.seats) sc.push(fmt(t.seats) + " seats");
    if (t.screens) sc.push(t.screens + (t.screens === 1 ? " screen" : " screens"));
    if (sc.length) bits.push(sc.join(" &middot; "));
    bits.push("Status: " + t.status + (t.confidence ? " &middot; year confidence: " + t.confidence : ""));
    if (t.address) bits.push(escapeHtml(t.address));
    bits.push('<a href="' + t.url + '" target="_blank" rel="noopener">Cinema Treasures &nearr;</a>');
    el("detailMeta").innerHTML = bits.join("<br>");
    el("detail").classList.add("open");
  }

  function flyTo(t) {
    map.flyTo([t.lat, t.lng], Math.max(map.getZoom(), 15), { duration: 0.7 });
    if (t.opened > year || (t.gone && t.gone < year)) { /* keep year as-is */ }
    showDetail(t);
  }

  function boroughName(b) {
    var m = { M: "Manhattan", B: "Brooklyn", X: "Bronx", Q: "Queens", S: "Staten Island" };
    return m[b] || b || "New York City";
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
})();
