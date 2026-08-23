/* Atlas: drill-down map (Türkiye → il → ilçe → mahalle) with a sign card on the left
   and a sortable unit table on the right. No libraries; geometry drawn as SVG paths in
   an equirectangular projection fitted to the current level's bounding box. */
"use strict";

const GEO = {
    country: "../public/areas.geojson",
    province: (id) => `../public/geo/districts/${id}.geojson`,
    district: (id) => `../public/geo/neighbourhoods/${id}.geojson`,
};
const BUNDLES = { "TR-16-006": "../public/atlas/TR-16-006.json" };
const KIND_TR = { centre: "Merkez", urban_town: "Kentsel belde", rural_town: "Kırsal belde", village: "Köy" };
const KIND_COLOR = { centre: "#5b8fd1", urban_town: "#d97706", rural_town: "#7da33a", village: "#8b5e34" };
const MOCK = new URLSearchParams(location.search).has("bos"); // ?bos → sayılar boş, yapı duruyor
const fmt = (n, d = 0) => MOCK ? "—" : n == null || Number.isNaN(n) ? "—" : n.toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (x, d = 1) => MOCK || x == null ? "—" : (x * 100).toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d }) + " %";

const state = {
    level: "country", // country | province | district
    path: [{ level: "country", id: "TR", name: "Türkiye" }],
    features: [],
    mode: "plain",
    indicator: null,
    selected: null,
    bundle: null,
    sort: { key: null, dir: -1 },
    filter: "",
    view: null, // {x,y,w,h} viewBox
};

// ---------- geometry ----------
let proj = null;
function makeProjection(features) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const walk = (c) => { if (typeof c[0] === "number") { minX = Math.min(minX, c[0]); maxX = Math.max(maxX, c[0]); minY = Math.min(minY, c[1]); maxY = Math.max(maxY, c[1]); } else c.forEach(walk); };
    features.forEach((f) => walk(f.geometry.coordinates));
    const k = Math.cos(((minY + maxY) / 2) * Math.PI / 180);
    const W = 1000, H = 1000 * ((maxY - minY) / ((maxX - minX) * k));
    const sx = W / ((maxX - minX) * k), sy = H / (maxY - minY);
    proj = { W, H, to: ([x, y]) => [(x - minX) * k * sx, (maxY - y) * sy] };
    return proj;
}
function ringPath(ring) { return ring.map((p, i) => (i ? "L" : "M") + proj.to(p).map((v) => v.toFixed(1)).join(" ")).join("") + "Z"; }
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

// ---------- data helpers ----------
function unitRows() {
    const b = state.bundle; if (!b) return [];
    return b.units.map((u) => {
        const age = u.age; let median = null, old = null;
        if (age) {
            const tot = age.male.map((m, i) => m + age.female[i]); const n = tot.reduce((a, c) => a + c, 0); let acc = 0;
            for (let i = 0; i < tot.length; i++) { const w = i < 13 ? 5 : 10; if (acc + tot[i] >= n / 2) { median = i * 5 + (n / 2 - acc) / tot[i] * w; break; } acc += tot[i]; }
            old = tot[13] / n;
        }
        const m = u.marital; const m15 = m ? Object.values(m).reduce((a, c) => a + c, 0) : 0;
        return {
            id: u.id, name: u.name, kind: u.kind, kindTr: KIND_TR[u.kind], urban: u.urban ? "Kent" : "Kır", settlement: u.settlement,
            population: u.population, households: u.households, perHousehold: u.households ? u.population / u.households : null,
            female100: u.male ? u.female / u.male * 100 : null, median, old, married: m ? m.married / m15 : null, never: m ? m.never / m15 : null,
            area: u.area_km2_endeksa,
        };
    });
}
const COLS = {
    district: [
        { key: "name", label: "Birim", text: true },
        { key: "urban", label: "Kent/Kır", text: true },
        { key: "kindTr", label: "Tür", text: true },
        { key: "population", label: "Nüfus", f: (v) => fmt(v) },
        { key: "households", label: "Hane", f: (v) => fmt(v) },
        { key: "perHousehold", label: "Kişi/hane", f: (v) => fmt(v, 2) },
        { key: "female100", label: "Kadın/100 E", f: (v) => fmt(v, 1) },
        { key: "median", label: "Medyan yaş", f: (v) => fmt(v, 1), est: true },
        { key: "old", label: "65+", f: (v) => pct(v) },
        { key: "married", label: "Evli", f: (v) => pct(v) },
        { key: "never", label: "Hiç evlenmedi", f: (v) => pct(v) },
    ],
    generic: [{ key: "name", label: "Ad", text: true }, { key: "has", label: "Veri", text: true }],
};
const INDICATORS = [
    { key: "population", label: "Nüfus", f: (v) => fmt(v) },
    { key: "perHousehold", label: "Hane başına kişi", f: (v) => fmt(v, 2) },
    { key: "female100", label: "Kadın / 100 erkek", f: (v) => fmt(v, 1) },
    { key: "median", label: "Medyan yaş", f: (v) => fmt(v, 1) },
    { key: "old", label: "65+ payı", f: (v) => pct(v) },
    { key: "married", label: "Evli payı (15+)", f: (v) => pct(v) },
    { key: "never", label: "Hiç evlenmemiş payı (15+)", f: (v) => pct(v) },
];

// ---------- load & navigate ----------
async function loadJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error(url); return r.json(); }

async function goto(level, id, name) {
    state.level = level; state.selected = null; state.sort = { key: null, dir: -1 }; state.filter = ""; $("#filter").value = "";
    const url = level === "country" ? GEO.country : level === "province" ? GEO.province(id) : GEO.district(id);
    let geo; try { geo = await loadJSON(url); } catch { geo = { features: [] }; }
    state.features = geo.features;
    state.bundle = level === "district" && BUNDLES[id] ? await loadJSON(BUNDLES[id]) : null;
    const country = { level: "country", id: "TR", name: "Türkiye" };
    if (level === "country") state.path = [country];
    else if (level === "province") state.path = [country, { level, id, name }];
    else {
        const prov = state.path[1] && state.path[1].level === "province" ? state.path[1]
            : { level: "province", id: state.bundle ? state.bundle.province_id : id.slice(0, 5), name: state.bundle ? state.bundle.province : id.slice(0, 5) };
        state.path = [country, prov, { level, id, name: state.bundle ? state.bundle.name : name }];
    }
    makeProjection(state.features.length ? state.features : [{ geometry: { type: "Polygon", coordinates: [[[25, 35], [45, 35], [45, 43], [25, 43], [25, 35]]] } }]);
    state.view = null;
    drawMap(); drawCrumbs(); drawLeft(); drawTable(); drawLegend(); updateIndicatorBox();
    location.hash = level === "country" ? "" : id;
}

// ---------- map ----------
const $ = (s) => document.querySelector(s);
const svg = $("#map");
function fitView() { const pad = 30; state.view = { x: -pad, y: -pad, w: proj.W + pad * 2, h: proj.H + pad * 2 }; applyView(); }
function applyView() { const v = state.view; svg.setAttribute("viewBox", `${v.x} ${v.y} ${v.w} ${v.h}`); }
function hasData(f) {
    if (state.level === "country") return f.properties.area_id === "TR-16";
    if (state.level === "province") return !!BUNDLES[f.properties.area_id];
    return true;
}
function fillFor(f, rowsById) {
    if (!hasData(f)) return null;
    const id = f.properties.area_id;
    if (state.level === "district") {
        if (state.mode === "kind") return KIND_COLOR[f.properties.kind];
        if (state.mode === "theme" && state.indicator) { const r = rowsById[id]; const v = r ? r[state.indicator.key] : null; return Number.isFinite(v) ? ramp(v) : "var(--map-muted)"; }
    }
    return null;
}
let rampScale = null;
function ramp(v) { const t = Math.max(0, Math.min(1, (v - rampScale.min) / (rampScale.max - rampScale.min || 1))); return mix("#e3ebf6", "#1f3a73", t); }
function mix(a, b, t) { const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)); const [r1, g1, b1] = p(a), [r2, g2, b2] = p(b); return `rgb(${Math.round(r1 + (r2 - r1) * t)},${Math.round(g1 + (g2 - g1) * t)},${Math.round(b1 + (b2 - b1) * t)})`; }

function drawMap() {
    const rows = unitRows(); const rowsById = Object.fromEntries(rows.map((r) => [r.id, r]));
    if (state.mode === "theme" && state.indicator && rows.length) { const vals = rows.map((r) => r[state.indicator.key]).filter((v) => Number.isFinite(v)); rampScale = { min: Math.min(...vals), max: Math.max(...vals) }; }
    svg.innerHTML = "";
    const g = document.createElementNS(svg.namespaceURI, "g"); g.id = "areas";
    const labels = document.createElementNS(svg.namespaceURI, "g"); labels.id = "labels";
    for (const f of state.features) {
        const p = document.createElementNS(svg.namespaceURI, "path");
        p.setAttribute("d", geoPath(f.geometry)); p.classList.add("area");
        const id = f.properties.area_id; p.dataset.id = id;
        if (!hasData(f)) p.classList.add("muted");
        const fill = fillFor(f, rowsById); if (fill) p.style.fill = fill;
        if (state.selected === id) p.classList.add("sel");
        p.addEventListener("mousemove", (e) => showTip(e, f, rowsById[id]));
        p.addEventListener("mouseleave", hideTip);
        p.addEventListener("click", () => onAreaClick(f));
        g.appendChild(p);
        const c = centroid(f.geometry);
        if (c && (state.level !== "country" || hasData(f) || state.features.length < 100)) {
            const t = document.createElementNS(svg.namespaceURI, "text"); t.setAttribute("x", c[0]); t.setAttribute("y", c[1]); t.textContent = f.properties.name_tr;
            t.classList.add("lbl"); if (hasData(f) && state.level !== "district") t.classList.add("big"); if (state.level === "country" && !hasData(f)) t.style.display = "none";
            labels.appendChild(t);
        }
    }
    svg.appendChild(g); svg.appendChild(labels);
    if (!state.view) fitView(); else applyView();
}
function onAreaClick(f) {
    const id = f.properties.area_id, name = f.properties.name_tr;
    if (state.level === "country") return goto("province", id, name);
    if (state.level === "province") { if (BUNDLES[id]) return goto("district", id, name); state.selected = id; drawMap(); drawLeft(); return; }
    state.selected = state.selected === id ? null : id; drawMap(); drawLeft(); drawTable();
}
function showTip(e, f, row) {
    const tip = $("#tip"); tip.hidden = false;
    let body = `<b>${f.properties.name_tr}</b>`;
    if (row) { body += `${row.kindTr} · ${fmt(row.population)} kişi`; if (state.mode === "theme" && state.indicator) body += `<br>${state.indicator.label}: ${state.indicator.f(row[state.indicator.key])}`; }
    else body += hasData(f) ? "Tıkla → içine gir" : "<span class='muted'>Henüz veri yok</span>";
    tip.innerHTML = body; const r = $(".map-wrap").getBoundingClientRect(); tip.style.left = (e.clientX - r.left + 14) + "px"; tip.style.top = (e.clientY - r.top + 14) + "px";
}
function hideTip() { $("#tip").hidden = true; }

// pan & zoom
let drag = null;
svg.addEventListener("mousedown", (e) => { drag = { x: e.clientX, y: e.clientY, v: { ...state.view } }; svg.classList.add("dragging"); });
window.addEventListener("mousemove", (e) => { if (!drag) return; const s = state.view.w / svg.clientWidth; state.view.x = drag.v.x - (e.clientX - drag.x) * s; state.view.y = drag.v.y - (e.clientY - drag.y) * s; applyView(); });
window.addEventListener("mouseup", () => { drag = null; svg.classList.remove("dragging"); });
svg.addEventListener("wheel", (e) => { e.preventDefault(); zoomBy(e.deltaY < 0 ? 0.8 : 1.25, e); }, { passive: false });
function zoomBy(k, e) {
    const v = state.view; const r = svg.getBoundingClientRect();
    const fx = e ? (e.clientX - r.left) / r.width : 0.5, fy = e ? (e.clientY - r.top) / r.height : 0.5;
    const nx = v.x + v.w * fx * (1 - k), ny = v.y + v.h * fy * (1 - k);
    state.view = { x: nx, y: ny, w: v.w * k, h: v.h * k }; applyView();
}
$("#zoom-in").onclick = () => zoomBy(0.8); $("#zoom-out").onclick = () => zoomBy(1.25); $("#zoom-fit").onclick = fitView;

// ---------- crumbs / modes ----------
function drawCrumbs() {
    const el = $("#crumbs"); el.innerHTML = "";
    state.path.forEach((p, i) => {
        if (i) { const s = document.createElement("span"); s.className = "sep"; s.textContent = "›"; el.appendChild(s); }
        const a = document.createElement(i === state.path.length - 1 ? "span" : "a"); a.textContent = p.name;
        if (i === state.path.length - 1) a.className = "cur"; else a.onclick = () => goto(p.level, p.id, p.name);
        el.appendChild(a);
    });
}
document.querySelectorAll("#mode button").forEach((b) => b.onclick = () => { state.mode = b.dataset.mode; document.querySelectorAll("#mode button").forEach((x) => x.classList.toggle("on", x === b)); updateIndicatorBox(); drawMap(); drawLegend(); });
function updateIndicatorBox() {
    const sel = $("#indicator"); sel.hidden = !(state.mode === "theme" && state.level === "district" && state.bundle);
    if (!sel.options.length) { INDICATORS.forEach((ind, i) => { const o = document.createElement("option"); o.value = i; o.textContent = ind.label; sel.appendChild(o); }); sel.onchange = () => { state.indicator = INDICATORS[sel.value]; drawMap(); drawLegend(); }; }
    if (!state.indicator) state.indicator = INDICATORS[0];
}
$("#theme-toggle").onclick = () => { const h = document.documentElement; h.dataset.theme = h.dataset.theme === "dark" ? "light" : "dark"; drawMap(); };

function drawLegend() {
    const el = $("#legend"); el.innerHTML = "";
    if (state.level !== "district" || !state.bundle) { if (state.level !== "district") el.innerHTML = `<div class="t">Veri olan alanlar</div><div class="row"><span class="sw" style="background:var(--map-fill)"></span>var</div><div class="row"><span class="sw" style="background:var(--map-muted)"></span>henüz yok</div>`; return; }
    if (state.mode === "kind") { el.innerHTML = `<div class="t">Yerleşim türü</div>` + Object.entries(KIND_TR).filter(([k]) => k !== "urban_town").map(([k, v]) => `<div class="row"><span class="sw" style="background:${KIND_COLOR[k]}"></span>${v}</div>`).join(""); }
    else if (state.mode === "theme" && state.indicator && rampScale) { el.innerHTML = `<div class="t">${state.indicator.label}</div><div class="ramp" style="background:linear-gradient(90deg,#e3ebf6,#1f3a73)"></div><div class="ends"><span>${state.indicator.f(rampScale.min)}</span><span>${state.indicator.f(rampScale.max)}</span></div><div class="row muted" style="margin-top:4px">gri = veri yok</div>`; }
}

// ---------- left panel ----------
function sign(ctx, name, band, bandColor, stripe) {
    return `<div class="sign"><div class="stripe" style="background:${stripe || "transparent"}"></div><div class="ctx">${ctx}</div><div class="name">${name}</div><div class="band" style="background:${bandColor}">${band}</div></div>`;
}
function drawLeft() {
    const b = state.bundle; const cur = state.path[state.path.length - 1];
    let sg, card = "", mini = "";
    if (state.level === "country") { sg = sign("", "Türkiye", "Ülke", "var(--sign-turkey)"); card = `<h3>Kapsam</h3><div class="kv"><span class="k">İl</span><span class="v">81</span><span class="u"></span><span class="k">Veri olan il</span><span class="v">1</span><span class="u">Bursa</span></div><p class="muted">Haritada koyu il tıklanır. Pilot: Bursa › İznik.</p>`; }
    else if (state.level === "province") { sg = sign("Türkiye", cur.name, "İl", "var(--sign-region)"); card = `<h3>Kapsam</h3><div class="kv"><span class="k">İlçe</span><span class="v">${state.features.length}</span><span class="u"></span><span class="k">Veri olan ilçe</span><span class="v">${state.features.filter(hasData).length}</span><span class="u"></span></div><p class="muted">${cur.id === "TR-16" ? "İznik tıklanır; diğer ilçeler sırada." : "Bu ilde henüz ilçe verisi yok."}</p>`; }
    else if (b) {
        const rows = unitRows(); const sel = rows.find((r) => r.id === state.selected);
        if (sel) {
            const u = b.units.find((x) => x.id === sel.id);
            sg = sign(`${b.name} · ${sel.kindTr}`, sel.name, `${sel.kind === "village" ? "Köy" : "Mahalle"} · ${b.name}`, "var(--sign-iznik)", KIND_COLOR[sel.kind] === "#5b8fd1" ? null : KIND_COLOR[sel.kind]);
            card = `<h3>Kimlik</h3><div class="kv">
              <span class="k">Kent / Kır</span><span class="v">${sel.urban}</span><span class="u"></span>
              <span class="k">Semt</span><span class="v">${sel.settlement}</span><span class="u"></span>
              <span class="sect">Nüfus (TÜİK ${b.reference_year})</span>
              <span class="k">Nüfus</span><span class="v">${fmt(sel.population)}</span><span class="u">kişi</span>
              <span class="k">Erkek / Kadın</span><span class="v">${fmt(u.male)} / ${fmt(u.female)}</span><span class="u"></span>
              <span class="k">Hane</span><span class="v">${fmt(sel.households)}</span><span class="u"></span>
              <span class="k">Kişi / hane</span><span class="v">${fmt(sel.perHousehold, 2)}</span><span class="u"></span>
              <span class="k">Medyan yaş</span><span class="v">${fmt(sel.median, 1)}</span><span class="u">${sel.median == null ? "veri yok" : ""}</span>
              <span class="k">65+ payı</span><span class="v">${pct(sel.old)}</span><span class="u"></span>
              <span class="sect">Medeni durum (15+)</span>
              <span class="k">Evli</span><span class="v">${pct(sel.married)}</span><span class="u"></span>
              <span class="k">Hiç evlenmedi</span><span class="v">${pct(sel.never)}</span><span class="u"></span>
            </div>`;
            mini = u.age ? pyramid(u.age, `${sel.name} — yaş yapısı`) : `<p class="muted">Bu birim için yaş dağılımı yayımlanmıyor (kır mahallelerinin çoğu).</p>`;
        } else {
            const c = b.card;
            sg = sign(`${b.province} ili · ${b.region}`, b.name, `İlçe · ${b.province}`, "var(--sign-bursa)");
            card = `<h3>Kimlik</h3><div class="kv">
              <span class="k">Yüzölçüm</span><span class="v">${fmt(c.area_km2)}</span><span class="u">km²</span>
              <span class="k">Rakım</span><span class="v">${fmt(c.elevation_m)}</span><span class="u">m</span>
              <span class="k">İl merkezine</span><span class="v">${fmt(c.distance_to_province_km)}</span><span class="u">km</span>
              <span class="sect">Nüfus (TÜİK ${b.reference_year})</span>
              <span class="k">Nüfus</span><span class="v">${fmt(c.population)}</span><span class="u">kişi</span>
              <span class="k">Yoğunluk</span><span class="v">${fmt(c.population / c.area_km2, 1)}</span><span class="u">kişi/km²</span>
              <span class="k">Kentsel nüfus oranı</span><span class="v">${pct(c.urban_population / c.population)}</span><span class="u"></span>
              <span class="k">Hane</span><span class="v">${fmt(c.households)}</span><span class="u"></span>
              <span class="k">Medyan yaş</span><span class="v">${fmt(medianOf(b.age.district), 1)}</span><span class="u">yaş</span>
              <span class="k">Kent / Kır medyan</span><span class="v">${fmt(medianOf(b.age.urban), 1)} / ${fmt(medianOf(b.age.rural), 1)}</span><span class="u"></span>
              <span class="sect">Yerleşim</span>
              <span class="k">Kentsel birim</span><span class="v">${c.centre_units}</span><span class="u">adet</span>
              <span class="k">Kırsal birim</span><span class="v">${c.rural_units}</span><span class="u">adet</span>
            </div><p class="muted">${c.area_note}</p>`;
            mini = pyramid(b.age.district, "İlçe — nüfus piramidi 2024");
        }
    }
    $("#sign").outerHTML = sg.replace('class="sign"', 'class="sign" id="sign"');
    $("#card").innerHTML = card; $("#mini").innerHTML = mini; $("#mini").className = "card mini";
}
function medianOf(age) { const tot = age.male.map((m, i) => m + age.female[i]); const n = tot.reduce((a, c) => a + c, 0); let acc = 0; for (let i = 0; i < tot.length; i++) { const w = (i === tot.length - 1) ? 10 : 5; if (acc + tot[i] >= n / 2) return i * 5 + (n / 2 - acc) / tot[i] * w; acc += tot[i]; } return null; }
function pyramid(age, title) {
    if (MOCK) return `<h3>${title}</h3><p class="muted">(piramit — veri bağlanınca)</p>`;
    const N = age.bands.length, W = 300, H = 14 * N + 24, cw = 110, cx = W / 2, rh = 14;
    const mx = Math.max(...age.male, ...age.female), sc = cw / mx;
    let s = `<h3>${title}</h3><svg viewBox="0 0 ${W} ${H}" font-family="Lato,sans-serif" font-size="9">`;
    for (let i = 0; i < N; i++) {
        const y = H - (i + 1) * rh, est = age.estimate_from_band != null && i >= age.estimate_from_band;
        const wm = age.male[i] * sc, wf = age.female[i] * sc;
        s += `<rect x="${cx - 18 - wm}" y="${y + 1}" width="${wm}" height="${rh - 2}" fill="var(--male)" opacity="${est ? .55 : 1}"/><rect x="${cx + 18}" y="${y + 1}" width="${wf}" height="${rh - 2}" fill="var(--female)" opacity="${est ? .55 : 1}"/>`;
        s += `<text x="${cx}" y="${y + rh - 4}" text-anchor="middle" fill="var(--text-secondary)">${age.bands[i]}</text>`;
    }
    s += `<text x="${cx - 18 - cw}" y="10" fill="var(--male)" font-weight="700">Erkek</text><text x="${cx + 18 + cw}" y="10" text-anchor="end" fill="var(--female)" font-weight="700">Kadın</text></svg>`;
    if (age.estimate_from_band != null) s += `<p class="muted"><span class="est">Soluk çubuklar</span> 65+ alt bantları tahmin (IPF).</p>`;
    return s;
}

// ---------- right table ----------
function tableRows() {
    if (state.level === "district" && state.bundle) return unitRows();
    return state.features.map((f) => ({ id: f.properties.area_id, name: f.properties.name_tr, has: hasData(f) ? "var" : "—" }));
}
function drawTable() {
    const cols = state.level === "district" && state.bundle ? COLS.district : COLS.generic;
    let rows = tableRows();
    const q = state.filter.trim().toLocaleLowerCase("tr"); if (q) rows = rows.filter((r) => r.name.toLocaleLowerCase("tr").includes(q));
    const { key, dir } = state.sort;
    if (key) rows.sort((a, b) => { const x = a[key], y = b[key]; if (x == null) return 1; if (y == null) return -1; return (typeof x === "string" ? x.localeCompare(y, "tr") : x - y) * dir; });
    const t = $("#table");
    t.innerHTML = `<thead><tr>${cols.map((c) => `<th data-key="${c.key}" class="${key === c.key ? "on" : ""}">${c.label}${key === c.key ? `<span class="arr">${dir > 0 ? "▲" : "▼"}</span>` : ""}</th>`).join("")}</tr></thead>` +
        `<tbody>${rows.map((r) => `<tr data-id="${r.id}" class="${state.selected === r.id ? "sel" : ""}">${cols.map((c) => { const v = r[c.key]; const txt = c.text ? (v ?? "—") : c.f(v); return `<td class="${v == null ? "dim" : ""}">${c.key === "kindTr" ? `<span class="chip" style="background:${KIND_COLOR[r.kind]}">${txt}</span>` : txt}</td>`; }).join("")}</tr>`).join("")}</tbody>`;
    t.querySelectorAll("th").forEach((th) => th.onclick = () => { const k = th.dataset.key; state.sort = { key: k, dir: state.sort.key === k ? -state.sort.dir : (cols.find((c) => c.key === k).text ? 1 : -1) }; drawTable(); });
    t.querySelectorAll("tbody tr").forEach((tr) => {
        tr.onclick = () => { const id = tr.dataset.id; if (state.level === "district") { state.selected = state.selected === id ? null : id; drawMap(); drawLeft(); drawTable(); } else { const f = state.features.find((x) => x.properties.area_id === id); if (f) onAreaClick(f); } };
        tr.onmouseenter = () => svg.querySelector(`[data-id="${tr.dataset.id}"]`)?.classList.add("hl");
        tr.onmouseleave = () => svg.querySelector(`[data-id="${tr.dataset.id}"]`)?.classList.remove("hl");
    });
    $("#table-title").textContent = state.level === "district" ? "Yerleşimler" : state.level === "province" ? "İlçeler" : "İller";
    const b = state.bundle;
    $("#table-foot").textContent = b ? `${rows.length} birim · TÜİK ADNKS ${b.reference_year} (Endeksa aktarımı) · medyan/65+ yalnız yaş dağılımı olan birimlerde` : `${rows.length} alan`;
}
$("#filter").oninput = (e) => { state.filter = e.target.value; drawTable(); };
$("#csv").onclick = () => {
    const cols = state.level === "district" && state.bundle ? COLS.district : COLS.generic; const rows = tableRows();
    const csv = [cols.map((c) => c.label).join(";"), ...rows.map((r) => cols.map((c) => r[c.key] ?? "").join(";"))].join("\n");
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv" })); a.download = `${state.path[state.path.length - 1].name}.csv`; a.click();
};

// ---------- start ----------
(function start() {
    const h = location.hash.slice(1);
    if (/^TR-\d\d-\d\d\d$/.test(h)) goto("district", h, h);
    else if (/^TR-\d\d$/.test(h)) goto("province", h, h);
    else goto("country");
})();
