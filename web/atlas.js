// Atlas: boundary-only drill-down map. Türkiye → il → ilçe → mahalle, drawn as SVG
// paths in an equirectangular projection fitted to the current level. No indicator data
// is read here; this page is the canvas the indicators will later be painted on (K28).
//
// Look settings (theme, fill, stroke, labels…) live in localStorage under one key and are
// applied as CSS custom properties / data attributes, so the stylesheet does the styling.
"use strict";

const GEO = {
    country: () => "../public/areas.geojson",
    province: (id) => `../public/geo/districts/${id}.geojson`,
    district: (id) => `../public/geo/neighbourhoods/${id}.geojson`,
};
const LEVEL_TR = { country: "İl", province: "İlçe", district: "Mahalle" };
const CHILD = { country: "province", province: "district", district: null };

const HUES = [
    { id: "mavi", dark: "#3b5c8c", light: "#c7d7ec" },
    { id: "yesil", dark: "#3a6b5e", light: "#c9e3d9" },
    { id: "turuncu", dark: "#8c4d3a", light: "#f2d3c7" },
    { id: "mor", dark: "#5b4778", light: "#dfd2ec" },
    { id: "gri", dark: "#3a3a3a", light: "#dedede" },
];

const DEFAULT_LOOK = {
    theme: "dark", fill: "flat", hue: "mavi", stroke: 8, strokeColor: "dark",
    labels: "hover", font: 11, hover: "on",
};
const LOOK_KEY = "veriatlas.atlas.look";
let look = loadLook();

function loadLook() {
    try { return { ...DEFAULT_LOOK, ...JSON.parse(localStorage.getItem(LOOK_KEY) || "{}") }; }
    catch { return { ...DEFAULT_LOOK }; }
}

const $ = (s) => document.querySelector(s);

const state = {
    path: [{ level: "country", id: "TR", name: "Türkiye" }],
    features: [],
    view: null, // viewBox {x,y,w,h}
};
const cache = new Map();

// ---------- look ----------
function applyLook() {
    const root = document.documentElement;
    const light = look.theme === "light";
    root.dataset.theme = look.theme;
    root.dataset.fill = look.fill;
    root.dataset.labels = look.labels;
    root.dataset.hover = look.hover;

    const hue = HUES.find((h) => h.id === look.hue) || HUES[0];
    root.style.setProperty("--map-fill", light ? hue.light : hue.dark);
    root.style.setProperty("--map-hover", light ? "#ffd98a" : "#d9a441");
    root.style.setProperty("--map-stroke-width", (look.stroke / 10) + "px");
    root.style.setProperty("--map-font", look.font + "px");
    const strokeColors = {
        dark: light ? "#2b2b2b" : "#0d0d0d",
        light: light ? "#ffffff" : "#cfcfcf",
        accent: light ? "#286bbb" : "#7fa8d8",
    };
    root.style.setProperty("--map-stroke", strokeColors[look.strokeColor]);

    localStorage.setItem(LOOK_KEY, JSON.stringify(look));
    syncPanel();
}

function syncPanel() {
    for (const [id, key] of [["set-theme", "theme"], ["set-fill", "fill"], ["set-stroke-color", "strokeColor"],
        ["set-labels", "labels"], ["set-hover", "hover"], ["set-hue", "hue"]]) {
        for (const b of document.getElementById(id).children) b.classList.toggle("on", b.dataset.value === look[key]);
    }
    $("#set-stroke").value = look.stroke; $("#set-stroke-value").textContent = (look.stroke / 10).toFixed(1) + " px";
    $("#set-font").value = look.font; $("#set-font-value").textContent = look.font + " px";
}

function buildPanel() {
    $("#set-hue").innerHTML = HUES.map((h) => `<button data-value="${h.id}" title="${h.id}" style="background:${h.dark}"></button>`).join("");
    const pick = (id, key, after) => {
        document.getElementById(id).onclick = (ev) => {
            const b = ev.target.closest("button"); if (!b) return;
            look[key] = b.dataset.value; applyLook(); if (after) after();
        };
    };
    pick("set-theme", "theme"); pick("set-fill", "fill", drawAreas); pick("set-hue", "hue");
    pick("set-stroke-color", "strokeColor"); pick("set-labels", "labels"); pick("set-hover", "hover");
    $("#set-stroke").oninput = (e) => { look.stroke = +e.target.value; applyLook(); };
    $("#set-font").oninput = (e) => { look.font = +e.target.value; applyLook(); };
    $("#set-reset").onclick = () => { look = { ...DEFAULT_LOOK }; applyLook(); drawAreas(); };
    $("#look-toggle").onclick = () => {
        const p = $("#look"); p.hidden = !p.hidden;
        $("#look-toggle").setAttribute("aria-expanded", String(!p.hidden));
    };
}

// ---------- geometry ----------
let proj = null;
function makeProjection(features) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const walk = (c) => {
        if (typeof c[0] === "number") { minX = Math.min(minX, c[0]); maxX = Math.max(maxX, c[0]); minY = Math.min(minY, c[1]); maxY = Math.max(maxY, c[1]); }
        else c.forEach(walk);
    };
    features.forEach((f) => walk(f.geometry.coordinates));
    const k = Math.cos(((minY + maxY) / 2) * Math.PI / 180);
    const W = 1000, H = 1000 * ((maxY - minY) / ((maxX - minX) * k));
    const sx = W / ((maxX - minX) * k), sy = H / (maxY - minY);
    proj = { W, H, to: ([x, y]) => [(x - minX) * k * sx, (maxY - y) * sy] };
}
const ringPath = (ring) => ring.map((p, i) => (i ? "L" : "M") + proj.to(p).map((v) => v.toFixed(1)).join(" ")).join("") + "Z";
function geoPath(g) {
    if (g.type === "Polygon") return g.coordinates.map(ringPath).join("");
    return g.coordinates.map((poly) => poly.map(ringPath).join("")).join("");
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
async function loadLevel() {
    const here = state.path[state.path.length - 1];
    const url = GEO[here.level](here.id);
    if (!cache.has(url)) {
        const r = await fetch(url);
        if (!r.ok) throw new Error(`${r.status} ${url}`);
        const g = await r.json();
        g.features.sort((a, b) => a.properties.name_tr.localeCompare(b.properties.name_tr, "tr"));
        cache.set(url, g.features);
    }
    state.features = cache.get(url);
    makeProjection(state.features);
    state.view = { x: 0, y: 0, w: proj.W, h: proj.H };
    drawAreas();
    drawCrumbs();
    fit();
}

async function hasChildren(level, id) {
    const next = CHILD[level]; if (!next) return false;
    const url = GEO[next](id);
    if (cache.has(url)) return true;
    try { const r = await fetch(url, { method: "HEAD" }); return r.ok; } catch { return false; }
}

// ---------- drawing ----------
function hashShade(id) {
    let h = 0; for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    const light = look.theme === "light";
    const base = HUES.find((x) => x.id === look.hue) || HUES[0];
    const t = (h % 1000) / 1000; // 0..1
    return `color-mix(in srgb, ${light ? base.light : base.dark} ${Math.round(55 + t * 45)}%, ${light ? "#ffffff" : "#000000"})`;
}

function drawAreas() {
    const here = state.path[state.path.length - 1];
    const areas = $("#areas"), labels = $("#labels");
    areas.innerHTML = ""; labels.innerHTML = "";
    for (const f of state.features) {
        const p = f.properties;
        const el = document.createElementNS("http://www.w3.org/2000/svg", "path");
        el.setAttribute("d", geoPath(f.geometry));
        el.dataset.id = p.area_id; el.dataset.name = p.name_tr;
        if (look.fill === "shade") { el.classList.add("shade"); el.style.setProperty("--shade", hashShade(p.area_id)); }
        if (CHILD[here.level]) el.classList.add("enterable");
        areas.appendChild(el);

        const c = centroid(f.geometry);
        if (c) {
            const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
            t.setAttribute("x", c[0].toFixed(1)); t.setAttribute("y", c[1].toFixed(1));
            t.dataset.id = p.area_id; t.textContent = p.name_tr;
            labels.appendChild(t);
        }
    }
    $("#count").textContent = `${LEVEL_TR[here.level]} düzeyi · ${state.features.length} alan`;
    scaleLabels();
}

// Labels keep a constant on-screen size: SVG text scales with the viewBox, so the font is
// multiplied by the current zoom factor relative to the fitted view.
function scaleLabels() {
    const svg = $("#map"), v = state.view;
    const rect = svg.getBoundingClientRect();
    const unitsPerPx = Math.max(v.w / rect.width, v.h / rect.height);
    document.documentElement.style.setProperty("--map-font", (look.font * unitsPerPx) + "px");
    $("#labels").style.setProperty("--sw", (3 * unitsPerPx) + "px");
    for (const t of $("#labels").children) t.style.strokeWidth = (3 * unitsPerPx) + "px";
}

function drawCrumbs() {
    const c = $("#crumbs"); c.innerHTML = "";
    state.path.forEach((node, i) => {
        if (i) { const s = document.createElement("span"); s.className = "sep"; s.textContent = "›"; c.appendChild(s); }
        if (i === state.path.length - 1) { const h = document.createElement("span"); h.className = "here"; h.textContent = node.name; c.appendChild(h); }
        else { const b = document.createElement("button"); b.textContent = node.name; b.onclick = () => { state.path = state.path.slice(0, i + 1); loadLevel(); }; c.appendChild(b); }
    });
    $("#up").disabled = state.path.length === 1;
}

// ---------- view ----------
function setView(v) {
    state.view = v;
    $("#map").setAttribute("viewBox", `${v.x} ${v.y} ${v.w} ${v.h}`);
    scaleLabels();
}
function fit() {
    const rect = $("#map").getBoundingClientRect();
    const pad = 0.04;
    const ar = rect.width / rect.height;
    let w = proj.W * (1 + 2 * pad), h = proj.H * (1 + 2 * pad);
    if (w / h < ar) w = h * ar; else h = w / ar;
    setView({ x: (proj.W - w) / 2, y: (proj.H - h) / 2, w, h });
}
function zoomAt(factor, cx, cy) { // cx,cy in viewBox units
    const v = state.view;
    const w = v.w / factor, h = v.h / factor;
    setView({ x: cx - (cx - v.x) / factor, y: cy - (cy - v.y) / factor, w, h });
}
function toUnits(ev) {
    const svg = $("#map"), r = svg.getBoundingClientRect(), v = state.view;
    return [v.x + (ev.clientX - r.left) / r.width * v.w, v.y + (ev.clientY - r.top) / r.height * v.h];
}

function bindMap() {
    const svg = $("#map"), tip = $("#tip");
    svg.addEventListener("wheel", (ev) => { ev.preventDefault(); const [cx, cy] = toUnits(ev); zoomAt(ev.deltaY < 0 ? 1.25 : 0.8, cx, cy); }, { passive: false });
    $("#zoom-in").onclick = () => zoomAt(1.4, state.view.x + state.view.w / 2, state.view.y + state.view.h / 2);
    $("#zoom-out").onclick = () => zoomAt(1 / 1.4, state.view.x + state.view.w / 2, state.view.y + state.view.h / 2);
    $("#zoom-fit").onclick = fit;
    $("#up").onclick = goUp;
    svg.addEventListener("contextmenu", (ev) => { ev.preventDefault(); goUp(); });

    let drag = null;
    svg.addEventListener("pointerdown", (ev) => { if (ev.button !== 0) return; drag = { x: ev.clientX, y: ev.clientY, v: { ...state.view }, moved: false }; svg.setPointerCapture(ev.pointerId); });
    svg.addEventListener("pointermove", (ev) => {
        if (drag) {
            const r = svg.getBoundingClientRect();
            const dx = (ev.clientX - drag.x) / r.width * drag.v.w, dy = (ev.clientY - drag.y) / r.height * drag.v.h;
            if (Math.abs(ev.clientX - drag.x) + Math.abs(ev.clientY - drag.y) > 3) { drag.moved = true; svg.classList.add("dragging"); }
            setView({ ...drag.v, x: drag.v.x - dx, y: drag.v.y - dy });
            return;
        }
        const path = ev.target.closest("path");
        for (const t of $("#labels").querySelectorAll(".hot")) t.classList.remove("hot");
        if (path) {
            const lbl = $("#labels").querySelector(`[data-id="${path.dataset.id}"]`); if (lbl) lbl.classList.add("hot");
            const here = state.path[state.path.length - 1];
            tip.hidden = false; tip.innerHTML = `<b>${path.dataset.name}</b><small>${LEVEL_TR[here.level]}${CHILD[here.level] ? " · tıkla: içine gir" : ""}</small>`;
            const wr = svg.parentElement.getBoundingClientRect();
            tip.style.left = (ev.clientX - wr.left + 14) + "px"; tip.style.top = (ev.clientY - wr.top + 14) + "px";
        } else tip.hidden = true;
    });
    svg.addEventListener("pointerup", async (ev) => {
        const moved = drag && drag.moved; drag = null; svg.classList.remove("dragging");
        if (moved || ev.button !== 0) return;
        const path = ev.target.closest("path"); if (!path) return;
        const here = state.path[state.path.length - 1];
        if (!CHILD[here.level]) return;
        if (!(await hasChildren(here.level, path.dataset.id))) { tip.innerHTML = `<b>${path.dataset.name}</b><small>alt sınırlar henüz yok</small>`; return; }
        state.path.push({ level: CHILD[here.level], id: path.dataset.id, name: path.dataset.name });
        tip.hidden = true; loadLevel();
    });
    svg.addEventListener("pointerleave", () => { tip.hidden = true; });
    window.addEventListener("resize", fit);
    document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" || ev.key === "Backspace") goUp(); });
}
function goUp() { if (state.path.length > 1) { state.path.pop(); loadLevel(); } }

// ---------- boot ----------
buildPanel();
applyLook();
bindMap();
loadLevel().catch((e) => { $("#count").textContent = "Harita yüklenemedi: " + e.message; });
