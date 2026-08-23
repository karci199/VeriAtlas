// District file page (web/district.html). Reads the district bundle written by
// scripts/build_atlas_data.py and the settlement series written by
// scripts/build_district_children.py, and draws: summary cards, age pyramid with a
// comparison-year silhouette, and the settlement map coloured by a chosen variable.
//
// Rules the page follows (user decisions, 2026-08-23):
//   - only district-measured indicators appear; nothing is inherited from the province
//   - cards give a share or a ten-year change, not ranks and not both count and share
//   - "ten years" means the earliest year when the series is shorter
//   - the Toplam / Kent / Kır switch applies to every card that has the split; a card
//     without it says so instead of silently showing the total
"use strict";

const $ = (s) => document.querySelector(s);
const params = new URLSearchParams(location.search);
const DISTRICT = params.get("id") || "TR-16-006";
const fmt = new Intl.NumberFormat("tr-TR");
const pct = (x, d = 1) => (x * 100).toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });
const num = (x, d = 1) => x.toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });
const sum = (a) => a.reduce((s, v) => s + (v || 0), 0);

const state = { year: 2024, scope: "total", mapVar: "pop", data: null, kids: null, geo: null, view: null };

// ---------- derived readings ----------
/** Age bands for a scope and year: {bands, male, female} or null when the split is absent. */
function ages(year, scope) {
    const y = state.data.age_series[String(year)];
    if (!y) return null;
    const key = scope === "total" ? "district" : scope;
    return y[key] || null;
}
const total = (a) => sum(a.male) + sum(a.female);
function bandIndex(bands, lo) { return bands.findIndex((b) => parseInt(b, 10) === lo); }
/** Share of 0-14, 15-64, 65+ and the median age, from five-year bands. */
function ageGroups(a) {
    const tot = total(a);
    const both = a.bands.map((_, i) => (a.male[i] || 0) + (a.female[i] || 0));
    const i15 = bandIndex(a.bands, 15), i65 = bandIndex(a.bands, 65);
    const young = sum(both.slice(0, i15)), old = sum(both.slice(i65));
    // Median: walk the bands; interpolate inside the band that crosses the half.
    let acc = 0, median = null;
    for (let i = 0; i < both.length; i++) {
        if (acc + both[i] >= tot / 2) {
            const lo = parseInt(a.bands[i], 10), width = a.bands[i].includes("+") ? 10 : 5;
            median = lo + width * ((tot / 2 - acc) / both[i]);
            break;
        }
        acc += both[i];
    }
    return { young: young / tot, mid: 1 - (young + old) / tot, old: old / tot, median, tot };
}
/** Population for a scope and year from the long urban/rural series (1935-2025). */
function popOf(year, scope) {
    const row = state.data.series.find((r) => r.year === year);
    if (!row) return null;
    return scope === "total" ? row.urban + row.rural : row[scope];
}
/** Child share (0-17) for a scope and year from the settlement series (2013+; earlier
 *  years carry totals only). */
function childShare(year, scope) {
    const t = state.kids.totals[String(year)];
    if (!t || t.urban.child == null) return null;
    const pick = scope === "total" ? { child: t.urban.child + t.rural.child, adult: t.urban.adult + t.rural.adult } : t[scope];
    return pick.child / (pick.child + pick.adult);
}
/** A settlement's population in a year: the age-split cell or the plain total. */
const unitPop = (cell) => (cell ? (cell.total != null ? cell.total : cell.child + cell.adult) : null);
function tenYearsBack(year, firstYear) { return Math.max(firstYear, year - 10); }
function delta(now, then, kind) {
    if (now == null || then == null || !isFinite(now - then)) return "";
    const d = now - then;
    const cls = d > 0 ? "up" : d < 0 ? "down" : "";
    const arrow = d > 0 ? "▲" : d < 0 ? "▼" : "•";
    if (kind === "pt") return `<span class="${cls}">${arrow} ${num(Math.abs(d) * 100)} puan</span>`;
    if (kind === "n") return `<span class="${cls}">${arrow} ${fmt.format(Math.abs(Math.round(d)))} kişi (%${num(Math.abs(d / then) * 100)})</span>`;
    return `<span class="${cls}">${arrow} ${num(Math.abs(d))}</span>`;
}

/** A two-decimal delta for small ratios (household size). */
function delta2(now, then) {
    if (now == null || then == null || !isFinite(now - then)) return "";
    const d = now - then, cls = d > 0 ? "up" : d < 0 ? "down" : "";
    return `<span class="${cls}">${d > 0 ? "▲" : d < 0 ? "▼" : "•"} ${num(Math.abs(d), 2)}</span>`;
}
/** "/ N yıl" after a delta — empty when the span is zero or the delta is empty. */
const span = (d, years) => (d && years > 0 ? d + ` <span>/ ${years} yıl</span>` : "");

// ---------- cards ----------
function card(title, value, unit, lines, tag) {
    const v = value == null ? `<div class="v muted">bu kapsamda yok</div>` : `<div class="v">${value}<span class="u">${unit || ""}</span></div>`;
    return `<div class="card"><div class="t">${title}</div>${v}<div class="cmp">${(lines || []).filter(Boolean).join("")}</div>${tag ? `<span class="lvl">${tag}</span>` : ""}</div>`;
}
function drawCards() {
    const { year, scope } = state, d = state.data, c = d.card;
    const scopeTr = { total: "toplam", urban: "kent", rural: "kır" }[scope];
    $("#kind").textContent = `İlçe · ${d.province} · ${year} · ${scopeTr}`;

    const pop = popOf(year, scope);
    const yPop = d.series.filter((r) => r.year <= year - 10).map((r) => r.year).pop(); // latest year at least ten back
    const popThen = yPop != null && year - yPop <= 12 ? popOf(yPop, scope) : null;
    const yThen = tenYearsBack(year, 2007);
    const a = ages(year, scope), aThen = ages(yThen, scope);
    const g = a && ageGroups(a), gThen = aThen && ageGroups(aThen);
    const urbanShare = popOf(year, "urban") / popOf(year, "total");
    const urbanThen = yPop != null && year - yPop <= 12 ? popOf(yPop, "urban") / popOf(yPop, "total") : null;
    const firstKidSplit = state.kids.years.find((y) => state.kids.totals[String(y)].urban.child != null);
    const child = childShare(year, scope), childThen = childShare(tenYearsBack(year, firstKidSplit), scope);

    // Households: TÜİK district mean size (2008+) for the district total; the urban/rural
    // split exists only in Endeksa 2024, from the settlements that report a count.
    const H = state.kids.households || {};
    let hh = null, hhThen = null, hhSpan = 0;
    if (scope === "total") {
        hh = H[String(year)] && H[String(year)].size;
        const firstH = Math.min(...Object.keys(H).filter((y) => H[y].size != null).map(Number));
        const yT = tenYearsBack(year, firstH);
        hhThen = H[String(yT)] && H[String(yT)].size; hhSpan = year - yT;
    } else if (year === 2024) {
        const known = d.units.filter((u) => u.households && (scope === "urban") === u.urban);
        if (known.length) hh = sum(known.map((u) => u.population)) / sum(known.map((u) => u.households));
    }
    const areaKm2 = state.areaKm2;

    $("#cards").innerHTML = [
        card("Nüfus", pop == null ? null : fmt.format(pop), "kişi", [span(delta(pop, popThen, "n"), yPop != null ? year - yPop : 0)]),
        card("Hane başına nüfus", hh == null ? null : num(hh, 2), "kişi", [span(delta2(hh, hhThen), hhSpan)], scope !== "total" && year !== 2024 ? "kent/kır yalnız 2024" : ""),
        card("Yüzölçümü", fmt.format(Math.round(areaKm2)), "km²", [`<span>${num(pop / areaKm2)} kişi/km²</span>`]),
        card("Kentleşme", "%" + pct(urbanShare), "kentte", [span(delta(urbanShare, urbanThen, "pt"), yPop != null ? year - yPop : 0)]),
        card("Çocuk nüfus (0-17)", child == null ? null : "%" + pct(child), "", child == null ? [`<span>0-17 ayrımı ${firstKidSplit}'ten başlıyor</span>`] : [span(delta(child, childThen, "pt"), year - tenYearsBack(year, firstKidSplit))]),
        card("Medyan yaş", g ? num(g.median) : null, "", g ? [span(delta(g.median, gThen && gThen.median, ""), year - yThen)] : []),
        g ? (() => { const rows = [["0-14", g.young, "var(--green)"], ["15-64", g.mid, "var(--blue)"], ["65+", g.old, "var(--amber)"]]; return `<div class="card wide"><div class="t">Yaş grupları</div><div class="ages">
            <div class="labs">${rows.map(([l, v, col]) => `<div class="lab"><i style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${col}"></i> ${l} <b>%${pct(v)}</b></div>`).join("")}</div>
            <div class="bars">${rows.map(([, v, col]) => `<span style="width:${v * 100}%;background:${col}"></span>`).join("")}</div>
          </div></div>`; })() : "",
    ].join("");

    $("#foot").textContent = `${d.units.length} yerleşim · ${d.units.filter((u) => u.urban).length} kentsel mahalle · ${d.units.filter((u) => !u.urban).length} köy · Endeksa 2024 kent tanımı`;
}

// ---------- pyramid ----------
function drawPyramid() {
    const { year, scope } = state;
    const a = ages(year, scope);
    const box = $("#pyr");
    if (!a) { box.innerHTML = `<div class="src">${year} için bu kapsamda yaş dağılımı yok.</div>`; $("#pyrFoot").textContent = ""; return; }
    const max = Math.max(...a.male, ...a.female, 1);
    const w = (v) => (100 * (v || 0)) / max;
    box.innerHTML = [...a.bands.keys()].reverse().map((i) => `
        <div class="l"><div class="bar" style="width:${w(a.male[i])}%;background:var(--blue)" title="${a.bands[i]} erkek ${fmt.format(a.male[i])}"></div></div>
        <div class="lab">${a.bands[i]}</div>
        <div class="r"><div class="bar" style="width:${w(a.female[i])}%;background:var(--acc)" title="${a.bands[i]} kadın ${fmt.format(a.female[i])}"></div></div>`).join("");
    $("#pyrFoot").innerHTML = `<span>◀ Erkek ${fmt.format(sum(a.male))}</span><span>Kadın ${fmt.format(sum(a.female))} ▶</span>`;
    $("#pyrSrc").textContent = `ADNKS ${year} · ${{ total: "toplam", urban: "kent", rural: "kır" }[scope]}`;
}

// ---------- social / vital ----------
function drawSocial() {
    const m = state.data.marital;
    const key = state.scope === "total" ? "district" : state.scope;
    const t = m[key] && (m[key].total || m[key]);
    const cols = [["never", "Hiç evlenmedi", "var(--blue)"], ["married", "Evli", "var(--green)"], ["divorced", "Boşandı", "var(--amber)"], ["widowed", "Eşi öldü", "#6b7280"]];
    if (!t || !cols.every(([k]) => t[k] != null)) { $("#social").innerHTML = card("Medeni hal (15+)", null); return; }
    const tot = sum(cols.map(([k]) => t[k]));
    $("#social").innerHTML = `<div class="card wide"><div class="t">Medeni hal (15+)${state.year !== 2024 ? " · yalnız 2024" : ""}</div>
        <div class="strip">${cols.map(([k, , c]) => `<span style="width:${(100 * t[k]) / tot}%;background:${c}"></span>`).join("")}</div>
        <div class="keys">${cols.map(([k, l, c]) => `<span><i style="background:${c}"></i>${l} <b>%${pct(t[k] / tot)}</b></span>`).join("")}</div></div>`;
}
function drawVital() {
    const v = state.kids.vital, y = state.year;
    const pop = popOf(y, "total");
    const rate = (k, yy) => v[String(yy)] && v[String(yy)][k] != null && popOf(yy, "total") ? (1000 * v[String(yy)][k]) / popOf(yy, "total") : null;
    const years = Object.keys(v).map(Number);
    const firstB = Math.min(...years.filter((yy) => v[yy].births != null)), firstD = Math.min(...years.filter((yy) => v[yy].deaths != null));
    const b = rate("births", y), bThen = rate("births", tenYearsBack(y, firstB));
    const d = rate("deaths", y), dThen = rate("deaths", tenYearsBack(y, firstD));
    $("#vital").innerHTML = [
        card("Kaba doğum hızı", b == null ? null : "‰ " + num(b), "", b == null ? [`<span>ilçe doğumları ${firstB}'ten başlıyor</span>`] : [span(delta(b, bThen, ""), y - tenYearsBack(y, firstB))], "ilçe toplamı"),
        card("Kaba ölüm hızı", d == null ? null : "‰ " + num(d), "", d == null ? [`<span>ilçe ölümleri ${firstD}'dan başlıyor</span>`] : [span(delta(d, dThen, ""), y - tenYearsBack(y, firstD))], "ilçe toplamı"),
        card("Doğal artış", b != null && d != null ? "‰ " + num(b - d) : null, "", [`<span>doğum − ölüm, bin kişiye</span>`], "ilçe toplamı"),
    ].join("");
}

// ---------- settlements table & map ----------
function unitValue(u, varName) {
    const s = u.series, y = String(state.year), yt = String(state.year - 10);
    const now = s[y];
    if (!now) return null;
    const tot = unitPop(now);
    if (varName === "pop") return tot;
    if (varName === "child") return tot && now.child != null ? now.child / tot : null;
    if (varName === "change") { const then = unitPop(s[yt]); return then ? tot / then - 1 : null; }
    return null;
}
function drawUnits() {
    const y = String(state.year);
    const rows = state.kids.units.filter((u) => state.scope === "total" || (state.scope === "urban") === u.urban)
        .sort((a, b) => a.name.localeCompare(b.name, "tr"));
    $("#units").innerHTML = `<tr><th>Yerleşim</th><th>Tür</th><th>Nüfus ${y}</th><th>0-17</th><th>10 yıl</th></tr>` + rows.map((u) => {
        const s = u.series[y];
        if (!s) return `<tr data-id="${u.id}"><td>${u.name}</td><td>${u.urban ? "mahalle" : "köy"}</td><td colspan="3" style="color:var(--mute)">${y} yok</td></tr>`;
        const tot = unitPop(s), ch = unitValue(u, "change");
        return `<tr data-id="${u.id}"><td>${u.name}${u.former ? ` <small style="color:var(--mute)">(eski: ${u.former.join(", ")})</small>` : ""}</td><td>${u.urban ? "mahalle" : "köy"}</td><td>${fmt.format(tot)}</td><td>${s.child == null ? "—" : "%" + pct(s.child / tot, 0)}</td><td>${ch == null ? "—" : (ch >= 0 ? "+" : "−") + pct(Math.abs(ch), 0) + "%"}</td></tr>`;
    }).join("");
}

/** Area of the settlement polygons, km², on a locally-scaled flat projection. */
function areaKm2Of(features) {
    let total = 0;
    for (const f of features) {
        const rings = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
        for (const poly of rings) poly.forEach((ring, idx) => {
            const lat0 = (ring[0][1] * Math.PI) / 180, kx = 111.32 * Math.cos(lat0), ky = 110.57;
            let a = 0;
            for (let i = 0; i < ring.length - 1; i++) a += (ring[i][0] * kx) * (ring[i + 1][1] * ky) - (ring[i + 1][0] * kx) * (ring[i][1] * ky);
            total += (idx === 0 ? 1 : -1) * Math.abs(a) / 2;
        });
    }
    return total;
}
let proj = null;
function projection(features, W, aspect) {
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    const walk = (g) => (g.type === "Polygon" ? g.coordinates : g.coordinates.flat()).forEach((r) => r.forEach(([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }));
    features.forEach((f) => walk(f.geometry));
    const k = Math.cos(((y0 + y1) / 2) * Math.PI / 180); // shrink longitude to keep shape
    const s = (W * 0.96) / Math.max((x1 - x0) * k, 1e-9), H = (y1 - y0) * s + W * 0.04;
    // Fit inside W × W/aspect (the frame), centred.
    const Hf = W / aspect, s2 = Math.min(s, (Hf * 0.96) / Math.max(y1 - y0, 1e-9));
    const dw = (x1 - x0) * k * s2, dh = (y1 - y0) * s2;
    return { W, H: Hf, s: s2, x0, y1, k, ox: (W - dw) / 2, oy: (Hf - dh) / 2 };
}
function pathOf(g) {
    const rings = g.type === "Polygon" ? g.coordinates : g.coordinates.flat();
    return rings.map((r) => "M" + r.map(([x, y]) => `${(proj.ox + (x - proj.x0) * proj.k * proj.s).toFixed(1)} ${(proj.oy + (proj.y1 - y) * proj.s).toFixed(1)}`).join("L") + "Z").join("");
}
function colour(t) { return `hsl(212 62% ${(24 + 40 * t).toFixed(0)}%)`; }
function drawMap() {
    const svg = $("#map"), feats = state.geo.features;
    const byMedas = new Map();
    state.kids.units.forEach((u) => u.medas.forEach((m) => byMedas.set(m, u)));
    const vals = feats.map((f) => { const u = byMedas.get(f.properties.area_id); return u ? unitValue(u, state.mapVar) : null; });
    const present = vals.filter((v) => v != null);
    const lo = Math.min(...present), hi = Math.max(...present);
    const t = (v) => (hi > lo ? (v - lo) / (hi - lo) : 0.5);
    const fmtVar = { pop: (v) => fmt.format(v), child: (v) => "%" + pct(v, 0), change: (v) => (v >= 0 ? "+" : "−") + pct(Math.abs(v), 0) + "%" }[state.mapVar];
    svg.innerHTML = feats.map((f, i) => {
        const u = byMedas.get(f.properties.area_id), v = vals[i];
        const hidden = state.scope !== "total" && u && (state.scope === "urban") !== u.urban;
        return `<path d="${pathOf(f.geometry)}" fill="${v == null || hidden ? "#1a1c20" : colour(t(v))}" data-id="${u ? u.id : ""}" data-tip="${f.properties.name_tr}${v == null ? "" : " · " + fmtVar(v)}"></path>`;
    }).join("");
    $("#legMin").textContent = present.length ? fmtVar(lo) : "—";
    $("#legMax").textContent = present.length ? fmtVar(hi) : "—";
    const d = state.data, nU = d.units.filter((u) => u.urban).length;
    $("#mapTitle").textContent = `${d.name} · ${feats.length} yerleşim (${nU} mahalle, ${feats.length - nU} köy) · ${state.year}`;
    const note = $(".mapnote"); if (note) note.remove();
    if (!present.length) $(".mapwrap").insertAdjacentHTML("beforeend", `<div class="mapnote">${state.year} için bu değişken yok</div>`);
}

// Pan / zoom: the viewBox is the camera. Wheel zooms about the pointer, drag pans,
// double-click or "0" refits, "+"/"-" step. Paths are never rebuilt for this.
function setView(v) {
    // Clamp so the drawing never leaves the frame entirely: at least a third stays visible.
    const m = 0.66;
    v.x = Math.min(Math.max(v.x, -v.w * m), proj.W - v.w * (1 - m));
    v.y = Math.min(Math.max(v.y, -v.h * m), proj.H - v.h * (1 - m));
    state.view = v; $("#map").setAttribute("viewBox", `${v.x} ${v.y} ${v.w} ${v.h}`);
}
function fitMap() { setView({ x: 0, y: 0, w: proj.W, h: proj.H }); }
function zoomAt(factor, px, py) {
    const v = state.view, svg = $("#map"), r = svg.getBoundingClientRect();
    const fx = (px - r.left) / r.width, fy = (py - r.top) / r.height;
    const w = Math.min(Math.max(v.w / factor, proj.W / 40), proj.W * 3), h = w * (v.h / v.w);
    setView({ x: v.x + fx * (v.w - w), y: v.y + fy * (v.h - h), w, h });
}
function wireMap() {
    const svg = $("#map");
    let drag = null;
    svg.addEventListener("wheel", (e) => { e.preventDefault(); zoomAt(e.deltaY < 0 ? 1.25 : 0.8, e.clientX, e.clientY); }, { passive: false });
    // No pointer capture: the press is remembered, the window follows the drag, and a
    // press that did not move is a click on the shape it started on.
    svg.addEventListener("pointerdown", (e) => { if (e.button !== 0) return; drag = { x: e.clientX, y: e.clientY, v: { ...state.view }, moved: false, path: e.target.closest("path") }; e.preventDefault(); });
    window.addEventListener("pointermove", (e) => {
        if (!drag) return;
        const r = svg.getBoundingClientRect(), k = drag.v.w / r.width;
        const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
        if (!drag.moved && Math.abs(dx) + Math.abs(dy) > 4) { drag.moved = true; svg.classList.add("drag"); }
        if (drag.moved) setView({ ...drag.v, x: drag.v.x - dx * k, y: drag.v.y - dy * k });
    });
    window.addEventListener("pointerup", () => {
        if (!drag) return;
        const p = drag.path;
        if (!drag.moved && p && p.dataset.id) highlight(p.dataset.id);
        drag = null; svg.classList.remove("drag");
    });
    svg.addEventListener("pointermove", (e) => {
        if (drag) return;
        const p = e.target.closest("path"), id = p && p.dataset.id;
        if (id === state.hover) return;
        state.hover = id || null;
        if (id) showPick(id, id === state.pinned); else if (state.pinned) showPick(state.pinned, true); else $("#pick").hidden = true;
    });
    svg.addEventListener("pointerleave", () => { state.hover = null; if (state.pinned) showPick(state.pinned, true); else $("#pick").hidden = true; });
    svg.addEventListener("dblclick", fitMap);
    svg.addEventListener("keydown", (e) => {
        const r = svg.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        if (e.key === "+" || e.key === "=") zoomAt(1.25, cx, cy); else if (e.key === "-") zoomAt(0.8, cx, cy); else if (e.key === "0") fitMap(); else return;
        e.preventDefault();
    });
}

/** The card over the map: hover previews a settlement, click pins it. */
function showPick(id, pinned) {
    const pick = $("#pick"), u = state.kids.units.find((x) => x.id === id);
    if (!u) { pick.hidden = true; return; }
    const y = u.series[String(state.year)], tot = unitPop(y), ch = unitValue(u, "change");
    pick.hidden = false; pick.classList.toggle("pinned", !!pinned);
    const former = u.former && u.former.length ? ` · eski adı ${u.former.join(", ")}` : "";
    pick.innerHTML = `<b>${u.name}</b><small>${u.urban ? "mahalle" : "köy"}${former} · ${state.year}${pinned ? "" : " · tıkla: sabitle"}</small>` + (y
        ? `<div class="row"><span>nüfus <i>${fmt.format(tot)}</i></span>${y.child == null ? "" : `<span>0-17 <i>%${pct(y.child / tot, 0)}</i></span>`}${ch == null ? "" : `<span>nüfus, 10 yıl <i>${(ch >= 0 ? "+" : "−") + pct(Math.abs(ch), 0)}%</i></span>`}</div>`
        : `<div class="row"><span>bu yıl için veri yok</span></div>`);
}

// ---------- views: the sidebar swaps the panel; the map stays ----------
function showView(name) {
    document.querySelectorAll(".view").forEach((v) => (v.hidden = v.dataset.view !== name));
    document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.view === name && !a.dataset.to));
    $(".panel").scrollTop = 0;
}
function wireViews() {
    $("#nav").addEventListener("click", (e) => {
        const a = e.target.closest("a[data-view]"); if (!a) return; e.preventDefault();
        history.replaceState(null, "", a.getAttribute("href"));
        showView(a.dataset.view);
        if (a.dataset.to) { const t = document.getElementById(a.dataset.to); if (t) t.scrollIntoView({ block: "start" }); }
        document.querySelectorAll("#nav a").forEach((x) => x.classList.toggle("on", x === a));
    });
    const [view, to] = location.hash.slice(1).split("/");
    if (view && document.querySelector(`.view[data-view="${view}"]`)) { showView(view); const t = to && document.getElementById(to); if (t) t.scrollIntoView(); }
}
function drawAgeDetail() {
    const { year, scope } = state, a = ages(year, scope);
    if (!a) { $("#ageDetail").innerHTML = ""; return; }
    const tot = total(a), males = sum(a.male), g = ageGroups(a);
    const i15 = bandIndex(a.bands, 15), i65 = bandIndex(a.bands, 65);
    const both = a.bands.map((_, i) => a.male[i] + a.female[i]);
    const dep = (sum(both.slice(0, i15)) + sum(both.slice(i65))) / sum(both.slice(i15, i65));
    $("#ageDetail").innerHTML = [
        card("Kadın oranı", "%" + pct((tot - males) / tot), "", [`<span>${fmt.format(tot - males)} kadın · ${fmt.format(males)} erkek</span>`]),
        card("Yaşlı oranı (65+)", "%" + pct(g.old), "", []),
        card("Bağımlılık oranı", "%" + pct(dep), "", [`<span>(0-14 + 65+) / 15-64</span>`]),
        `<div class="card wide"><div class="t">Yaş grupları · ${year}</div><table class="units">${a.bands.map((b, i) => `<tr><td>${b}</td><td>${fmt.format(a.male[i])}</td><td>${fmt.format(a.female[i])}</td><td>${fmt.format(both[i])}</td><td>%${pct(both[i] / tot)}</td></tr>`).join("")}</table></div>`,
    ].join("");
}

// ---------- crumb, search ----------
function drawCrumb() {
    const d = state.data;
    $("#crumb").innerHTML = `<a href="atlas.html">Türkiye</a><span class="sep">›</span><a href="atlas.html">${d.region}</a><span class="sep">›</span><a href="atlas.html">${d.province}</a><span class="sep">›</span><span class="cur">${d.name} <span class="lvl">ilçe</span></span>`;
    document.title = `VeriAtlas — ${d.name}`;
}
function search(q) {
    const box = $("#hits");
    q = q.trim().toLocaleLowerCase("tr");
    if (!q) { box.innerHTML = ""; return; }
    const hits = state.kids.units.filter((u) => u.name.toLocaleLowerCase("tr").includes(q)).slice(0, 8);
    box.innerHTML = hits.map((u) => `<div data-id="${u.id}"><span>${u.name}</span><small>${u.urban ? "mahalle" : "köy"} · ${state.data.name}</small></div>`).join("") || `<div><small>bulunamadı</small></div>`;
}
function highlight(id) {
    document.querySelectorAll("#map path").forEach((p) => p.classList.toggle("hit", p.dataset.id === id));
    const row = document.querySelector(`#units tr[data-id="${id}"]`);
    if (row) { row.style.outline = "1px solid var(--amber)"; setTimeout(() => (row.style.outline = ""), 1500); }
    state.pinned = id;
    showPick(id, true);
}

// ---------- wiring ----------
function render() { drawCards(); drawPyramid(); drawAgeDetail(); drawSocial(); drawVital(); drawUnits(); drawMap(); }
async function main() {
    const [data, kids, geo] = await Promise.all([
        fetch(`../public/atlas/${DISTRICT}.json`).then((r) => r.json()),
        fetch(`../public/atlas/${DISTRICT}.children.json`).then((r) => r.json()),
        fetch(`../public/geo/neighbourhoods/${DISTRICT}.geojson`).then((r) => r.json()),
    ]);
    state.data = data; state.kids = kids; state.geo = geo;
    $("#name").textContent = data.name;
    const ys = Object.keys(data.age_series).map(Number);
    $("#year").min = Math.min(...ys); $("#year").max = Math.max(...ys);
    state.areaKm2 = areaKm2Of(geo.features);
    const box = $("#map").getBoundingClientRect();
    const aspect = box.width > 0 && box.height > 0 ? box.width / box.height : 1.2;
    proj = projection(geo.features, 600, Math.max(aspect, 0.5));
    fitMap(); wireMap(); wireViews();
    drawCrumb(); render();

    let raf = 0;
    $("#year").addEventListener("input", (e) => { state.year = +e.target.value; $("#yearLabel").textContent = state.year; cancelAnimationFrame(raf); raf = requestAnimationFrame(render); });
    $("#scope").addEventListener("click", (e) => { const s = e.target.closest("span[data-v]"); if (!s) return; state.scope = s.dataset.v; document.querySelectorAll("#scope span").forEach((x) => x.classList.toggle("on", x === s)); render(); });
    $("#mapVar").addEventListener("change", (e) => { state.mapVar = e.target.value; drawMap(); });
    $("#mapToggle").addEventListener("click", (e) => { $("main").classList.toggle("nomap"); e.target.classList.toggle("on"); });
    $("#units").addEventListener("click", (e) => { const r = e.target.closest("tr[data-id]"); if (r) highlight(r.dataset.id); });
    $("#q").addEventListener("input", (e) => search(e.target.value));
    $("#hits").addEventListener("mousedown", (e) => { const h = e.target.closest("div[data-id]"); if (h) { highlight(h.dataset.id); $("#q").value = ""; $("#hits").innerHTML = ""; } });
}
main().catch((err) => { $("#name").textContent = "Veri yüklenemedi"; $("#kind").textContent = err.message; });
