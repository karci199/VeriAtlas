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

const state = { year: 2024, scope: "total", cmp: "2007", mapVar: "pop", data: null, kids: null, geo: null };

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
/** Child share (0-17) for a scope and year from the settlement series (2013+). */
function childShare(year, scope) {
    const t = state.kids.totals[String(year)];
    if (!t) return null;
    const pick = scope === "total" ? { child: t.urban.child + t.rural.child, adult: t.urban.adult + t.rural.adult } : t[scope];
    return pick.child / (pick.child + pick.adult);
}
function tenYearsBack(year, firstYear) { return Math.max(firstYear, year - 10); }
function delta(now, then, kind) {
    if (now == null || then == null) return "";
    const d = now - then;
    const cls = d > 0 ? "up" : d < 0 ? "down" : "";
    const arrow = d > 0 ? "▲" : d < 0 ? "▼" : "•";
    if (kind === "pt") return `<span class="${cls}">${arrow} ${num(Math.abs(d) * 100)} puan</span>`;
    if (kind === "n") return `<span class="${cls}">${arrow} ${fmt.format(Math.abs(Math.round(d)))} kişi (%${num(Math.abs(d / then) * 100)})</span>`;
    return `<span class="${cls}">${arrow} ${num(Math.abs(d))}</span>`;
}

// ---------- cards ----------
function card(title, value, unit, lines, tag) {
    const v = value == null ? `<div class="v muted">bu kapsamda yok</div>` : `<div class="v">${value}<span class="u">${unit || ""}</span></div>`;
    return `<div class="card"><div class="t">${title}</div>${v}<div class="cmp">${(lines || []).filter(Boolean).join("")}</div>${tag ? `<span class="lvl">${tag}</span>` : ""}</div>`;
}
function drawCards() {
    const { year, scope } = state, d = state.data, c = d.card;
    const scopeTr = { total: "toplam", urban: "kent", rural: "kır" }[scope];
    $("#kind").textContent = `İlçe · ${d.province} · ${year} · ${scopeTr}`;

    const firstPop = d.series[0].year;
    const pop = popOf(year, scope), popThen = popOf(tenYearsBack(year, firstPop), scope);
    const yThen = tenYearsBack(year, 2007);
    const a = ages(year, scope), aThen = ages(yThen, scope);
    const g = a && ageGroups(a), gThen = aThen && ageGroups(aThen);
    const urbanShare = popOf(year, "urban") / popOf(year, "total");
    const urbanThen = popOf(tenYearsBack(year, firstPop), "urban") / popOf(tenYearsBack(year, firstPop), "total");
    const firstKid = state.kids.years[0];
    const child = childShare(year, scope), childThen = childShare(tenYearsBack(year, firstKid), scope);

    // Households: Endeksa 2024 only, and only where every settlement reports a count.
    let hh = null, hhNote = "";
    if (year === 2024) {
        const units = d.units.filter((u) => scope === "total" || (scope === "urban") === u.urban);
        const known = units.filter((u) => u.households);
        if (known.length === units.length) hh = sum(units.map((u) => u.population)) / sum(units.map((u) => u.households));
        else if (scope !== "rural" && known.length) { hh = sum(known.map((u) => u.population)) / sum(known.map((u) => u.households)); hhNote = `${units.length - known.length} yerleşimde hane sayısı yok`; }
    }

    $("#cards").innerHTML = [
        card("Nüfus", pop == null ? null : fmt.format(pop), "kişi", [delta(pop, popThen, "n") + ` <span>/ ${year - tenYearsBack(year, firstPop)} yıl</span>`]),
        card("Hane başına nüfus", hh == null ? null : num(hh, 2), "kişi", [hhNote ? `<span>${hhNote}</span>` : "", `<span>Endeksa 2024${year !== 2024 ? " · yalnız 2024" : ""}</span>`], year !== 2024 ? "yalnız 2024" : ""),
        card("Yüzölçümü", fmt.format(c.area_km2), "km²", [`<span>${num(pop / c.area_km2)} kişi/km²</span>`, `<span>${c.area_note || ""}</span>`]),
        card("Kentleşme", "%" + pct(urbanShare), "kentte", [delta(urbanShare, urbanThen, "pt") + ` <span>/ ${year - tenYearsBack(year, firstPop)} yıl</span>`, `<span>${fmt.format(popOf(year, "urban"))} kent · ${fmt.format(popOf(year, "rural"))} kır</span>`], "kapsamdan bağımsız"),
        card("Çocuk nüfus (0-17)", child == null ? null : "%" + pct(child), "", child == null ? [`<span>mahalle verisi ${firstKid}'ten başlıyor</span>`] : [delta(child, childThen, "pt") + ` <span>/ ${year - tenYearsBack(year, firstKid)} yıl</span>`]),
        card("Medyan yaş", g ? num(g.median) : null, "", g ? [delta(g.median, gThen && gThen.median, "") + ` <span>/ ${year - yThen} yıl</span>`] : []),
        g ? `<div class="card wide"><div class="t">Yaş grupları</div><div class="ages">
            ${[["0-14", g.young, "var(--green)"], ["15-64", g.mid, "var(--blue)"], ["65+", g.old, "var(--amber)"]].map(([l, v, col]) =>
                `<div style="width:${v * 100}%"><div class="lab"><i style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${col}"></i> ${l} <b>%${pct(v)}</b></div><div class="bar" style="background:${col}"></div></div>`).join("")}
          </div><div class="keys">${gThen ? `<span>${yThen}: ${pct(gThen.young, 0)} · ${pct(gThen.mid, 0)} · ${pct(gThen.old, 0)}</span>` : ""}${a.estimate_from_band != null && scope !== "total" ? `<span>kent/kır yaş dağılımı: 65+ üstü bantlar tahmin</span>` : ""}</div></div>` : "",
    ].join("");

    $("#foot").textContent = `${d.units.length} yerleşim (${d.units.filter((u) => u.urban).length} kentsel mahalle, ${d.units.filter((u) => !u.urban).length} kır) · ayrıntı: Yerleşimler`;
}

// ---------- pyramid ----------
function drawPyramid() {
    const { year, scope } = state;
    const a = ages(year, scope);
    const box = $("#pyr");
    if (!a) { box.innerHTML = `<div class="src">Bu kapsamda ${year} için yaş dağılımı yok.</div>`; $("#pyrFoot").textContent = ""; return; }
    const cmpYear = state.cmp === "" ? null : state.cmp === "-10" ? tenYearsBack(year, 2007) : parseInt(state.cmp, 10);
    const b = cmpYear != null && cmpYear !== year ? ages(cmpYear, scope) : null;
    const max = Math.max(...a.male, ...a.female, ...(b ? [...b.male, ...b.female] : [1]));
    const w = (v) => (100 * (v || 0)) / max;
    box.innerHTML = [...a.bands.keys()].reverse().map((i) => `
        <div class="l">${b ? `<div class="bar" style="width:${w(b.male[i])}%;background:#2e323a;position:absolute;right:0"></div>` : ""}<div class="bar" style="width:${w(a.male[i])}%;background:var(--blue);position:relative" title="${a.bands[i]} erkek ${fmt.format(a.male[i])}"></div></div>
        <div class="lab">${a.bands[i]}</div>
        <div class="r">${b ? `<div class="bar" style="width:${w(b.female[i])}%;background:#2e323a;position:absolute;left:0"></div>` : ""}<div class="bar" style="width:${w(a.female[i])}%;background:var(--acc);position:relative" title="${a.bands[i]} kadın ${fmt.format(a.female[i])}"></div></div>`).join("");
    $("#pyrFoot").innerHTML = `<span>◀ Erkek ${fmt.format(sum(a.male))}</span><span>${b ? `gri: ${cmpYear} · ${fmt.format(total(b))} kişi` : ""}</span><span>Kadın ${fmt.format(sum(a.female))} ▶</span>`;
    $("#pyrSrc").textContent = `ADNKS ${year} · 5 yaş grubu · ${{ total: "ilçe toplamı", urban: "kent", rural: "kır" }[scope]}${scope !== "total" ? " (kent/kır yaş dağılımı Endeksa 2024 paylarından tahmin; 2024 ölçüm)" : ""}`;
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
        card("Kaba doğum hızı", b == null ? null : "‰ " + num(b), "", b == null ? [`<span>ilçe doğumları ${firstB}'ten başlıyor</span>`] : [delta(b, bThen, "") + ` <span>‰ / ${y - tenYearsBack(y, firstB)} yıl</span>`], "ilçe toplamı"),
        card("Kaba ölüm hızı", d == null ? null : "‰ " + num(d), "", d == null ? [`<span>ilçe ölümleri ${firstD}'dan başlıyor</span>`] : [delta(d, dThen, "") + ` <span>‰ / ${y - tenYearsBack(y, firstD)} yıl</span>`], "ilçe toplamı"),
        card("Doğal artış", b != null && d != null ? "‰ " + num(b - d) : null, "", [`<span>doğum − ölüm, bin kişiye</span>`], "ilçe toplamı"),
    ].join("");
}

// ---------- settlements table & map ----------
function unitValue(u, varName) {
    const s = u.series, y = String(state.year), yt = String(tenYearsBack(state.year, state.kids.years[0]));
    const now = s[y];
    if (!now) return null;
    const tot = now.child + now.adult;
    if (varName === "pop") return tot;
    if (varName === "child") return tot ? now.child / tot : null;
    if (varName === "female") return tot ? now.female / tot : null;
    if (varName === "change") { const then = s[yt]; return then && then.child + then.adult ? tot / (then.child + then.adult) - 1 : null; }
    return null;
}
function drawUnits() {
    const y = String(state.year);
    const rows = state.kids.units.filter((u) => state.scope === "total" || (state.scope === "urban") === u.urban)
        .sort((a, b) => a.name.localeCompare(b.name, "tr"));
    $("#units").innerHTML = `<tr><th>Yerleşim</th><th>Tür</th><th>Nüfus ${y}</th><th>0-17</th><th>Kadın</th><th>10 yıl</th></tr>` + rows.map((u) => {
        const s = u.series[y];
        if (!s) return `<tr data-id="${u.id}"><td>${u.name}</td><td>${u.urban ? "mahalle" : "köy"}</td><td colspan="4" style="color:var(--mute)">${y} yok</td></tr>`;
        const tot = s.child + s.adult, ch = unitValue(u, "change");
        return `<tr data-id="${u.id}"><td>${u.name}</td><td>${u.urban ? "mahalle" : "köy"}</td><td>${fmt.format(tot)}</td><td>%${pct(s.child / tot, 0)}</td><td>%${pct(s.female / tot, 0)}</td><td>${ch == null ? "—" : (ch >= 0 ? "+" : "−") + pct(Math.abs(ch), 0) + "%"}</td></tr>`;
    }).join("");
}

let proj = null;
function projection(features, W) {
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    const walk = (g) => (g.type === "Polygon" ? g.coordinates : g.coordinates.flat()).forEach((r) => r.forEach(([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }));
    features.forEach((f) => walk(f.geometry));
    const k = Math.cos(((y0 + y1) / 2) * Math.PI / 180); // shrink longitude to keep shape
    const s = (W * 0.96) / Math.max((x1 - x0) * k, 1e-9), H = (y1 - y0) * s + W * 0.04;
    return { W, H: Math.min(H, W * 1.1), s, x0, y1, k, ox: W * 0.02, oy: W * 0.02 };
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
    const fmtVar = { pop: (v) => fmt.format(v), child: (v) => "%" + pct(v, 0), female: (v) => "%" + pct(v, 0), change: (v) => (v >= 0 ? "+" : "−") + pct(Math.abs(v), 0) + "%" }[state.mapVar];
    svg.innerHTML = feats.map((f, i) => {
        const u = byMedas.get(f.properties.area_id), v = vals[i];
        const hidden = state.scope !== "total" && u && (state.scope === "urban") !== u.urban;
        return `<path d="${pathOf(f.geometry)}" fill="${v == null || hidden ? "#1a1c20" : colour(t(v))}" data-id="${u ? u.id : ""}" data-tip="${f.properties.name_tr}${v == null ? "" : " · " + fmtVar(v)}"></path>`;
    }).join("");
    $("#legMin").textContent = present.length ? fmtVar(lo) : "—";
    $("#legMax").textContent = present.length ? fmtVar(hi) : "—";
    $("#mapTitle").textContent = `${state.data.name} yerleşimleri · ${feats.length} birim · ${state.year}`;
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
    if (row) { row.scrollIntoView({ block: "center", behavior: "smooth" }); row.style.outline = "1px solid var(--blue)"; setTimeout(() => (row.style.outline = ""), 1500); }
}

// ---------- wiring ----------
function render() { drawCards(); drawPyramid(); drawSocial(); drawVital(); drawUnits(); drawMap(); }
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
    $("#sources").textContent = "Kaynaklar: " + data.sources.join(" · ") + " · TÜİK ilçe doğum ve ölüm sayıları.";
    proj = projection(geo.features, 600);
    $("#map").setAttribute("viewBox", `0 0 ${proj.W} ${proj.H}`);
    drawCrumb(); render();

    $("#year").addEventListener("input", (e) => { state.year = +e.target.value; $("#yearLabel").textContent = state.year; render(); });
    $("#scope").addEventListener("click", (e) => { const s = e.target.closest("span[data-v]"); if (!s) return; state.scope = s.dataset.v; document.querySelectorAll("#scope span").forEach((x) => x.classList.toggle("on", x === s)); render(); });
    $("#cmp").addEventListener("change", (e) => { state.cmp = e.target.value; drawPyramid(); });
    $("#mapVar").addEventListener("change", (e) => { state.mapVar = e.target.value; drawMap(); });
    $("#mapToggle").addEventListener("click", (e) => { $("main").classList.toggle("nomap"); e.target.classList.toggle("on"); });
    $("#map").addEventListener("mousemove", (e) => { const p = e.target.closest("path"); $("#tip").textContent = p ? p.dataset.tip : ""; });
    $("#map").addEventListener("click", (e) => { const p = e.target.closest("path"); if (p && p.dataset.id) highlight(p.dataset.id); });
    $("#units").addEventListener("click", (e) => { const r = e.target.closest("tr[data-id]"); if (r) highlight(r.dataset.id); });
    $("#q").addEventListener("input", (e) => search(e.target.value));
    $("#hits").addEventListener("mousedown", (e) => { const h = e.target.closest("div[data-id]"); if (h) { highlight(h.dataset.id); $("#q").value = ""; $("#hits").innerHTML = ""; } });
}
main().catch((err) => { $("#name").textContent = "Veri yüklenemedi"; $("#kind").textContent = err.message; });
