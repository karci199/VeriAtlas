/* Election map: one number per place, painted on its own boundary.
 *
 * Pick an election, an indicator (a party or candidate, or turnout / valid-over-registered /
 * invalid share), a scope (whole place, urban, rural, rural minus urban) and a level
 * (district or province). Everything is read from public/elections/kentkir/<code>.json,
 * which scripts/build_kentkir_secim.py builds from the tiles and the user's decisions, so
 * nothing here needs regenerating when the question changes.
 *
 * Urban / rural exist only for provinces whose every unit has a decision (index.json lists
 * them). Elsewhere the scope shows "kapsam dışı" instead of guessing.
 */

"use strict";

const BASE = "../public/elections/kentkir/";
const PROVINCE_GEO = "../public/areas.geojson";
const DISTRICT_GEO = (id) => `../public/geo/districts/${id}.geojson`;
const SVGNS = "http://www.w3.org/2000/svg";
const $ = (s) => document.querySelector(s);

const STATS = [
  { key: "_turnout", label: "Katılım (kullanılan / kayıtlı)", value: (b) => (b.k ? (b.o / b.k) * 100 : null) },
  { key: "_valid", label: "Geçerli / kayıtlı", value: (b) => (b.k ? (b.g / b.k) * 100 : null) },
  { key: "_invalid", label: "Geçersiz oy payı", value: (b) => (b.o ? ((b.o - b.g) / b.o) * 100 : null) },
];
// Parties and candidates get a recognisable hue; anything else uses the neutral teal.
const HUES = [
  [/AK PARTİ|ERDOĞAN|Evet/, "#f2a43a"],
  [/CHP|KILIÇDAROĞLU|İNCE|İHSANOĞLU|Hayır/, "#e0504a"],
  [/MHP/, "#b5457f"],
  [/İYİ|AKŞENER/, "#45a7d8"],
  [/DEM|HDP|YEŞİL SOL|DEMİRTAŞ/, "#8a5fe0"],
  [/YENİDEN REFAH/, "#d6b32a"],
  [/BÜYÜK BİRLİK/, "#c06a3a"],
  [/SAADET/, "#d97c9a"],
];
const NEUTRAL = "#3aa6a0";
const DIVERGING = ["#2b5c9e", "#4a82c4", "#84aedb", "#bcd3e8", "#e9e6e1", "#efc9b6", "#df9a7c", "#c9674a", "#9b3a2a"];
const DIFF_BREAKS = [-30, -20, -10, -3, 3, 10, 20, 30];

const state = {
  index: null, elections: {}, geo: {}, outlines: null,
  election: "ho2017", metric: null, scope: "t", level: "ilce",
  values: new Map(), data: null,
};

const fmt1 = (v) => v.toFixed(1).replace(".", ",");
const signed = (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + fmt1(Math.abs(v));
const int = (v) => Math.round(v).toLocaleString("tr-TR");

/* ---- colour ------------------------------------------------------------ */

function mix(a, b, t) {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return "#" + pa.map((x, i) => Math.round(x + (pb[i] - x) * t).toString(16).padStart(2, "0")).join("");
}

function hueFor(metricKey) {
  for (const [re, colour] of HUES) if (re.test(metricKey)) return colour;
  return NEUTRAL;
}

function sequential(metricKey, n) {
  const hue = hueFor(metricKey);
  return Array.from({ length: n }, (_, i) => mix("#2c3036", hue, 0.12 + (0.88 * i) / (n - 1)));
}

// Quantile breaks: with one party the spread is huge, so fixed breaks would paint half the
// country one colour. The legend prints the real cut points.
function quantileBreaks(values, classes) {
  const sorted = [...values].sort((a, b) => a - b);
  const breaks = [];
  for (let i = 1; i < classes; i++) breaks.push(sorted[Math.floor((sorted.length * i) / classes)]);
  return [...new Set(breaks.map((b) => Math.round(b * 10) / 10))];
}

/* ---- values ------------------------------------------------------------ */

function blockValue(block, metricKey) {
  if (!block) return null;
  const stat = STATS.find((s) => s.key === metricKey);
  if (stat) return stat.value(block);
  return block.v[metricKey] ?? 0; // under 1% is not stored: counted as zero
}

function placeValue(place, metricKey, scope) {
  if (!place) return null;
  if (scope === "diff") {
    const a = blockValue(place.kir, metricKey), b = blockValue(place.kent, metricKey);
    return a === null || b === null ? null : a - b;
  }
  return blockValue(place[scope], metricKey);
}

function compute() {
  state.values = new Map();
  for (const [id, place] of Object.entries(state.data.places)) {
    const isProvince = id.length === 5;
    if ((state.level === "il") !== isProvince) continue;
    const v = placeValue(place, state.metric, state.scope);
    if (v !== null && Number.isFinite(v)) state.values.set(id, v);
  }
}

/* ---- geometry ---------------------------------------------------------- */

async function loadProvinces() {
  if (state.outlines) return state.outlines;
  state.outlines = (await (await fetch(PROVINCE_GEO)).json()).features;
  return state.outlines;
}

async function loadDistricts() {
  if (state.geo.ilce) return state.geo.ilce;
  const provinces = await loadProvinces();
  const features = [];
  let done = 0;
  await Promise.all(
    provinces.map(async (p) => {
      try {
        features.push(...(await (await fetch(DISTRICT_GEO(p.properties.area_id))).json()).features);
      } catch {
        /* a province without a boundary file stays blank rather than guessed */
      }
      $("#status").textContent = `sınırlar yükleniyor… ${++done}/${provinces.length}`;
    })
  );
  state.geo.ilce = features;
  return features;
}

function eachRing(feature, fn) {
  const g = feature.geometry;
  if (!g) return;
  if (g.type === "Polygon") g.coordinates.forEach(fn);
  else if (g.type === "MultiPolygon") g.coordinates.forEach((poly) => poly.forEach(fn));
}

function project(features) {
  let x0 = 180, x1 = -180, y0 = 90, y1 = -90;
  for (const f of features) {
    eachRing(f, (ring) => {
      for (const [lon, lat] of ring) {
        if (lon < x0) x0 = lon;
        if (lon > x1) x1 = lon;
        if (lat < y0) y0 = lat;
        if (lat > y1) y1 = lat;
      }
    });
  }
  const k = Math.cos((((y0 + y1) / 2) * Math.PI) / 180);
  return { box: { x: x0 * k, y: -y1, w: (x1 - x0) * k, h: y1 - y0 }, point: ([lon, lat]) => [lon * k, -lat] };
}

function pathFor(feature, point) {
  const parts = [];
  eachRing(feature, (ring) => {
    let d = "";
    for (let i = 0; i < ring.length; i++) {
      const [x, y] = point(ring[i]);
      d += (i ? "L" : "M") + x.toFixed(4) + " " + y.toFixed(4);
    }
    parts.push(d + "Z");
  });
  return parts.join("");
}

/* ---- drawing ----------------------------------------------------------- */

function classify() {
  const values = [...state.values.values()];
  if (state.scope === "diff") {
    return { breaks: DIFF_BREAKS, colours: DIVERGING, labels: legendLabels(DIFF_BREAKS, true) };
  }
  const breaks = quantileBreaks(values, 8);
  const colours = sequential(state.metric, breaks.length + 1);
  return { breaks, colours, labels: legendLabels(breaks, false) };
}

function legendLabels(breaks, signedLabels) {
  const f = signedLabels ? signed : fmt1;
  return [`< ${f(breaks[0])}`, ...breaks.slice(1).map((b, i) => `${f(breaks[i])}–${f(b)}`), `≥ ${f(breaks[breaks.length - 1])}`];
}

function colourFor(v, scale) {
  if (v === null || v === undefined) return null;
  let i = 0;
  while (i < scale.breaks.length && v >= scale.breaks[i]) i++;
  return scale.colours[i];
}

function metricLabel() {
  const stat = STATS.find((s) => s.key === state.metric);
  return stat ? stat.label : state.metric;
}

function scopeLabel() {
  return { t: "tümü", kent: "kent", kir: "kır", diff: "kır − kent farkı (puan)" }[state.scope];
}

function draw() {
  const features = state.level === "il" ? state.outlines : state.geo.ilce;
  const { box, point } = project(state.outlines);
  const svg = document.createElementNS(SVGNS, "svg");
  svg.setAttribute("viewBox", `${box.x} ${box.y} ${box.w} ${box.h}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  const scale = state.values.size ? classify() : null;

  for (const f of features) {
    const id = f.properties.area_id;
    const v = state.values.get(id);
    const p = document.createElementNS(SVGNS, "path");
    p.setAttribute("d", pathFor(f, point));
    p.setAttribute("class", "cell");
    const colour = scale && v !== undefined ? colourFor(v, scale) : null;
    if (colour) p.setAttribute("fill", colour);
    else p.classList.add("na");
    p.dataset.area = id;
    p.addEventListener("mouseenter", () => showDetail(id));
    svg.appendChild(p);
  }
  if (state.level === "ilce") {
    for (const f of state.outlines) {
      const o = document.createElementNS(SVGNS, "path");
      o.setAttribute("d", pathFor(f, point));
      o.setAttribute("class", "prov");
      svg.appendChild(o);
    }
  }
  $("#map").textContent = "";
  $("#map").appendChild(svg);
  drawLegend(scale);
  drawRanks();
  $("#detail").innerHTML =
    `<div class="hint">Haritanın ya da listenin üzerine gelin: o yerin kent, kır ve tümü değerleri burada görünür.</div>`;
  drawNote();
  $("#status").textContent = "";
}

function drawLegend(scale) {
  if (!scale) {
    $("#legend").innerHTML = `<span class="cap">Bu seçim ve kapsam için veri yok.</span>`;
    return;
  }
  $("#legend").innerHTML =
    scale.colours.map((c, i) => `<span class="sw"><i style="background:${c}"></i>${scale.labels[i]}</span>`).join("") +
    `<span class="cap">${state.data.label_tr} · ${metricLabel()} · ${scopeLabel()}${state.scope === "diff" ? "" : " · %"}</span>`;
}

function drawNote() {
  const covered = state.index.provinces.length;
  const parts = [`${state.values.size} ${state.level === "il" ? "il" : "ilçe"} boyalı`];
  if (state.scope !== "t") {
    parts.push(`kent/kır yalnızca işaretlemesi tamamlanan ${covered} ilde var, diğer yerler gri`);
  }
  if (state.scope === "kent" || state.scope === "kir" || state.scope === "diff") {
    parts.push(
      `sınıflanamayan ${int(state.data.unmatched_valid)} geçerli oy hariç` +
        (state.data.unmatched_valid > 500000 ? " — eski seçimde bu pay yüksek, kent/kır dikkatle okunmalı" : "")
    );
  }
  parts.push("%1'in altı oy alan taraf sıfır sayıldı");
  $("#note").textContent = parts.join(" · ");
}

function drawRanks() {
  const rows = [];
  for (const [id, v] of state.values) {
    const place = state.data.places[id];
    const block = place[state.scope === "diff" ? "t" : state.scope] || place.t;
    if (!block || block.g < (state.level === "il" ? 20000 : 2000)) continue;
    rows.push({ id, v, g: block.g });
  }
  rows.sort((a, b) => b.v - a.v);
  const fmtV = state.scope === "diff" ? signed : fmt1;
  const li = (r) => `<li data-area="${r.id}">${placeName(r.id)}<b>${fmtV(r.v)}</b></li>`;
  $("#top").innerHTML = rows.slice(0, 10).map(li).join("");
  $("#bottom").innerHTML = rows.slice(-10).reverse().map(li).join("");
  for (const el of document.querySelectorAll(".rank li")) el.onmouseenter = () => showDetail(el.dataset.area, true);
}

function placeName(id) {
  if (id.length === 5) {
    const f = state.outlines.find((x) => x.properties.area_id === id);
    return f ? f.properties.name_tr : id;
  }
  const province = state.outlines.find((x) => x.properties.area_id === id.slice(0, 5));
  const name = state.data.names[id] || id;
  return `${name} <small>${province ? province.properties.name_tr : ""}</small>`;
}

function showDetail(id, highlight = false) {
  const place = state.data.places[id];
  const host = $("#detail");
  if (!place) {
    host.innerHTML = `<div class="hint">Bu yerin bu seçimde verisi yok.</div>`;
    return;
  }
  const cell = (scope) => {
    const b = place[scope];
    if (!b) return ["—", "—", "—"];
    const v = blockValue(b, state.metric);
    return [v === null ? "—" : fmt1(v), int(b.g), b.k ? fmt1((b.g / b.k) * 100) : "—"];
  };
  const [t, k, r] = ["t", "kent", "kir"].map(cell);
  const diff = placeValue(place, state.metric, "diff");
  const current = state.values.get(id);
  const bigValue = current === undefined ? "—" : state.scope === "diff" ? signed(current) + " puan" : fmt1(current) + "%";
  host.innerHTML =
    `<div class="name">${placeName(id)}</div>` +
    `<div class="hint">${state.data.label_tr} · ${metricLabel()} · ${scopeLabel()}</div>` +
    `<div class="big">${bigValue}</div>` +
    `<table><thead><tr><th></th><th>%</th><th>geçerli oy</th><th>geçerli/kayıtlı</th></tr></thead><tbody>` +
    `<tr><td>Tümü</td><td>${t[0]}</td><td>${t[1]}</td><td>${t[2]}</td></tr>` +
    `<tr><td>Kent</td><td>${k[0]}</td><td>${k[1]}</td><td>${k[2]}</td></tr>` +
    `<tr><td>Kır</td><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td></tr>` +
    `<tr><td>Kır − kent</td><td>${diff === null ? "—" : signed(diff)}</td><td></td><td></td></tr>` +
    `</tbody></table>` +
    (place.kent || place.kir ? "" : `<div class="hint" style="margin-top:8px">Bu yerin ili henüz işaretlenmedi: kent/kır yok.</div>`);
  for (const p of document.querySelectorAll("#map path.hi")) p.classList.remove("hi");
  if (highlight) {
    const p = document.querySelector(`#map path.cell[data-area="${id}"]`);
    if (p) {
      p.classList.add("hi");
      p.parentNode.insertBefore(p, p.parentNode.querySelector("path.prov"));
    }
  }
}

/* ---- wiring ------------------------------------------------------------ */

function fillMetrics() {
  const parties = state.index.elections[state.election].parties;
  const sel = $("#metric");
  sel.innerHTML =
    parties.map((p) => `<option value="${p}">${p}</option>`).join("") +
    STATS.map((s) => `<option value="${s.key}">${s.label}</option>`).join("");
  if (![...sel.options].some((o) => o.value === state.metric)) state.metric = parties[0];
  sel.value = state.metric;
}

async function loadElection(code) {
  if (!state.elections[code]) {
    $("#status").textContent = "seçim verisi yükleniyor…";
    state.elections[code] = await (await fetch(`${BASE}${code}.json`)).json();
  }
  state.data = state.elections[code];
}

async function refresh() {
  $("#status").textContent = "yükleniyor…";
  await Promise.all([loadElection(state.election), state.level === "ilce" ? loadDistricts() : loadProvinces()]);
  await loadProvinces();
  compute();
  draw();
  const q = new URLSearchParams({ secim: state.election, gosterge: state.metric, kapsam: state.scope, duzey: state.level });
  history.replaceState(null, "", "?" + q);
}

function segment(id, onPick) {
  $(`#${id}`).addEventListener("click", (e) => {
    const span = e.target.closest("span[data-v]");
    if (!span || span.classList.contains("on")) return;
    for (const s of $(`#${id}`).children) s.classList.toggle("on", s === span);
    onPick(span.dataset.v);
  });
}

async function init() {
  state.index = await (await fetch(BASE + "index.json")).json();
  const q = new URLSearchParams(location.search);
  const codes = Object.keys(state.index.elections);
  state.election = codes.includes(q.get("secim")) ? q.get("secim") : codes.includes("ho2017") ? "ho2017" : codes[0];
  state.scope = ["t", "kent", "kir", "diff"].includes(q.get("kapsam")) ? q.get("kapsam") : "t";
  state.level = q.get("duzey") === "il" ? "il" : "ilce";
  state.metric = q.get("gosterge");
  $("#election").innerHTML = codes.map((c) => `<option value="${c}">${state.index.elections[c].label_tr}</option>`).join("");
  $("#election").value = state.election;
  fillMetrics();
  for (const [id, key] of [["scope", state.scope], ["level", state.level]]) {
    for (const s of $(`#${id}`).children) s.classList.toggle("on", s.dataset.v === key);
  }
  $("#election").onchange = (e) => {
    state.election = e.target.value;
    fillMetrics();
    refresh();
  };
  $("#metric").onchange = (e) => {
    state.metric = e.target.value;
    refresh();
  };
  segment("scope", (v) => { state.scope = v; refresh(); });
  segment("level", (v) => { state.level = v; refresh(); });
  await refresh();
}

init();
