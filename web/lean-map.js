/* Lean choropleth: one number per place, painted on its own boundary.
 *
 * The number is the shift of a place's distance from the national left-bloc share
 * between the first and last window of the period — positive means it moved left
 * relative to the country, negative right. It is computed in
 * scripts/analyze_province_lean.py, not here; this page only joins it to geometry.
 *
 * The scale is diverging and classed, not continuous: the reader has to be able to
 * tell "moved a lot" from "moved a little" without a colour-matching exercise, and
 * zero has to be a visible boundary rather than a shade.
 */

"use strict";

const DATA = { il: "../public/elections/lean-il.json", ilce: "../public/elections/lean-ilce.json" };
const PROVINCE_GEO = "../public/areas.geojson";
const DISTRICT_GEO = (id) => `../public/geo/districts/${id}.geojson`;

// Red = moved right relative to the country, blue = moved left. Breaks in points.
const BREAKS = [-20, -10, -5, 0, 5, 10, 20];
const COLOURS = [
  "#7f2828", "#b3453c", "#d98a72", "#e8c9b4",
  "#bcd3e6", "#6fa8d8", "#3b74b8", "#1d4380",
];

const state = { level: "il", reading: "shift", data: {}, geo: {}, byArea: new Map() };
const $ = (s) => document.querySelector(s);
const SVGNS = "http://www.w3.org/2000/svg";
const signed = (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(1).replace(".", ",");

function colourFor(v) {
  if (v === null || v === undefined) return null;
  let i = 0;
  while (i < BREAKS.length && v >= BREAKS[i]) i++;
  return COLOURS[i];
}

/* ---- geometry ---------------------------------------------------------- */

async function loadGeo(level) {
  if (state.geo[level]) return state.geo[level];
  let features;
  if (level === "il") {
    features = (await (await fetch(PROVINCE_GEO)).json()).features;
  } else {
    const provinces = (await (await fetch(PROVINCE_GEO)).json()).features;
    features = [];
    let done = 0;
    // 81 small files rather than one big one: they are what the atlas already ships.
    await Promise.all(
      provinces.map(async (p) => {
        try {
          const fc = await (await fetch(DISTRICT_GEO(p.properties.area_id))).json();
          features.push(...fc.features);
        } catch {
          /* a province without a boundary file is left blank, not guessed */
        }
        $("#status").textContent = `sınırlar yükleniyor… ${++done}/${provinces.length}`;
      })
    );
  }
  state.geo[level] = features;
  return features;
}

// Equirectangular, fitted to the drawn features. Longitude is scaled by cos(mean lat)
// so Türkiye is not stretched sideways.
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
  return {
    box: { x: x0 * k, y: -y1, w: (x1 - x0) * k, h: y1 - y0 },
    point: ([lon, lat]) => [lon * k, -lat],
  };
}

function eachRing(feature, fn) {
  const g = feature.geometry;
  if (!g) return;
  if (g.type === "Polygon") g.coordinates.forEach(fn);
  else if (g.type === "MultiPolygon") g.coordinates.forEach((poly) => poly.forEach(fn));
}

function pathFor(feature, project) {
  const parts = [];
  eachRing(feature, (ring) => {
    let d = "";
    for (let i = 0; i < ring.length; i++) {
      const [x, y] = project(ring[i]);
      d += (i ? "L" : "M") + x.toFixed(4) + " " + y.toFixed(4);
    }
    parts.push(d + "Z");
  });
  return parts.join("");
}

/* ---- drawing ----------------------------------------------------------- */

function draw() {
  const features = state.geo[state.level];
  const { box, point } = project(features);
  const svg = document.createElementNS(SVGNS, "svg");
  svg.setAttribute("viewBox", `${box.x} ${box.y} ${box.w} ${box.h}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

  for (const f of features) {
    const row = state.byArea.get(f.properties.area_id);
    const value = row ? row[state.reading] : null;
    const p = document.createElementNS(SVGNS, "path");
    p.setAttribute("d", pathFor(f, point));
    const colour = colourFor(value);
    if (colour) p.setAttribute("fill", colour);
    else p.setAttribute("class", "na");
    p.dataset.area = f.properties.area_id;
    const title = document.createElementNS(SVGNS, "title");
    title.textContent = row
      ? `${row.name}: ${signed(value)} puan`
      : `${f.properties.name_tr} — kapsam dışı`;
    p.appendChild(title);
    p.addEventListener("mouseenter", () => showDetail(f.properties.area_id));
    svg.appendChild(p);
  }
  const host = $("#map");
  host.textContent = "";
  host.appendChild(svg);
  drawLegend();
  drawRanks();
  $("#detail").innerHTML =
    `<div class="hint">Haritanın ya da listenin üzerine gelin: o birimin iki pencere ` +
    `farkı ve diğer okumadaki değeri burada görünür.</div>`;
  const meta = state.data[state.level];
  $("#note").textContent =
    `${meta.units.length} birim · ${meta.elections.length} seçim (${meta.elections[0]}–` +
    `${meta.elections[meta.elections.length - 1]}) · 2007 ve 2011 hariç` +
    (state.level === "ilce"
      ? ` · sınırı değiştiği için elenen ${meta.boundaryDropped} ilçe ve ` +
        `${meta.minVoters.toLocaleString("tr-TR")} seçmenin altındakiler boş bırakıldı`
      : " · 1989 sonrası kurulan iller çıktıkları ille aynı renkte");
  $("#status").textContent = "";
}

function drawLegend() {
  const labels = ["−20 ve altı", "−20…−10", "−10…−5", "−5…0", "0…+5", "+5…+10", "+10…+20", "+20 ve üstü"];
  $("#legend").innerHTML =
    COLOURS.map((c, i) => `<span class="sw"><i style="background:${c}"></i>${labels[i]}</span>`).join("") +
    `<span class="cap">← ülkeye göre sağa kayma · puan · sola kayma →</span>`;
}

function drawRanks() {
  const rows = [...state.data[state.level].units].sort((a, b) => b[state.reading] - a[state.reading]);
  const li = (r) =>
    `<li data-area="${r.areas[0]}">${r.name}<b>${signed(r[state.reading])}</b></li>`;
  $("#topLeft").innerHTML = rows.slice(0, 10).map(li).join("");
  $("#topRight").innerHTML = rows.slice(-10).reverse().map(li).join("");
  for (const el of document.querySelectorAll(".rank li")) {
    el.onmouseenter = () => showDetail(el.dataset.area, true);
  }
}

function showDetail(areaId, highlight = false) {
  const row = state.byArea.get(areaId);
  const host = $("#detail");
  if (!row) {
    host.innerHTML = `<div class="hint">Bu birim kapsam dışı: sınırı değişmiş, çok küçük ya da yeterli seçimde verisi yok.</div>`;
    return;
  }
  host.innerHTML =
    `<div class="name">${row.name}</div>` +
    `<div class="hint">${state.reading === "shift" ? "Kürt partileri solda" : "Kürt partileri hariç"}</div>` +
    `<div class="big" style="color:${colourFor(row[state.reading])}">${signed(row[state.reading])} puan</div>` +
    `<table><tbody>` +
    `<tr><td>ilk pencere farkı</td><td>${signed(state.reading === "shift" ? row.early : row.earlyNk)}</td></tr>` +
    `<tr><td>2018–23 farkı</td><td>${signed(state.reading === "shift" ? row.late : row.lateNk)}</td></tr>` +
    `<tr><td>diğer okuma</td><td>${signed(state.reading === "shift" ? row.shiftNk : row.shift)}</td></tr>` +
    `<tr><td>seçim sayısı</td><td>${row.n}</td></tr>` +
    `</tbody></table>`;
  for (const p of document.querySelectorAll("#map path.hi")) p.classList.remove("hi");
  if (highlight) {
    for (const id of row.areas) {
      const p = document.querySelector(`#map path[data-area="${id}"]`);
      if (p) {
        p.classList.add("hi");
        p.parentNode.appendChild(p); // raise, so the outline is not covered
      }
    }
  }
}

/* ---- wiring ------------------------------------------------------------ */

async function show(level) {
  state.level = level;
  $("#status").textContent = "yükleniyor…";
  if (!state.data[level]) {
    state.data[level] = await (await fetch(DATA[level])).json();
  }
  await loadGeo(level);
  state.byArea = new Map();
  for (const row of state.data[level].units) {
    for (const id of row.areas) state.byArea.set(id, row);
  }
  draw();
  const q = new URLSearchParams({ duzey: level, okuma: state.reading });
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
  const q = new URLSearchParams(location.search);
  state.reading = q.get("okuma") === "shiftNk" ? "shiftNk" : "shift";
  const level = q.get("duzey") === "ilce" ? "ilce" : "il";
  for (const [id, key] of [["level", level], ["reading", state.reading]]) {
    for (const s of $(`#${id}`).children) s.classList.toggle("on", s.dataset.v === key);
  }
  segment("level", (v) => show(v));
  segment("reading", (v) => {
    state.reading = v;
    show(state.level);
  });
  await show(level);
}

init();
