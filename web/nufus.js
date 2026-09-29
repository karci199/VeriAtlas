// Population ranking page. Every unit is [level, name, district index (negative = province),
// first year index, values]; shares are computed against the province, district and country
// totals of the same year, so a filter never changes a share, only which rows are shown.
"use strict";

const LEVELS = [
  { key: "il", label: "İl", levels: ["il"] },
  { key: "ilce", label: "İlçe", levels: ["ilce"] },
  { key: "belde", label: "Belde", levels: ["belde"] },
  { key: "mahalle", label: "Mahalle / köy", levels: ["mahalle", "koy"] },
];
const TYPE_LABEL = { il: "İl", ilce: "İlçe", belde: "Belde (2013)", mahalle: "Mahalle", koy: "Köy" };
const PAGE = 300;
const fmt = new Intl.NumberFormat("tr-TR");
const pct = (x, d = 2) => (x == null || !isFinite(x) ? "" : x.toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d }));
const fold = (s) => s.toLocaleLowerCase("tr-TR");

const state = { level: "ilce", prov: -1, dist: -1, year: null, base: null, q: "", sort: "value", asc: false, limit: PAGE };
let DATA, TR = [], PROV = [], DIST = [];

const $ = (id) => document.getElementById(id);

function valueAt(u, yi) {
  const i = yi - u[3];
  return i >= 0 && i < u[4].length ? u[4][i] : null;
}

function totals() {
  const n = DATA.years.length;
  TR = new Array(n).fill(0);
  PROV = DATA.provinces.map(() => new Array(n).fill(null));
  DIST = DATA.districts.map(() => new Array(n).fill(null));
  for (const u of DATA.units) {
    for (let yi = 0; yi < n; yi++) {
      const v = valueAt(u, yi);
      if (v == null) continue;
      if (u[0] === "il") { TR[yi] += v; PROV[-1 - u[2]][yi] = v; }
      if (u[0] === "ilce") DIST[u[2]][yi] = v;
    }
  }
}

function provOf(u) { return u[2] < 0 ? -1 - u[2] : DATA.districts[u[2]][2]; }

function rows() {
  const lv = LEVELS.find((l) => l.key === state.level).levels;
  const yi = state.year, bi = state.base;
  const q = fold(state.q.trim());
  const out = [];
  for (const u of DATA.units) {
    if (!lv.includes(u[0])) continue;
    const p = provOf(u);
    if (state.prov >= 0 && p !== state.prov) continue;
    if (state.dist >= 0 && u[2] !== state.dist) continue;
    if (q && !fold(u[1]).includes(q)) continue;
    const v = valueAt(u, yi);
    if (v == null) continue;
    const r = { u, name: u[1], type: TYPE_LABEL[u[0]], prov: DATA.provinces[p][1],
      dist: u[2] >= 0 ? DATA.districts[u[2]][1] : "", value: v,
      trShare: (v / TR[yi]) * 100,
      provShare: u[0] === "il" ? null : (v / PROV[p][yi]) * 100,
      distShare: u[0] === "il" || u[0] === "ilce" ? null : (v / DIST[u[2]][yi]) * 100 };
    if (bi != null) {
      const b = valueAt(u, bi);
      r.change = b == null ? null : v - b;
      r.changePct = b ? ((v - b) / b) * 100 : null;
    }
    out.push(r);
  }
  const k = state.sort, s = state.asc ? 1 : -1;
  out.sort((a, b) => {
    const x = a[k], y = b[k];
    if (x == null) return 1; if (y == null) return -1;
    return typeof x === "string" ? s * x.localeCompare(y, "tr") : s * (x - y);
  });
  return out;
}

function columns() {
  const c = [{ k: "rank", t: "Sıra", num: true }, { k: "name", t: "Ad" }];
  if (state.level !== "il") c.push({ k: "prov", t: "İl" });
  if (state.level === "belde" || state.level === "mahalle") c.push({ k: "dist", t: "İlçe" });
  if (state.level === "mahalle") c.push({ k: "type", t: "Tür" });
  c.push({ k: "value", t: `Nüfus ${DATA.years[state.year]}`, num: true });
  c.push({ k: "trShare", t: "Türkiye payı %", num: true });
  if (state.level !== "il") c.push({ k: "provShare", t: "İl içi pay %", num: true });
  if (state.level === "belde" || state.level === "mahalle") c.push({ k: "distShare", t: "İlçe içi pay %", num: true });
  if (state.base != null) {
    c.push({ k: "change", t: `Değişim ${DATA.years[state.base]}→`, num: true });
    c.push({ k: "changePct", t: "Değişim %", num: true });
  }
  return c;
}

function render() {
  const list = rows();
  const cols = columns();
  $("head").innerHTML = cols.map((c) => `<th data-k="${c.k}" class="${c.num ? "num" : ""} ${state.sort === c.k ? "sorted" + (state.asc ? " asc" : "") : ""}">${c.t}</th>`).join("");
  const maxShare = Math.max(...list.slice(0, state.limit).map((r) => r.trShare), 0) || 1;
  const html = [];
  list.slice(0, state.limit).forEach((r, i) => {
    html.push("<tr>" + cols.map((c) => {
      if (c.k === "rank") return `<td class="num">${i + 1}</td>`;
      if (c.k === "value") return `<td class="num">${fmt.format(r.value)}</td>`;
      if (c.k === "trShare") return `<td class="num">${pct(r.trShare, r.trShare < 0.01 ? 4 : 2)}<span class="bar" style="width:${Math.round((r.trShare / maxShare) * 60)}px"></span></td>`;
      if (c.k === "change") return `<td class="num ${r.change > 0 ? "pos" : r.change < 0 ? "neg" : ""}">${r.change == null ? "" : (r.change > 0 ? "+" : "") + fmt.format(r.change)}</td>`;
      if (c.k === "changePct") return `<td class="num ${r.changePct > 0 ? "pos" : r.changePct < 0 ? "neg" : ""}">${r.changePct == null ? "" : (r.changePct > 0 ? "+" : "") + pct(r.changePct, 1)}</td>`;
      if (c.num) return `<td class="num">${pct(r[c.k])}</td>`;
      return `<td>${r[c.k] ?? ""}</td>`;
    }).join("") + "</tr>");
  });
  $("body").innerHTML = html.join("");
  const sum = list.reduce((a, r) => a + r.value, 0);
  const y = DATA.years[state.year];
  $("summary").innerHTML = `<span><b>${fmt.format(list.length)}</b> birim</span>
    <span>Toplam <b>${fmt.format(sum)}</b></span>
    <span>Türkiye payı <b>%${pct((sum / TR[state.year]) * 100, 1)}</b></span>
    <span>Türkiye ${y}: <b>${fmt.format(TR[state.year])}</b></span>`;
  $("more").innerHTML = list.length > state.limit ? `<button id="moreBtn">${fmt.format(Math.min(PAGE, list.length - state.limit))} satır daha göster (${fmt.format(list.length - state.limit)} kaldı)</button>` : "";
  if ($("moreBtn")) $("moreBtn").onclick = () => { state.limit += PAGE; render(); };
  $("head").querySelectorAll("th").forEach((th) => th.onclick = () => {
    const k = th.dataset.k; if (k === "rank") return;
    if (state.sort === k) state.asc = !state.asc; else { state.sort = k; state.asc = ["name", "prov", "dist", "type"].includes(k); }
    render();
  });
  const n = [];
  if (state.level === "mahalle") n.push("Mahalle ve köy kimlikleri 2013'te değişti: 2007–2012 ile 2013–2025 aynı yer için iki ayrı satır olabilir; değişim yalnız iki yılda da var olan satırda hesaplanır. Küçük mahallelerde 0–17 yaş satırı gizli olduğundan toplam biraz eksik olabilir.");
  if (state.level === "belde") n.push("Belde: mahallenin 2013'te bağlı olduğu belde (büyükşehirlerde 2014'te kapatılanlar dahil); 2013–2025. Beldenin mahalleleri Mahalle / köy düzeyinde ayrıca listelenir.");
  if (state.level === "ilce") n.push("2008'de kurulan ilçeler 2007'de yoktur; bölünen ilçelerde 2007 değeri eski sınırdadır.");
  $("note").textContent = n.join(" ");
}

function fillDistricts() {
  const opts = ['<option value="-1">Tümü</option>'];
  DATA.districts.forEach((d, i) => { if (state.prov >= 0 && d[2] === state.prov) opts.push(`<option value="${i}">${d[1]}</option>`); });
  $("dist").innerHTML = opts.join("");
  $("dist").disabled = state.prov < 0;
  state.dist = -1;
}

function fillYears() {
  const lv = LEVELS.find((l) => l.key === state.level).levels;
  const first = lv.some((l) => l === "belde") ? DATA.years.indexOf(2013) : 0;
  const last = DATA.years.length - 1;
  const ys = DATA.years.map((y, i) => i).filter((i) => i >= first);
  if (state.year == null || state.year < first) state.year = last;
  if (state.base != null && state.base < first) state.base = null;
  $("year").innerHTML = ys.map((i) => `<option value="${i}" ${i === state.year ? "selected" : ""}>${DATA.years[i]}</option>`).join("");
  $("base").innerHTML = '<option value="">—</option>' + ys.map((i) => `<option value="${i}" ${i === state.base ? "selected" : ""}>${DATA.years[i]}</option>`).join("");
}

async function main() {
  $("summary").textContent = "Veri yükleniyor…";
  const res = await fetch("../public/nufus_birimler.json");
  DATA = await res.json();
  totals();
  $("level").innerHTML = LEVELS.map((l) => `<button data-k="${l.key}" class="${l.key === state.level ? "on" : ""}">${l.label}</button>`).join("");
  $("level").querySelectorAll("button").forEach((b) => b.onclick = () => {
    state.level = b.dataset.k; state.limit = PAGE; state.sort = "value"; state.asc = false;
    $("level").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    fillYears(); render();
  });
  $("prov").innerHTML = '<option value="-1">Tümü</option>' + DATA.provinces.map((p, i) => [p[1], i]).sort((a, b) => a[0].localeCompare(b[0], "tr")).map(([n, i]) => `<option value="${i}">${n}</option>`).join("");
  $("prov").onchange = (e) => { state.prov = +e.target.value; state.limit = PAGE; fillDistricts(); render(); };
  $("dist").onchange = (e) => { state.dist = +e.target.value; state.limit = PAGE; render(); };
  $("year").onchange = (e) => { state.year = +e.target.value; render(); };
  $("base").onchange = (e) => { state.base = e.target.value === "" ? null : +e.target.value; render(); };
  $("q").oninput = (e) => { state.q = e.target.value; state.limit = PAGE; render(); };
  fillDistricts(); fillYears(); render();
}
main();
