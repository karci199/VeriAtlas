// Population ranking page. Every unit is [level, name, district index (negative = province),
// first year index, values, settlement index]; shares are computed against the province,
// district and country totals of the same year, so a filter never changes a share, only which
// rows are shown. An analysis picks the ranking column and a default set of columns; the user
// can switch any column on or off. A row with no value for the ranking column is left out of
// the ranking (a neighbourhood that did not exist in the comparison year, say) and counted.
"use strict";

const LEVELS = [
  { key: "il", label: "İl", levels: ["il"] },
  { key: "ilce", label: "İlçe", levels: ["ilce"] },
  { key: "belde", label: "Belde", levels: ["belde"] },
  { key: "mahalle", label: "Mahalle / köy", levels: ["mahalle", "koy"] },
];
const TYPE_LABEL = { il: "İl", ilce: "İlçe", belde: "Belde", mahalle: "Mahalle", koy: "Köy" };

// every computable column; `lv` limits where it makes sense, `base` needs a comparison year
const COLS = {
  rank: { t: "Sıra", num: true, fixed: true },
  name: { t: "Ad", fixed: true },
  prov: { t: "İl", lv: ["ilce", "belde", "mahalle"], always: true },
  dist: { t: "İlçe", lv: ["belde", "mahalle"], always: true },
  settle: { t: "Yerleşim", lv: ["mahalle"], always: true },
  type: { t: "Tür", lv: ["mahalle"], always: true },
  value: { t: "Nüfus", num: true },
  prevChange: { t: "Önceki yıla göre", num: true, sign: true },
  prevChangePct: { t: "Önceki yıla göre %", num: true, sign: true, d: 2 },
  change: { t: "Değişim", num: true, sign: true, base: true },
  changePct: { t: "Değişim %", num: true, sign: true, d: 1, base: true },
  cagr: { t: "Yıllık ort. büyüme %", num: true, sign: true, d: 2, base: true },
  trShare: { t: "Türkiye payı %", num: true, d: 2, bar: true },
  provShare: { t: "İl içi pay %", num: true, d: 2, lv: ["ilce", "belde", "mahalle"] },
  distShare: { t: "İlçe içi pay %", num: true, d: 2, lv: ["belde", "mahalle"] },
  trShareDelta: { t: "Türkiye payı değişimi (puan)", num: true, sign: true, d: 3, base: true },
  provShareDelta: { t: "İl içi pay değişimi (puan)", num: true, sign: true, d: 2, base: true, lv: ["ilce", "belde", "mahalle"] },
  distShareDelta: { t: "İlçe içi pay değişimi (puan)", num: true, sign: true, d: 2, base: true, lv: ["belde", "mahalle"] },
  first: { t: "İlk yıl", num: true },
};
// what is counted; each unit carries one series per indicator. Only total population so far --
// under-18s, voters, election results join this list and every column works for them
// kind "count" adds up (shares, % change work); kind "ratio" does not (change in points only)
const INDICATORS = [
  { group: "Nüfus", key: "total", label: "Toplam nüfus", kind: "count" },
  { group: "Nüfus", key: "u17", label: "0–17 yaş nüfusu", kind: "count" },
  { group: "Nüfus", key: "a18", label: "18 yaş ve üstü", kind: "count" },
  { group: "Nüfus", key: "u17p", label: "0–17 yaş payı %", kind: "ratio" },
  { group: "Yaş", key: "med", label: "Ortanca yaş", kind: "ratio", ex: "med" },
  { group: "Yaş", key: "mean", label: "Ortalama yaş", kind: "ratio", ex: "mean" },
  { group: "Seçmen", key: "vote_med", label: "Seçmen ortanca yaşı", kind: "ratio", ex: "vote_med", lv: ["il", "ilce"] },
  { group: "Seçmen", key: "vote_mean", label: "Seçmen ortalama yaşı", kind: "ratio", ex: "vote_mean", lv: ["il", "ilce"] },
  { group: "Yaşam olayları (il)", key: "fm_f", label: "İlk evlenme yaşı, kadın", kind: "ratio", ex: "fm_f", lv: ["il"] },
  { group: "Yaşam olayları (il)", key: "fm_m", label: "İlk evlenme yaşı, erkek", kind: "ratio", ex: "fm_m", lv: ["il"] },
  { group: "Yaşam olayları (il)", key: "mar", label: "Ortalama evlenme yaşı", kind: "ratio", ex: "mar", lv: ["il"] },
  { group: "Yaşam olayları (il)", key: "mom_med", label: "Doğumda anne yaşı, ortanca", kind: "ratio", ex: "mom_med", lv: ["il"] },
  { group: "Yaşam olayları (il)", key: "mom_mean", label: "Doğumda anne yaşı, ortalama", kind: "ratio", ex: "mom_mean", lv: ["il"] },
  { group: "Yaşam olayları (il)", key: "death_med", label: "Ölüm yaşı, ortanca", kind: "ratio", ex: "death_med", lv: ["il"] },
  { group: "Yaşam olayları (il)", key: "death_mean", label: "Ölüm yaşı, ortalama", kind: "ratio", ex: "death_mean", lv: ["il"] },
];
// an extra series kept in the unit's extras slot, [first year index, values]
function exAt(u, key, yi) {
  const s = u[7] && u[7][key];
  if (!s) return null;
  const i = yi - s[0];
  return i >= 0 && i < s[1].length ? s[1][i] : null;
}
const COUNT_ONLY = ["trShare", "provShare", "distShare", "changePct", "cagr", "prevChangePct", "trShareDelta", "provShareDelta", "distShareDelta"];
// a view is a ready column set with its natural ranking; any header still sorts, and the
// Sütunlar menu adds or drops columns on top of it
const VIEWS = [
  { key: "temel", label: "Temel", sort: "value", cols: ["value", "trShare", "provShare", "distShare"] },
  { key: "degisim", label: "Değişim", sort: "changePct", base: true, cols: ["value", "change", "changePct", "cagr", "prevChangePct"] },
  { key: "pay", label: "Pay değişimi", sort: "provShareDelta", base: true, cols: ["value", "provShare", "provShareDelta", "distShareDelta", "trShareDelta"] },
];
const WIDTH = { rank: 52, name: 180, prov: 115, dist: 115, settle: 140, type: 70, value: 105, first: 64, trShare: 150 };
const PAGE = 300;
const fmt = new Intl.NumberFormat("tr-TR");
const num = (x, d) => x.toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });
const fold = (s) => s.toLocaleLowerCase("tr-TR");
const $ = (id) => document.getElementById(id);

// per-viewer conveniences only (column set, widths); the page works when storage is off
const store = {
  get(k, dflt) { try { const v = localStorage.getItem("nufus." + k); return v == null ? dflt : JSON.parse(v); } catch (e) { return dflt; } },
  set(k, v) { try { localStorage.setItem("nufus." + k, JSON.stringify(v)); } catch (e) { /* storage off */ } },
};
const state = { level: "ilce", view: "temel", indicator: "total", prov: -1, dist: -1, settle: -1, year: null, base: null, q: "",
                sort: "value", asc: false, limit: PAGE, min: null, max: null };
let visible = store.get("cols", null);
let userWidth = store.get("widths", {});
let DATA, TR = [], PROV = [], DIST = [];
const UIDX = new Map();  // unit -> its index, for the ⓘ links

const widthOf = (k) => userWidth[k] || WIDTH[k] || 110;
const analysis = () => VIEWS.find((a) => a.key === state.view);

// total population: filters, the population floor and "does the unit exist that year"
function valueAt(u, yi) {
  const i = yi - u[3];
  return i >= 0 && i < u[4].length ? u[4][i] : null;
}
function u17At(u, yi) {
  const s = u[6];
  if (!s) return null;
  const i = yi - s[0];
  return i >= 0 && i < s[1].length ? s[1][i] : null;
}
const ind = () => INDICATORS.find((x) => x.key === state.indicator);
// the chosen indicator's value
function indAt(u, yi, key = state.indicator) {
  const t = valueAt(u, yi);
  if (key === "total") return t;
  const def = INDICATORS.find((x) => x.key === key);
  if (def && def.ex) return t == null ? null : exAt(u, def.ex, yi);
  const c = u17At(u, yi);
  if (c == null || t == null) return null;
  if (key === "u17") return c;
  if (key === "a18") return t - c;
  if (key === "u17p") return t ? (c / t) * 100 : null;
  return null;
}

// share bases for the chosen count indicator
function totals() {
  const n = DATA.years.length;
  TR = new Array(n).fill(0);
  PROV = DATA.provinces.map(() => new Array(n).fill(null));
  DIST = DATA.districts.map(() => new Array(n).fill(null));
  if (ind().kind !== "count") return;
  for (const u of DATA.units) for (let yi = 0; yi < n; yi++) {
    const v = indAt(u, yi);
    if (v == null) continue;
    if (u[0] === "il") { TR[yi] += v; PROV[-1 - u[2]][yi] = v; }
    if (u[0] === "ilce") DIST[u[2]][yi] = v;
  }
  // a district not yet founded that year: its own quarters summed, i.e. today's boundaries
  if (state.indicator === "total")
    for (const [d, [first, vals]] of Object.entries(DATA.district_cb || {}))
      vals.forEach((v, i) => { if (DIST[+d][first + i] == null && v != null) DIST[+d][first + i] = v; });
}

const provOf = (u) => (u[2] < 0 ? -1 - u[2] : DATA.districts[u[2]][2]);
const share = (v, tot) => (v == null || !tot ? null : (v / tot) * 100);

function measures(u, yi, bi) {
  const p = provOf(u), v = indAt(u, yi);
  const inProv = u[0] !== "il", inDist = u[0] === "belde" || u[0] === "mahalle" || u[0] === "koy";
  const m = { value: v, trShare: share(v, TR[yi]),
    provShare: inProv ? share(v, PROV[p][yi]) : null, distShare: inDist ? share(v, DIST[u[2]][yi]) : null };
  const pv = yi > 0 ? indAt(u, yi - 1) : null;
  m.prevChange = pv == null ? null : v - pv;
  m.prevChangePct = pv ? ((v - pv) / pv) * 100 : null;
  if (bi != null) {
    const b = indAt(u, bi);
    m.isNew = b == null && u[3] > bi;
    m.change = b == null ? null : v - b;
    m.changePct = b ? ((v - b) / b) * 100 : null;
    const yrs = yi - bi;
    m.cagr = b && yrs ? (Math.pow(v / b, 1 / yrs) - 1) * 100 : null;
    const d = (a, c) => (a == null || c == null ? null : a - c);
    m.trShareDelta = d(m.trShare, share(b, TR[bi]));
    m.provShareDelta = inProv ? d(m.provShare, share(b, PROV[p][bi])) : null;
    m.distShareDelta = inDist ? d(m.distShare, share(b, DIST[u[2]][bi])) : null;
  }
  return m;
}

const usable = (k) => { const c = COLS[k]; return !(c.lv && !c.lv.includes(state.level)) && !(c.base && state.base == null) && !(ind().kind === "ratio" && COUNT_ONLY.includes(k)); };

function shownCols() {
  const on = visible || analysis().cols;
  return Object.keys(COLS).filter((k) => usable(k) && (COLS[k].fixed || COLS[k].always || on.includes(k) || k === state.sort));
}

function rows() {
  const lv = LEVELS.find((l) => l.key === state.level).levels;
  const q = fold(state.q.trim());
  const out = [];
  let dropped = 0;
  for (const u of DATA.units) {
    if (!lv.includes(u[0])) continue;
    const p = provOf(u);
    if (state.prov >= 0 && p !== state.prov) continue;
    if (state.dist >= 0 && u[2] !== state.dist) continue;
    if (state.settle >= 0 && u[5] !== state.settle) continue;
    if (q && !fold(u[1]).includes(q)) continue;
    const v0 = valueAt(u, state.year);
    if (v0 == null) continue;
    if (state.max != null && v0 > state.max) continue;
    if (state.min != null) {
      // the floor holds in the comparison year too: a 30-person village tripling is noise
      const b0 = state.base != null ? valueAt(u, state.base) : null;
      if (v0 < state.min || (b0 != null && b0 < state.min)) continue;
    }
    const r = { ...measures(u, state.year, state.base), u, lvl: u[0], did: u[2], name: u[1], type: TYPE_LABEL[u[0]], prov: DATA.provinces[p][1],
      dist: u[2] >= 0 ? DATA.districts[u[2]][1] : "", settle: u[5] >= 0 ? DATA.settlements[u[5]] : "",
      first: DATA.years[u[3]] };
    // no value for the ranking column: out of the ranking, not at its bottom
    if (COLS[state.sort].num && state.sort !== "rank" && r[state.sort] == null) { dropped++; continue; }
    out.push(r);
  }
  const k = state.sort, s = state.asc ? 1 : -1;
  out.sort((a, b) => (typeof a[k] === "string" ? s * a[k].localeCompare(b[k], "tr") : s * (a[k] - b[k])));
  return { list: out, dropped };
}

function cell(k, r, i, maxShare) {
  const c = COLS[k];
  if (k === "rank") return `<td class="num rank">${i + 1}</td>`;
  if (k === "name") {
    const has = infoLines(r.u).length > 0;
    return `<td class="name" title="${r.name}">${r.name}${has ? `<a class="info" data-i="${UIDX.get(r.u)}" title="Bilgi">ⓘ</a>` : ""}</td>`;
  }
  if (k === "first") return `<td class="num rank">${r.first}</td>`;
  if (k === "change" && r.isNew) return `<td class="num new" title="${DATA.years[state.base]} yılında kaydı yok">yeni</td>`;
  if (!c.num) return `<td title="${r[k] ?? ""}">${r[k] ?? ""}</td>`;
  const x = r[k];
  if (x == null) return `<td class="num"></td>`;
  const ratio = ind().kind === "ratio" && ["value", "change", "prevChange"].includes(k);
  const txt = ratio ? num(x, 1) : c.d == null ? fmt.format(Math.round(x)) : num(x, k === "trShare" && x < 0.01 ? 4 : c.d);
  const cls = c.sign ? (x > 0 ? "pos" : x < 0 ? "neg" : "") : "";
  const signed = c.sign && x > 0 ? "+" + txt : txt;
  if (c.bar) return `<td class="num"><div class="cell-bar">${signed}<span class="bar" style="width:${Math.max(2, Math.round((x / maxShare) * 50))}px"></span></div></td>`;
  return `<td class="num ${cls}">${signed}</td>`;
}

function title(k) {
  const y = DATA.years[state.year], b = state.base != null ? DATA.years[state.base] : "";
  const ratio = ind().kind === "ratio", unit = ind().ex ? " (yıl)" : " (puan)";
  if (k === "value") return `${ind().label} ${y}`;
  if (k === "change") return `Değişim ${b}→${y}${ratio ? unit : ""}`;
  if (k === "prevChange" && ratio) return `${y - 1}→${y}${unit}`;
  if (k === "changePct") return `Değişim ${b}→${y} %`;
  if (k === "prevChange") return `${y - 1}→${y}`;
  if (k === "prevChangePct") return `${y - 1}→${y} %`;
  if (k === "cagr") return `Yıllık ort. büyüme ${b}→${y} %`;
  return COLS[k].t;
}

function render() {
  const { list, dropped } = rows();
  const cols = shownCols();
  $("cols").innerHTML = cols.map((k) => `<col data-k="${k}" style="width:${widthOf(k)}px">`).join("");
  $("head").innerHTML = cols.map((k) => `<th data-k="${k}" title="${title(k)}" class="${COLS[k].num ? "num" : ""} ${state.sort === k ? "sorted" + (state.asc ? " asc" : "") : ""}">${title(k)}<span class="grip"></span></th>`).join("");
  const page = list.slice(0, state.limit);
  const maxShare = Math.max(...page.map((r) => r.trShare || 0), 0) || 1;
  $("body").innerHTML = page.map((r, i) => "<tr>" + cols.map((k) => cell(k, r, i, maxShare)).join("") + "</tr>").join("");
  const y = DATA.years[state.year];
  let cards;
  if (ind().kind === "count") {
    const sum = list.reduce((a, r) => a + r.value, 0);
    cards = `<span><b>${fmt.format(sum)}</b>seçili toplam (${ind().label.toLocaleLowerCase("tr-TR")})</span>
      <span><b>%${num((sum / TR[state.year]) * 100, 1)}</b>Türkiye payı</span>
      <span><b>${fmt.format(TR[state.year])}</b>Türkiye ${y}</span>`;
  } else {
    // a ratio is summarised population-weighted, over the rows shown and over Türkiye
    const w = (units) => { let a = 0, t = 0; for (const u of units) { const x = indAt(u, state.year), v = valueAt(u, state.year); if (x != null && v) { a += x * v; t += v; } } return t ? a / t : null; };
    const shown = w(list.map((r) => r.u)), tr = w(DATA.units.filter((u) => u[0] === "il"));
    const pc = state.indicator === "u17p" ? "%" : "";
    cards = `<span><b>${pc}${shown == null ? "–" : num(shown, 1)}</b>seçilenlerin nüfus ağırlıklı ortalaması</span>
      <span><b>${pc}${tr == null ? "–" : num(tr, 1)}</b>Türkiye ${y} (illerin ağırlıklı ortalaması)</span>`;
  }
  $("summary").innerHTML = `<span><b>${fmt.format(list.length)}</b>birim</span>` + cards +
    (dropped ? `<span><b>${fmt.format(dropped)}</b>sıralamaya girmedi</span>` : "");
  $("more").innerHTML = list.length > state.limit ? `<button id="moreBtn">${fmt.format(Math.min(PAGE, list.length - state.limit))} satır daha (${fmt.format(list.length - state.limit)} kaldı)</button>` : "";
  if ($("moreBtn")) $("moreBtn").onclick = () => { state.limit += PAGE; render(); };
  wireHead();
  $("body").querySelectorAll("a.info").forEach((el) => el.onclick = (ev) => {
    ev.preventDefault(); ev.stopPropagation();
    const u = DATA.units[+el.dataset.i];
    showPop(el, u[1], infoLines(u));
  });
}

// what the ⓘ of a row says: district history, belde notes, a reused id, and for the age
// indicators how the value was made
function infoLines(u) {
  const out = [];
  if (u[0] === "ilce" && DATA.history[u[2]]) out.push(...DATA.history[u[2]]);
  if (u[7] && u[7].h) out.push(...u[7].h);
  if ((state.indicator === "med" || state.indicator === "mean") && (u[0] === "mahalle" || u[0] === "koy" || u[0] === "belde")) {
    const r = u[7] && u[7].medr;
    if (state.indicator === "med" && r) out.push(`2024 ortanca yaşı Monte Carlo ile (200 çekiliş): %5–95 aralığı ${num(r[0], 1)}–${num(r[1], 1)}; kaynak ${ {A: "Endeksa yaş grupları TÜİK toplamını tutuyor", B: "regresyon", C: "seçmen verisi"}[r[2]] || r[2] }.`);
    if (state.indicator === "mean") out.push("2024 ortalama yaşı: Endeksa yaş grupları, TÜİK'in bu mahalle için verdiği 0–17 ve 18+ sayısına ölçeklenerek.");
    if (u[7] && u[7].model) out.push("2024 dışındaki yıllar model tahminidir: mahallenin 2024 yaş yapısı, ilçenin her yaş grubundaki değişimiyle o yıla taşınıp mahallenin o yılki 0–17 / 18+ sayısına ölçeklenir.");
    else if (u[0] !== "belde") out.push("Yalnız 2024 (bu birimde yıllık 0–17 kırılımı yok).");
  }
  return out;
}

// general notes behind one link instead of text under the table
const NOTES = [
  "Seçilen yılda kaydı olmayan birim listede yoktur; sıralanan sütunda değeri olmayan birim (karşılaştırma yılında ya da önceki yılda kaydı yok) sıralamaya alınmaz, sayısı özet kartında yazar.",
  "Adı değişen ilçeler (Eyüp → Eyüpsultan, Aydın Merkez → Efeler …) tek satırda, kesintisiz seridir. Kurulan, bölünen, kapanan ilçelerin tarihçesi adının yanındaki ⓘ'dedir; kaynak ilçeler mahallelerin TÜİK kayıt geçmişinden, nüfus ağırlığıyla hesaplanır.",
  "Mahalle ve köy kimlikleri 2013'te değişti: 2007–2012 ile 2013–2025 aynı yer için iki ayrı satır olabilir; eski kimliklerin yerleşimi boştur. Büyük yüzdeler gerçek büyüme de mahalle sınırı değişikliği de olabilir.",
  "Yerleşim: il/ilçe merkezinde semt, köyler için \"<ilçe> Köyleri\", beldeler resmî belediye adıyla.",
  "Belde: resmî TÜİK statüsü, bugün belediyesi olan beldeler (yalnız büyükşehir dışındaki iller), 2007–2025, bugünkü mahalleleriyle. Beldenin mahalleleri Mahalle / köy düzeyinde de listelenir.",
  "Küçük mahallelerde 0–17 yaş satırı gizlidir: toplam birkaç kişi eksik olabilir, 0–17 göstergelerinde o mahalle boş kalır.",
  "Seçmen yaşı: YSK seçmen profilleri (2011, 2015 Kasım, 2018, 2023), il ve ilçe; yaş grupları 18–24 … 75+. Yaşam olayları yalnız il düzeyinde: anne yaşı ve ölüm yaşı 2009–2025 yaş gruplarından (ortanca ölüm yaşı bebek ölümlerinden etkilenmez, ortalama etkilenir), ilk evlenme ve evlenme yaşı TÜİK'in yayımladığı değer. Boşanma yaşı depoda yok.",
  "Yaş: il ortanca yaşı TÜİK'in kendi değeri; ilçede 5'li yaş gruplarından hesap (2007–2025). Mahalle, köy ve belde: 2024 Monte Carlo (ortanca) ve Endeksa (ortalama); mahallelerde diğer yıllar model tahminidir, ⓘ'de yazar.",
  "0–17 yaş: mahallede TÜİK'in 0–17 satırı; il ve ilçede 5'li yaş gruplarından (15–19'un 3/5'i). Büyükşehir dışı köylerde yaş kırılımı yoktur. Oran göstergelerinde pay sütunları kapanır, değişim puan olarak verilir.",
  "Nüfus eşiği seçili yıla uygulanır; \"en az\" karşılaştırma yılında da aranır, küçük tabandan doğan büyük yüzdeleri eler.",
  "İlçe içi pay, ilçenin henüz kurulmadığı yıllarda (Kayapınar, Ataşehir 2007) bugünkü sınırlarıyla, yani bugünkü mahallelerinin o yılki toplamına göre hesaplanır.",
];

function showPop(anchor, head, items) {
  const p = $("pop"), r = anchor.getBoundingClientRect();
  p.innerHTML = `<h4>${head}</h4><ul>${items.map((x) => `<li>${x}</li>`).join("")}</ul>`;
  p.hidden = false;
  p.style.left = Math.min(window.scrollX + r.left, window.scrollX + document.documentElement.clientWidth - 440) + "px";
  p.style.top = window.scrollY + r.bottom + 6 + "px";
}


function wireHead() {
  $("head").querySelectorAll(".grip").forEach((g) => g.onmousedown = (ev) => {
    ev.preventDefault(); ev.stopPropagation();
    const k = g.parentElement.dataset.k, col = $("cols").querySelector(`col[data-k="${k}"]`);
    const x0 = ev.clientX, w0 = widthOf(k);
    g.classList.add("drag");
    const move = (e) => { userWidth[k] = Math.max(40, w0 + e.clientX - x0); col.style.width = userWidth[k] + "px"; };
    const up = () => { g.classList.remove("drag"); document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); store.set("widths", userWidth); };
    document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
  });
  $("head").querySelectorAll("th").forEach((th) => th.onclick = (ev) => {
    if (ev.target.classList.contains("grip")) return;
    const k = th.dataset.k; if (k === "rank") return;
    if (state.sort === k) state.asc = !state.asc; else { state.sort = k; state.asc = !COLS[k].num; }
    render();
  });
}

function colPanel() {
  const on = visible || analysis().cols;
  $("colPanel").innerHTML = Object.keys(COLS).filter((k) => !COLS[k].fixed && !COLS[k].always).map((k) => {
    const c = COLS[k], off = !usable(k);
    const why = c.base && state.base == null ? " — karşılaştırma yılı seçin" : off ? " — bu düzeyde yok" : "";
    return `<label class="${off ? "dis" : ""}"><input type="checkbox" data-k="${k}" ${on.includes(k) ? "checked" : ""} ${off ? "disabled" : ""}>${c.t}${why}</label>`;
  }).join("") + `<label><input type="checkbox" id="colDefault" ${visible ? "" : "checked"}>Görünüme göre (varsayılan)</label>`;
  $("colPanel").querySelectorAll("input[data-k]").forEach((cb) => cb.onchange = () => {
    const cur = new Set(visible || analysis().cols);
    cb.checked ? cur.add(cb.dataset.k) : cur.delete(cb.dataset.k);
    visible = [...cur]; store.set("cols", visible); colPanel(); render();
  });
  $("colDefault").onchange = (e) => { visible = e.target.checked ? null : [...analysis().cols]; store.set("cols", visible); colPanel(); render(); };
}

function fillDistricts() {
  const opts = ['<option value="-1">Tümü</option>'];
  DATA.districts.forEach((d, i) => { if (state.prov >= 0 && d[2] === state.prov) opts.push(`<option value="${i}">${d[1]}</option>`); });
  $("dist").innerHTML = opts.join("");
  $("dist").disabled = state.prov < 0;
  state.dist = -1;
  fillSettlements();
}

function fillSettlements() {
  const seen = new Map();
  if (state.level === "mahalle" && state.dist >= 0)
    for (const u of DATA.units) if (u[2] === state.dist && u[5] >= 0 && (u[0] === "mahalle" || u[0] === "koy")) seen.set(u[5], DATA.settlements[u[5]]);
  const opts = [...seen].sort((a, b) => a[1].localeCompare(b[1], "tr"));
  $("settle").innerHTML = '<option value="-1">Tümü</option>' + opts.map(([i, n]) => `<option value="${i}">${n}</option>`).join("");
  $("settle").disabled = !opts.length;
  state.settle = -1;
}

function fillYears() {
  const lv = LEVELS.find((l) => l.key === state.level).levels;
  const first = 0, last = DATA.years.length - 1;
  const ys = DATA.years.map((y, i) => i).filter((i) => i >= first);
  if (state.year == null || state.year < first) state.year = last;
  if (state.base != null && state.base < first) state.base = null;
  if (analysis().base && state.base == null) state.base = Math.max(first, state.year - 5);
  $("year").innerHTML = ys.map((i) => `<option value="${i}" ${i === state.year ? "selected" : ""}>${DATA.years[i]}</option>`).join("");
  $("base").innerHTML = '<option value="">—</option>' + ys.map((i) => `<option value="${i}" ${i === state.base ? "selected" : ""}>${DATA.years[i]}</option>`).join("");
}

function setAnalysis(key) {
  state.view = key;
  $("view").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x.dataset.k === key));
  state.asc = false; state.limit = PAGE;
  fillYears();  // sets a comparison year first when the analysis needs one
  // a ratio has no % change: the change view ranks by the change in points instead
  state.sort = [analysis().sort, analysis().base ? "change" : "value", "value"].find(usable);
  colPanel(); render();
}

async function main() {
  $("summary").textContent = "Veri yükleniyor…";
  DATA = await (await fetch("../public/nufus_birimler.json?v=9")).json();
  DATA.units.forEach((u, i) => UIDX.set(u, i));
  totals();
  $("level").innerHTML = LEVELS.map((l) => `<button data-k="${l.key}" class="${l.key === state.level ? "on" : ""}">${l.label}</button>`).join("");
  $("level").querySelectorAll("button").forEach((b) => b.onclick = () => {
    state.level = b.dataset.k; state.limit = PAGE;
    $("level").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    if (ind().lv && !ind().lv.includes(state.level)) { state.indicator = "total"; $("indicator").value = "total"; totals(); }
    fillYears(); fillSettlements();
    state.sort = usable(analysis().sort) ? analysis().sort : "value";
    colPanel(); render();
  });
  const groups = [...new Set(INDICATORS.map((x) => x.group))];
  $("indicator").innerHTML = groups.map((g) => `<optgroup label="${g}">` + INDICATORS.filter((x) => x.group === g).map((a) => `<option value="${a.key}">${a.label}</option>`).join("") + "</optgroup>").join("");
  $("indicator").onchange = (e) => {
    state.indicator = e.target.value; state.limit = PAGE;
    // an indicator published only for some levels takes the page to the finest of them
    const lvs = ind().lv;
    if (lvs && !lvs.includes(state.level)) {
      state.level = lvs[lvs.length - 1];
      $("level").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x.dataset.k === state.level));
      fillYears(); fillSettlements();
    }
    // a new indicator opens on its latest year (voter profiles end in 2023, the rest in 2025)
    const lv = LEVELS.find((l) => l.key === state.level).levels;
    const has = (yi) => DATA.units.some((u) => lv.includes(u[0]) && indAt(u, yi) != null);
    {
      for (let yi = DATA.years.length - 1; yi >= 0; yi--) if (has(yi)) { state.year = yi; break; }
      if (state.base != null && !has(state.base)) state.base = null;
      fillYears();
    }
    totals();
    state.sort = [analysis().sort, analysis().base ? "change" : "value", "value"].find(usable);
    colPanel(); render();
  };
  $("view").innerHTML = VIEWS.map((v) => `<button data-k="${v.key}" class="${v.key === state.view ? "on" : ""}">${v.label}</button>`).join("");
  $("view").querySelectorAll("button").forEach((b) => b.onclick = () => setAnalysis(b.dataset.k));
  $("prov").innerHTML = '<option value="-1">Tümü</option>' + DATA.provinces.map((p, i) => [p[1], i]).sort((a, b) => a[0].localeCompare(b[0], "tr")).map(([n, i]) => `<option value="${i}">${n}</option>`).join("");
  $("prov").onchange = (e) => { state.prov = +e.target.value; state.limit = PAGE; fillDistricts(); render(); };
  $("dist").onchange = (e) => { state.dist = +e.target.value; state.limit = PAGE; fillSettlements(); render(); };
  $("settle").onchange = (e) => { state.settle = +e.target.value; state.limit = PAGE; render(); };
  $("year").onchange = (e) => { state.year = +e.target.value; render(); };
  $("base").onchange = (e) => {
    state.base = e.target.value === "" ? null : +e.target.value;
    if (!usable(state.sort)) state.sort = "value";
    colPanel(); render();
  };
  $("q").oninput = (e) => { state.q = e.target.value; state.limit = PAGE; render(); };
  const numv = (x) => (x === "" ? null : Math.max(0, +x));
  $("minPop").oninput = (e) => { state.min = numv(e.target.value); state.limit = PAGE; render(); };
  $("maxPop").oninput = (e) => { state.max = numv(e.target.value); state.limit = PAGE; render(); };
  $("colBtn").onclick = (e) => { e.stopPropagation(); $("colPanel").hidden = !$("colPanel").hidden; };
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".colmenu")) $("colPanel").hidden = true;
    if (!e.target.closest(".pop")) $("pop").hidden = true;
  });
  $("notesLink").onclick = (e) => { e.preventDefault(); e.stopPropagation(); showPop(e.target, "Notlar", NOTES); };
  $("resetCols").onclick = () => { userWidth = {}; store.set("widths", userWidth); render(); };
  fillDistricts(); fillYears(); colPanel(); render();
}
main();
