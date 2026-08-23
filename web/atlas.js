// Atlas: boundary-only drill-down map. Türkiye → il → ilçe → mahalle, drawn as SVG
// paths in an equirectangular projection fitted to the current place. No indicator data
// is read here; this page is the canvas the indicators will later be painted on (K28).
//
// Two ideas shape the code:
//   - a *place* (where you are: Türkiye, Bursa, İznik) and a *layer* (what is drawn in
//     it: its children, or its grandchildren when the reader asks for the finer one).
//   - look settings live in localStorage under one key and are applied as CSS custom
//     properties / data attributes, so the stylesheet does the styling.
"use strict";

const GEO = {
    country: () => "../public/areas.geojson",
    province: (id) => `../public/geo/districts/${id}.geojson`,
    district: (id) => `../public/geo/neighbourhoods/${id}.geojson`,
};
const LEVEL_TR = { country: "Türkiye", province: "İl", district: "İlçe", neighbourhood: "Mahalle" };
const CHILD = { country: "province", province: "district", district: "neighbourhood", neighbourhood: null };

// The explorer's accent hues (K5); fills are built from the hue as an HSL ramp, exactly
// as explorer.js rampColours() does, so the two pages look like one thing.
const HUES = [
    { id: "mavi", dark: "#7fa8d8", light: "#286bbb" },
    { id: "yesil", dark: "#6fbfae", light: "#00847e" },
    { id: "turuncu", dark: "#e8735c", light: "#e56e5a" },
    { id: "mor", dark: "#b98ad6", light: "#6d3e91" },
    { id: "gri", dark: "#a0a0a0", light: "#555555" },
];
function hexToHsl(hex) {
    const n = parseInt(hex.slice(1), 16), r = (n >> 16) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2; let h = 0, s = 0;
    if (max !== min) {
        const d = max - min; s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    }
    return { h: h * 60, s: s * 100, l: l * 100 };
}
function rampColours(count) {
    const hue = HUES.find((x) => x.id === look.hue) || HUES[0];
    const light = look.theme === "light";
    const { h, s } = hexToHsl(light ? hue.light : hue.dark);
    const [l0, l1] = light ? [93, 28] : [24, 76];
    const [s0, s1] = light ? [Math.min(s, 35), s] : [Math.min(s, 40), Math.min(95, s + 12)];
    return Array.from({ length: count }, (_, i) => {
        const t = count < 2 ? 1 : i / (count - 1);
        return `hsl(${h.toFixed(0)} ${(s0 + (s1 - s0) * t).toFixed(0)}% ${(l0 + (l1 - l0) * t).toFixed(0)}%)`;
    });
}

const DEFAULT_LOOK = {
    theme: "dark", fill: "shade", hue: "mavi", stroke: 6, strokeColor: "dark",
    labels: "off", font: 11, hover: "on", context: "on", inset: "on",
};
const LOOK_KEY = "veriatlas.atlas.look.v3"; // bumped when defaults change, so a saved look does not hide them
let look = loadLook();

function loadLook() {
    try { return { ...DEFAULT_LOOK, ...JSON.parse(localStorage.getItem(LOOK_KEY) || "{}") }; }
    catch { return { ...DEFAULT_LOOK }; }
}

const $ = (s) => document.querySelector(s);
const SVG_NS = "http://www.w3.org/2000/svg";

const state = {
    path: [{ level: "country", id: "TR", name: "Türkiye" }],
    depth: 1,          // 1 = children of the place, 2 = grandchildren
    features: [],      // what is drawn
    context: [],       // siblings of the place, drawn as silhouettes
    missing: 0,        // at depth 2: children without a boundary file
    view: null,        // viewBox {x,y,w,h}
    busy: false,
};
const cache = new Map();

// ---------- look ----------
const LOOK_CHOICES = [["set-theme", "theme"], ["set-fill", "fill"], ["set-hue", "hue"], ["set-stroke-color", "strokeColor"],
    ["set-labels", "labels"], ["set-hover", "hover"], ["set-context", "context"], ["set-inset", "inset"]];

function applyLook() {
    const root = document.documentElement;
    const light = look.theme === "light";
    root.dataset.theme = look.theme;
    for (const k of ["fill", "labels", "hover", "context", "inset"]) root.dataset[k] = look[k];

    const hue = HUES.find((h) => h.id === look.hue) || HUES[0];
    root.style.setProperty("--accent", light ? hue.light : hue.dark);
    root.style.setProperty("--map-fill", rampColours(6)[2]);
    root.style.setProperty("--map-stroke-width", (look.stroke / 10) + "px");
    // Explorer draws borders in the card colour: a gap between areas, not a line on them.
    const strokeColors = {
        dark: light ? "#ffffff" : "#1a1a1a",
        light: light ? "#9aa7b8" : "#cfcfcf",
        accent: light ? hue.light : hue.dark,
    };
    root.style.setProperty("--map-stroke", strokeColors[look.strokeColor]);

    localStorage.setItem(LOOK_KEY, JSON.stringify(look));
    syncPanel();
    if (state.view) { drawAreas(); scaleLabels(); drawInset(); }
}

function syncPanel() {
    for (const [id, key] of LOOK_CHOICES) {
        for (const b of document.getElementById(id).children) b.classList.toggle("on", b.dataset.value === look[key]);
    }
    $("#set-stroke").value = look.stroke; $("#set-stroke-value").textContent = (look.stroke / 10).toFixed(1) + " px";
    $("#set-font").value = look.font; $("#set-font-value").textContent = look.font + " px";
}

function buildPanel() {
    $("#set-hue").innerHTML = HUES.map((h) => `<button data-value="${h.id}" title="${h.id}" style="background:${h.dark}"></button>`).join("");
    for (const [id, key] of LOOK_CHOICES) {
        document.getElementById(id).onclick = (ev) => {
            const b = ev.target.closest("button"); if (!b) return;
            look[key] = b.dataset.value; applyLook();
        };
    }
    $("#set-stroke").oninput = (e) => { look.stroke = +e.target.value; applyLook(); };
    $("#set-font").oninput = (e) => { look.font = +e.target.value; applyLook(); };
    $("#set-reset").onclick = () => { look = { ...DEFAULT_LOOK }; applyLook(); };
    $("#look-toggle").onclick = () => {
        const p = $("#look"); p.hidden = !p.hidden;
        $("#look-toggle").setAttribute("aria-expanded", String(!p.hidden));
        fit();
    };
    $("#layer").onclick = (ev) => {
        const b = ev.target.closest("button"); if (!b || state.busy) return;
        state.depth = +b.dataset.depth; loadPlace();
    };
}

// ---------- geometry ----------
let proj = null;
function bounds(features) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const walk = (c) => {
        if (typeof c[0] === "number") { minX = Math.min(minX, c[0]); maxX = Math.max(maxX, c[0]); minY = Math.min(minY, c[1]); maxY = Math.max(maxY, c[1]); }
        else c.forEach(walk);
    };
    features.forEach((f) => walk(f.geometry.coordinates));
    return { minX, minY, maxX, maxY };
}
function projectionFor(features, W) {
    const { minX, minY, maxX, maxY } = bounds(features);
    const k = Math.cos(((minY + maxY) / 2) * Math.PI / 180);
    const H = W * ((maxY - minY) / ((maxX - minX) * k));
    const sx = W / ((maxX - minX) * k), sy = H / (maxY - minY);
    return { W, H, to: ([x, y]) => [(x - minX) * k * sx, (maxY - y) * sy] };
}
function pathWith(p, g) {
    const ring = (r) => r.map((c, i) => (i ? "L" : "M") + p.to(c).map((v) => v.toFixed(1)).join(" ")).join("") + "Z";
    if (g.type === "Polygon") return g.coordinates.map(ring).join("");
    return g.coordinates.map((poly) => poly.map(ring).join("")).join("");
}
const geoPath = (g) => pathWith(proj, g);
function projBounds(g) { // bbox in projected units
    const b = bounds([{ geometry: g }]);
    const [x0, y0] = proj.to([b.minX, b.maxY]), [x1, y1] = proj.to([b.maxX, b.minY]);
    return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}
function centroid(g) { // area-weighted centroid of the largest ring
    const rings = g.type === "Polygon" ? [g.coordinates[0]] : g.coordinates.map((p) => p[0]);
    let best = null, bestA = 0;
    for (const ring of rings) {
        let a = 0, cx = 0, cy = 0;
        for (let i = 0; i < ring.length - 1; i++) {
            const [x0, y0] = proj.to(ring[i]), [x1, y1] = proj.to(ring[i + 1]);
            const f = x0 * y1 - x1 * y0; a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f;
        }
        a /= 2; if (Math.abs(a) > bestA) { bestA = Math.abs(a); best = [cx / (6 * a), cy / (6 * a)]; }
    }
    return best;
}

// ---------- loading ----------
async function fetchFeatures(level, id) {
    const url = GEO[level](id);
    if (!cache.has(url)) {
        const r = await fetch(url);
        if (!r.ok) { cache.set(url, null); return null; }
        const g = await r.json();
        g.features.sort((a, b) => a.properties.name_tr.localeCompare(b.properties.name_tr, "tr"));
        cache.set(url, g.features);
    }
    return cache.get(url);
}
const here = () => state.path[state.path.length - 1];
const findFeature = (id) => state.features.find((f) => f.properties.area_id === id);

/** Features for a place at a depth: its children, or all its grandchildren stitched
 *  from the per-child files (missing ones — no neighbourhood file yet — are skipped). */
async function featuresFor(place, depth) {
    const kids = await fetchFeatures(place.level, place.id);
    if (!kids) return null;
    state.missing = 0;
    if (depth === 1) return kids;
    const parts = await Promise.all(kids.map((k) => fetchFeatures(CHILD[place.level], k.properties.area_id)));
    state.missing = parts.filter((p) => !p).length;
    const out = parts.filter(Boolean).flat();
    return out.length ? out : null;
}

async function loadPlace() {
    const place = here();
    $("#count").textContent = "yükleniyor…";
    let features = await featuresFor(place, state.depth);
    if (!features) { state.depth = 1; features = await featuresFor(place, 1); }
    state.features = features;
    // Siblings of the place (its parent's children), for the silhouette around it.
    const parent = state.path[state.path.length - 2];
    state.context = parent ? (await fetchFeatures(parent.level, parent.id) || []).filter((f) => f.properties.area_id !== place.id) : [];

    proj = projectionFor(features, 1000);
    setView(fitView());
    drawAreas(); drawContext(); drawOutline(); drawCrumbs(); drawLayer(); drawInset();
    const count = `${LEVEL_TR[layerLevel()]} düzeyi · ${features.length} alan`;
    $("#count").textContent = state.missing ? `${count} · ${state.missing} birimde alt sınır yok` : count;
    document.title = `VeriAtlas — ${place.name}`;
}
function layerLevel() { let l = here().level; for (let i = 0; i < state.depth; i++) l = CHILD[l]; return l; }

// ---------- drawing ----------
function hashShade(id, ramp) { // deterministic per area id, so a shade never jumps on redraw
    let h = 0; for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    return ramp[h % ramp.length];
}

function drawAreas() {
    const areas = $("#areas"), labels = $("#labels");
    areas.innerHTML = ""; labels.innerHTML = "";
    const ramp = rampColours(6);
    const enterable = CHILD[layerLevel()] !== null;
    for (const f of state.features) {
        const p = f.properties;
        const el = document.createElementNS(SVG_NS, "path");
        el.setAttribute("d", geoPath(f.geometry));
        el.dataset.id = p.area_id; el.dataset.name = p.name_tr;
        if (look.fill === "shade") { el.classList.add("shade"); el.style.setProperty("--shade", hashShade(p.area_id, ramp)); }
        if (enterable) el.classList.add("enterable");
        areas.appendChild(el);

        const c = centroid(f.geometry);
        if (c) {
            const t = document.createElementNS(SVG_NS, "text");
            t.setAttribute("x", c[0].toFixed(1)); t.setAttribute("y", c[1].toFixed(1));
            t.dataset.id = p.area_id; t.dataset.w = projBounds(f.geometry).w.toFixed(1); t.textContent = p.name_tr;
            labels.appendChild(t);
        }
    }
    if (state.view) scaleLabels();
}
// Outlines on top, derived from the drawn shapes themselves rather than from a coarser
// file: a segment used by one polygon is the outer edge of the place; one shared by two
// polygons with different parents is a border between children (district lines under a
// neighbourhood layer). Sources differ in detail, so a parent's own polygon never fits
// over its children — this does, because it *is* them.
function drawOutline() {
    const g = $("#outline"); g.innerHTML = "";
    const seen = new Map(); // "x,y|x,y" -> {n, parents:Set, a, b}
    const key = (p) => p[0].toFixed(5) + "," + p[1].toFixed(5);
    for (const f of state.features) {
        const parent = f.properties.parent_id || "";
        const gm = f.geometry;
        const rings = gm.type === "Polygon" ? gm.coordinates : gm.coordinates.flat();
        for (const ring of rings) {
            for (let i = 1; i < ring.length; i++) {
                const a = ring[i - 1], b = ring[i], ka = key(a), kb = key(b);
                const k = ka < kb ? ka + "|" + kb : kb + "|" + ka;
                let e = seen.get(k);
                if (!e) { e = { n: 0, parents: new Set(), a, b }; seen.set(k, e); }
                e.n++; e.parents.add(parent);
            }
        }
    }
    let outer = "", inner = "";
    for (const e of seen.values()) {
        const d = "M" + proj.to(e.a).map((v) => v.toFixed(1)).join(" ") + "L" + proj.to(e.b).map((v) => v.toFixed(1)).join(" ");
        // The country needs no frame (the explorer draws none); a place inside one does.
        if (e.n === 1) { if (state.path.length > 1) outer += d; } else if (state.depth === 2 && e.parents.size > 1) inner += d;
    }
    for (const [d, cls] of [[inner, "inner"], [outer, "own"]]) {
        if (!d) continue;
        const el = document.createElementNS(SVG_NS, "path"); el.setAttribute("d", d); el.setAttribute("class", cls); g.appendChild(el);
    }
}
function drawContext() {
    const g = $("#context"); g.innerHTML = "";
    for (const f of state.context) {
        const el = document.createElementNS(SVG_NS, "path");
        el.setAttribute("d", geoPath(f.geometry));
        el.dataset.name = f.properties.name_tr; el.dataset.id = f.properties.area_id;
        g.appendChild(el);
    }
}

// Labels keep a constant on-screen size: SVG text scales with the viewBox, so the font is
// multiplied by the current zoom factor relative to the fitted view.
function scaleLabels() {
    const svg = $("#map"), v = state.view;
    const rect = svg.getBoundingClientRect();
    const unitsPerPx = Math.max(v.w / rect.width, v.h / rect.height);
    document.documentElement.style.setProperty("--map-font", (look.font * unitsPerPx) + "px");
    for (const t of $("#labels").children) {
        t.style.strokeWidth = (3 * unitsPerPx) + "px";
        // A name wider than its area would sit on the neighbours; it waits for a zoom-in.
        // The hovered one is shown regardless, in the tooltip's company.
        const fits = t.textContent.length * look.font * 0.5 < (+t.dataset.w) / unitsPerPx * 1.25;
        t.classList.toggle("tight", !fits);
    }
}

function drawCrumbs() {
    const c = $("#crumbs"); c.innerHTML = "";
    state.path.forEach((node, i) => {
        if (i) { const s = document.createElement("span"); s.className = "sep"; s.textContent = "›"; c.appendChild(s); }
        if (i === state.path.length - 1) { const h = document.createElement("span"); h.className = "here"; h.textContent = node.name; c.appendChild(h); }
        else { const b = document.createElement("button"); b.textContent = node.name; b.onclick = () => goTo(i); c.appendChild(b); }
    });
    $("#up").disabled = state.path.length === 1;
}
function drawLayer() {
    const l1 = CHILD[here().level], l2 = l1 && CHILD[l1];
    const box = $("#layer");
    box.hidden = !l2;
    if (!l2) return;
    box.innerHTML = [[1, l1], [2, l2]].map(([d, l]) =>
        `<button data-depth="${d}" class="${state.depth === d ? "on" : ""}">${LEVEL_TR[l]}</button>`).join("");
}

// Inset: Türkiye with the current province marked, so a zoomed-in view keeps its bearings.
async function drawInset() {
    const svg = $("#inset");
    const provinces = await fetchFeatures("country", "TR");
    if (!provinces) return;
    const p = projectionFor(provinces, 200);
    svg.setAttribute("viewBox", `0 0 ${p.W} ${p.H}`);
    const mark = state.path.length > 1 ? state.path[1].id : null;
    svg.innerHTML = provinces.map((f) =>
        `<path d="${pathWith(p, f.geometry)}" class="${f.properties.area_id === mark ? "mark" : ""}"/>`).join("");
}

// ---------- view ----------
function setView(v) {
    state.view = v;
    $("#map").setAttribute("viewBox", `${v.x} ${v.y} ${v.w} ${v.h}`);
    scaleLabels();
}
function fitView() {
    const rect = $("#map").getBoundingClientRect();
    const pad = 0.04, ar = rect.width / rect.height;
    let w = proj.W * (1 + 2 * pad), h = proj.H * (1 + 2 * pad);
    if (w / h < ar) w = h * ar; else h = w / ar;
    return { x: (proj.W - w) / 2, y: (proj.H - h) / 2, w, h };
}
function fit() { if (proj) setView(fitView()); }
function boxView(b, pad = 1.1) { // a bbox widened to the map's aspect, as a viewBox
    const rect = $("#map").getBoundingClientRect(), ar = rect.width / rect.height;
    let w = b.w * pad, h = b.h * pad;
    if (w / h < ar) w = h * ar; else h = w / ar;
    return { x: b.x + b.w / 2 - w / 2, y: b.y + b.h / 2 - h / 2, w, h };
}
function scaled(v, k) { return { x: v.x + v.w * (1 - k) / 2, y: v.y + v.h * (1 - k) / 2, w: v.w * k, h: v.h * k }; }
function animateView(to, ms = 320) {
    // A hidden tab gets no animation frames; jumping there keeps navigation from hanging.
    if (document.hidden || document.visibilityState !== "visible") { setView(to); return Promise.resolve(); }
    const from = { ...state.view }, t0 = performance.now();
    const ease = (t) => 1 - Math.pow(1 - t, 3);
    return new Promise((done) => {
        const step = (now) => {
            const t = Math.min(1, (now - t0) / ms), e = ease(t);
            setView({ x: from.x + (to.x - from.x) * e, y: from.y + (to.y - from.y) * e, w: from.w + (to.w - from.w) * e, h: from.h + (to.h - from.h) * e });
            if (t < 1) requestAnimationFrame(step); else done();
        };
        requestAnimationFrame(step);
    });
}
function zoomAt(factor, cx, cy) { // cx,cy in viewBox units
    const v = state.view, fitW = fitView().w;
    // Bounds: 40× into the fitted view (the data has no more detail than that) and 3× out.
    const w = v.w / factor;
    if (w < fitW / 40 || w > fitW * 3) return;
    setView({ x: cx - (cx - v.x) / factor, y: cy - (cy - v.y) / factor, w: v.w / factor, h: v.h / factor });
}
function toUnits(ev) {
    const svg = $("#map"), r = svg.getBoundingClientRect(), v = state.view;
    return [v.x + (ev.clientX - r.left) / r.width * v.w, v.y + (ev.clientY - r.top) / r.height * v.h];
}

// ---------- navigation ----------
// Entering: zoom onto the clicked shape, swap to the new place, then ease out from a
// slightly tight view to the fit. Leaving runs the same film backwards.
async function enter(path) {
    if (state.busy) return;
    const id = path.dataset.id, name = path.dataset.name;
    const level = layerLevel();
    if (!CHILD[level]) return;
    if (!(await fetchFeatures(level, id))) { $("#tip").innerHTML = `<b>${name}</b><small>alt sınırlar henüz yok</small>`; return; }
    state.busy = true;
    $("#tip").hidden = true;
    const feature = findFeature(id);
    await animateView(boxView(projBounds(feature.geometry)), 260);
    if (state.depth === 2) { // the clicked area's parent is skipped on the path, but named
        const parentId = feature.properties.parent_id;
        const pf = (await fetchFeatures(here().level, here().id)).find((f) => f.properties.area_id === parentId);
        state.path.push({ level: CHILD[here().level], id: parentId, name: pf ? pf.properties.name_tr : parentId });
    }
    state.path.push({ level: CHILD[here().level], id, name });
    state.depth = 1;
    await loadPlace();
    setView(scaled(fitView(), 0.6)); await animateView(fitView(), 320);
    state.busy = false;
}
async function goTo(index) {
    if (state.busy || index >= state.path.length - 1) return;
    state.busy = true;
    await animateView(scaled(fitView(), 0.6), 200);
    const leaving = here().id;
    state.path = state.path.slice(0, index + 1); state.depth = 1;
    await loadPlace();
    // Open from the box of the place just left, so the eye lands where it was.
    const f = findFeature(leaving);
    if (f) { setView(boxView(projBounds(f.geometry))); await animateView(fitView(), 320); }
    state.busy = false;
}
function goUp() { goTo(state.path.length - 2); }
async function goSideways(path) { // to a sibling of the current place, from its silhouette
    if (state.busy) return;
    state.busy = true;
    const f = state.context.find((x) => x.properties.area_id === path.dataset.id);
    await animateView(boxView(projBounds(f.geometry)), 260);
    state.path[state.path.length - 1] = { level: here().level, id: path.dataset.id, name: path.dataset.name };
    state.depth = 1; $("#tip").hidden = true;
    await loadPlace();
    setView(scaled(fitView(), 0.8)); await animateView(fitView(), 260);
    state.busy = false;
}

function bindMap() {
    const svg = $("#map"), tip = $("#tip");
    svg.addEventListener("wheel", (ev) => { ev.preventDefault(); const [cx, cy] = toUnits(ev); zoomAt(ev.deltaY < 0 ? 1.25 : 0.8, cx, cy); }, { passive: false });
    $("#zoom-in").onclick = () => zoomAt(1.4, state.view.x + state.view.w / 2, state.view.y + state.view.h / 2);
    $("#zoom-out").onclick = () => zoomAt(1 / 1.4, state.view.x + state.view.w / 2, state.view.y + state.view.h / 2);
    $("#zoom-fit").onclick = () => animateView(fitView(), 250);
    $("#up").onclick = goUp;
    svg.addEventListener("contextmenu", (ev) => { ev.preventDefault(); goUp(); });

    // Drag-to-pan on window-level listeners: pointer capture proved unreliable in some
    // browsers (the press lands on a <path>, the capture on the <svg>), and a drag that
    // leaves the map must still end cleanly.
    let drag = null;
    svg.addEventListener("dragstart", (ev) => ev.preventDefault());
    svg.addEventListener("pointerdown", (ev) => {
        if (ev.button !== 0) return;
        ev.preventDefault();
        drag = { x: ev.clientX, y: ev.clientY, v: { ...state.view }, moved: false, path: ev.target.closest("#areas path, #context path") };
    });
    window.addEventListener("pointermove", (ev) => {
        if (!drag) return;
        const r = svg.getBoundingClientRect();
        const dx = (ev.clientX - drag.x) / r.width * drag.v.w, dy = (ev.clientY - drag.y) / r.height * drag.v.h;
        if (!drag.moved && Math.abs(ev.clientX - drag.x) + Math.abs(ev.clientY - drag.y) > 3) { drag.moved = true; svg.classList.add("dragging"); tip.hidden = true; }
        if (drag.moved) setView({ ...drag.v, x: drag.v.x - dx, y: drag.v.y - dy });
    });
    svg.addEventListener("pointermove", (ev) => {
        if (drag) return;
        const path = ev.target.closest("#areas path, #context path");
        for (const t of $("#labels").querySelectorAll(".hot")) t.classList.remove("hot");
        if (path) {
            const inContext = path.parentNode.id === "context";
            // The ring is a stroke, and later siblings paint over it: raise the hovered area.
            if (!inContext && path !== path.parentNode.lastElementChild) path.parentNode.appendChild(path);
            const lbl = $("#labels").querySelector(`[data-id="${path.dataset.id}"]`); if (lbl) lbl.classList.add("hot");
            const level = inContext ? here().level : layerLevel();
            const hint = inContext ? "komşu · tıkla: oraya geç" : CHILD[level] ? "tıkla: içine gir" : "";
            tip.hidden = false; tip.innerHTML = `<b>${path.dataset.name}</b><small>${LEVEL_TR[level]}${hint ? " · " + hint : ""}</small>`;
            const wr = svg.parentElement.getBoundingClientRect();
            tip.style.left = (ev.clientX - wr.left + 14) + "px"; tip.style.top = (ev.clientY - wr.top + 14) + "px";
        } else tip.hidden = true;
    });
    window.addEventListener("pointerup", (ev) => {
        if (!drag) return;
        const { path, moved } = drag; drag = null; svg.classList.remove("dragging");
        if (moved || ev.button !== 0 || !path) return;
        if (path.parentNode.id === "context") goSideways(path); else enter(path);
    });
    svg.addEventListener("pointerleave", () => { tip.hidden = true; });
    window.addEventListener("resize", fit);
    document.addEventListener("keydown", (ev) => {
        if (ev.target instanceof Element && ev.target.matches("input, select, textarea")) return;
        if (ev.key === "Escape" || ev.key === "Backspace") goUp();
        const v = state.view, step = v.w * 0.08;
        const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[ev.key];
        if (d) { ev.preventDefault(); setView({ ...v, x: v.x + d[0], y: v.y + d[1] }); }
        if (ev.key === "+" || ev.key === "=") $("#zoom-in").click();
        if (ev.key === "-") $("#zoom-out").click();
        if (ev.key === "0") $("#zoom-fit").click();
    });
}

// ---------- boot ----------
buildPanel();
applyLook();
bindMap();
loadPlace().catch((e) => { $("#count").textContent = "Harita yüklenemedi: " + e.message; });
