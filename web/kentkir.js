// Urban/rural review page. Rows come as arrays keyed by data.keys; the user's decisions
// ({area_id: {s: class, y: settlement, n: note}}) are loaded from kullanici_karar.json and
// saved back through POST /karar, with localStorage holding anything not yet accepted.
"use strict";

const DATA_URL = "../public/kentkir_kontrol.json";
const DEC_URL = "../scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json";
const PENDING_KEY = "kentkir.pending";
const PAGE = 250;
const CLASSES = ["İl Merkezi", "İlçe Merkezi", "Kentsel Belde", "Kasaba", "Kırsal Belde", "Köy"];
const URBAN = new Set(["İl Merkezi", "İlçe Merkezi", "Kentsel Belde"]);
const SOURCES = ["TÜİK", "AATOPLU", "DEGURBA", "Bina"];
const IH = { uyumlu: "Uyumlu", hafif: "Hafif", cok: "Çok ihtilaflı" };

let K = {}, rows = [], parties = [], dec = {}, pending = {};
let shown = [], limit = PAGE, sortKey = null, sortAsc = true;
const selIl = new Set(), selIlce = new Set();
const f = { ih: new Set(["uyumlu", "hafif", "cok"]), on: new Set(CLASSES), kr: new Set(["bos", "dolu"]), kurum: false,
            groups: new Set(["temel", "kaynak", "not"]) };

const $ = (id) => document.getElementById(id);
const fmt = (v, d = 0) => v == null || v === "" ? "" : Number(v).toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const fold = (s) => String(s || "").toLocaleLowerCase("tr").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ı/g, "i");
const get = (r, k) => r[K[k]];
const kentKir = (s) => (s ? (URBAN.has(s) ? "KENT" : "KIR") : "");

// --- columns: [key, header, group, render kind, digits]
const COLS = () => [
  ["il", "İl", "id", "t"], ["ilce", "İlçe", "id", "t"], ["yer", "Yerleşim", "id", "t"], ["semt", "Semt", "semt", "t"], ["ad", "Mahalle / köy", "id", "name"], ["tur", "Tür", "id", "c"],
  ["n", "Nüfus 2025", "temel", "n", 0], ["g", "Değişim 2013-25 %", "temel", "n", 1], ["dens", "Kişi / km²", "temel", "n", 0],
  ["leke", "Merkez lekesi %", "temel", "n", 0], ["kpb", "Konut / bina", "temel", "n", 2],
  ["src0", "TÜİK", "kaynak", "src"], ["src1", "AATOPLU", "kaynak", "src"], ["src2", "DEGURBA", "kaynak", "src"], ["src3", "Bina", "kaynak", "src"],
  ["ih", "İhtilaf", "kaynak", "ih"], ["os", "Öneri", "kaynak", "oneri"],
  ["u_s", "Sınıf (senin)", "you", "sel"], ["u_kk", "Kent/Kır", "you", "kk"], ["u_y", "Yerleşim (senin)", "you", "y"], ["u_n", "Not (senin)", "you", "nt"],
  ["not", "Otomatik not", "not", "note"],
  ["n0", "Nüfus 2013", "nufus", "n", 0], ["area", "Yüzölçümü km²", "nufus", "n", 2], ["kur", "Kuruluş", "nufus", "c"], ["kurum", "Kurum", "nufus", "kurum"],
  ["er", "Erkek %", "yas", "n", 1], ["u17", "0-17 %", "yas", "n", 1], ["o65", "65+ %", "yas", "n", 1], ["med", "Ortanca yaş", "yas", "n", 1], ["uni", "Üniversiteli %", "yas", "n", 1],
  ["hh", "Hane", "konut", "n", 0], ["hs", "Hane büyüklüğü", "konut", "n", 2], ["dw", "Konut", "konut", "n", 0], ["bl", "Bina (Microsoft)", "konut", "n", 0],
  ["kpbl", "Kişi / bina", "konut", "n", 1], ["hpb", "Hane / bina", "konut", "n", 2], ["prs", "Parsel", "konut", "n", 0], ["yaz", "Yazlık %", "konut", "n", 1],
  ["k23", "Kayıtlı", "secim", "n", 0], ["g23", "Geçerli", "secim", "n", 0], ["kn", "Kayıtlı / nüfus %", "secim", "n", 1],
  ...parties.map(([p, short]) => [p, short, "secim", "party", 1]),
  ["stat", "TÜİK statü", "kaynakx", "t"], ["aat", "AATOPLU", "kaynakx", "t"], ["deg", "DEGURBA", "kaynakx", "t"], ["bina", "Bina analizi", "kaynakx", "t"],
];
const GROUPS = { id: "Yer", semt: "Semt", temel: "Temel", kaynak: "Kaynaklar ve öneri", you: "Senin kararın", not: "Not", nufus: "Nüfus ayrıntı",
                 yas: "Yaş · eğitim (Endeksa 2024)", konut: "Hane · konut · bina", secim: "Seçim 2023", kaynakx: "Kaynak ayrıntı" };
const TOGGLE = ["semt", "temel", "kaynak", "not", "nufus", "yas", "konut", "secim", "kaynakx"];
const visibleCols = () => COLS().filter((c) => c[2] === "id" || c[2] === "you" || f.groups.has(c[2]));

// --- decisions
const decOf = (id) => pending[id] || dec[id] || {};
function setDecision(id, patch) {
  const d = { ...decOf(id), ...patch };
  for (const k of Object.keys(d)) if (!d[k]) delete d[k];
  pending[id] = d;
  try { localStorage.setItem(PENDING_KEY, JSON.stringify(pending)); } catch (e) { /* private window */ }
  scheduleSave();
}
let saveTimer = null;
function scheduleSave() { clearTimeout(saveTimer); saveTimer = setTimeout(flush, 500); status("kaydediliyor…", ""); }
async function flush() {
  const batch = pending;
  if (!Object.keys(batch).length) return;
  try {
    const r = await fetch("/karar", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(batch) });
    if (!r.ok) throw new Error(r.status);
    const res = await r.json();
    for (const [id, d] of Object.entries(batch)) {
      if (Object.keys(d).length) dec[id] = d; else delete dec[id];
      if (pending[id] === d) delete pending[id];
    }
    try { localStorage.setItem(PENDING_KEY, JSON.stringify(pending)); } catch (e) { /* ignore */ }
    summary();
    totals();
    status(`kaydedildi ✓ · ${fmt(res.kayit)} karar`, "ok");
  } catch (e) {
    status("sunucuya yazılamadı, tarayıcıda tutuluyor (serve.py açık mı?)", "err");
  }
}
function status(t, cls) { const s = $("save"); if (s) { s.textContent = t; s.className = cls; } }

// --- filters
function buildDrop(el, title, items, sel, onChange) {
  const btn = el.querySelector("button");
  let panel = null;
  const label = () => { btn.textContent = sel.size === 0 || sel.size === items().length ? `${title}: tümü` : `${title}: ${sel.size} seçili`; };
  const close = (ev) => { if (panel && !el.contains(ev.target)) { panel.remove(); panel = null; document.removeEventListener("mousedown", close); } };
  btn.onclick = () => {
    if (panel) { panel.remove(); panel = null; return; }
    panel = document.createElement("div");
    panel.className = "panel";
    panel.innerHTML = `<div class="row"><button data-a="all">Tümünü seç</button><button data-a="none">Tümünü kaldır</button></div>
      <input class="q" placeholder="ara"><div class="list"></div>`;
    const list = panel.querySelector(".list"), q = panel.querySelector(".q");
    const draw = () => {
      const qq = fold(q.value);
      list.innerHTML = items().filter(([v]) => !qq || fold(v).includes(qq)).map(([v, n]) =>
        `<label><input type="checkbox" value="${esc(v)}" ${sel.has(v) ? "checked" : ""}>${esc(v)}<small>${fmt(n)}</small></label>`).join("");
    };
    draw();
    q.oninput = draw;
    list.onchange = (ev) => { ev.target.checked ? sel.add(ev.target.value) : sel.delete(ev.target.value); label(); onChange(); };
    panel.querySelector(".row").onclick = (ev) => {
      const a = ev.target.dataset.a;
      if (!a) return;
      const vis = [...list.querySelectorAll("input")].map((i) => i.value);
      if (a === "all") vis.forEach((v) => sel.add(v)); else vis.forEach((v) => sel.delete(v));
      draw(); label(); onChange();
    };
    el.appendChild(panel);
    setTimeout(() => document.addEventListener("mousedown", close), 0);
    q.focus();
  };
  label();
  return label;
}
function chips(el, items, set, onChange) {
  el.innerHTML = items.map(([v, t, color]) =>
    `<label class="chip ${set.has(v) ? "on" : ""}"><input type="checkbox" value="${v}" ${set.has(v) ? "checked" : ""}>${color ? `<i style="background:${color}"></i>` : ""}${t}</label>`).join("");
  el.onchange = (ev) => {
    const i = ev.target;
    i.checked ? set.add(i.value) : set.delete(i.value);
    i.parentElement.classList.toggle("on", i.checked);
    onChange();
  };
}
function counts(key, pred) {
  const m = new Map();
  for (const r of rows) if (!pred || pred(r)) m.set(get(r, key), (m.get(get(r, key)) || 0) + 1);
  return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0], "tr"));
}

function apply() {
  const q = fold($("q").value), nMin = +$("nMin").value || 0;
  shown = rows.filter((r) => {
    if (selIl.size && !selIl.has(get(r, "il"))) return false;
    if (selIlce.size && !selIlce.has(`${get(r, "il")} · ${get(r, "ilce")}`)) return false;
    if (!f.ih.has(get(r, "ih"))) return false;
    if (!f.on.has(get(r, "os"))) return false;
    if (f.kurum && !get(r, "kurum")) return false;
    const has = !!decOf(get(r, "id")).s;
    if (!f.kr.has(has ? "dolu" : "bos")) return false;
    if (get(r, "n") < nMin) return false;
    if (q && !fold(`${get(r, "ad")} ${get(r, "yer")} ${get(r, "ilce")} ${get(r, "semt")}`).includes(q)) return false;
    return true;
  });
  if (sortKey) {
    const val = (r) => sortKey === "u_s" ? decOf(get(r, "id")).s || "" : sortKey.startsWith("src") ? get(r, "oy")[+sortKey[3]] : get(r, sortKey);
    shown.sort((a, b) => {
      const x = val(a), y = val(b);
      if (x == null || x === "") return 1;
      if (y == null || y === "") return -1;
      const c = typeof x === "number" ? x - y : String(x).localeCompare(String(y), "tr");
      return sortAsc ? c : -c;
    });
  }
  limit = PAGE;
  summary();
  render();
}

// --- live totals by level: the user's decision where given, else the suggestion
const LEVELS = { tr: "Türkiye", il: "İl", ilce: "İlçe", yer: "Yerleşim", semt: "Semt" };
let lvl = "il", lvlSort = "n";
function levelKey(r) {
  if (lvl === "tr") return "Türkiye";
  if (lvl === "il") return get(r, "il");
  if (lvl === "ilce") return `${get(r, "il")} · ${get(r, "ilce")}`;
  return `${get(r, "il")} · ${get(r, "ilce")} · ${get(r, lvl)}`;
}
function totals() {
  const box = $("tot");
  if (!box.open) return;
  const m = new Map();
  for (const r of rows) {
    if (selIl.size && !selIl.has(get(r, "il"))) continue;
    if (selIlce.size && !selIlce.has(`${get(r, "il")} · ${get(r, "ilce")}`)) continue;
    const k = levelKey(r), n = get(r, "n"), s = decOf(get(r, "id")).s;
    const t = m.get(k) || { n: 0, uk: 0, ur: 0, ok: 0, mixed: 0 };
    t.n += n;
    if (s) URBAN.has(s) ? (t.uk += n) : (t.ur += n);
    if (URBAN.has(get(r, "os"))) t.ok += n;
    if (URBAN.has(s || get(r, "os"))) t.mixed += n;
    m.set(k, t);
  }
  const list = [...m.entries()].map(([k, t]) => ({ k, ...t, done: t.uk + t.ur, pm: t.mixed / t.n * 100, po: t.ok / t.n * 100 }));
  const key = { n: (x) => -x.n, pm: (x) => -x.pm, d: (x) => -Math.abs(x.pm - x.po), done: (x) => x.done / x.n, k: null }[lvlSort];
  list.sort(key ? (a, b) => key(a) - key(b) : (a, b) => a.k.localeCompare(b.k, "tr"));
  const pct = (v) => fmt(v, 1);
  const shownList = list.slice(0, 300);
  $("totBody").innerHTML = `<table><thead><tr>
      <th data-s="k">${LEVELS[lvl]}</th><th data-s="n">Nüfus</th><th data-s="done">Karar verilen nüfus</th>
      <th>Kent (senin)</th><th>Kır (senin)</th><th data-s="pm" title="Kararı olmayan yerde öneri">Kent % (senin + öneri)</th>
      <th>Kent % (öneri)</th><th data-s="d">Fark</th></tr></thead><tbody>${
    shownList.map((x) => `<tr><td>${esc(x.k)}</td><td class="num">${fmt(x.n)}</td>
      <td class="num">${fmt(x.done / x.n * 100, 0)} %</td><td class="num">${fmt(x.uk)}</td><td class="num">${fmt(x.ur)}</td>
      <td class="num"><b>${pct(x.pm)}</b></td><td class="num">${pct(x.po)}</td>
      <td class="num" style="color:${x.pm - x.po > 0.05 ? "var(--kent)" : x.pm - x.po < -0.05 ? "var(--kir)" : "var(--mut)"}">${x.done ? (x.pm - x.po > 0 ? "+" : "") + pct(x.pm - x.po) : ""}</td></tr>`).join("")
  }</tbody></table>${list.length > 300 ? `<div class="more">ilk 300 / ${fmt(list.length)}</div>` : ""}`;
}

function summary() {
  let pop = 0, done = 0, kent = 0, kir = 0, oKent = 0;
  const ih = { uyumlu: 0, hafif: 0, cok: 0 };
  for (const r of shown) {
    const n = get(r, "n"), s = decOf(get(r, "id")).s;
    pop += n; ih[get(r, "ih")]++;
    if (URBAN.has(get(r, "os"))) oKent += n;
    if (s) { done++; URBAN.has(s) ? (kent += n) : (kir += n); }
  }
  const pct = (a, b) => (b ? fmt((a / b) * 100, 1) + " %" : "–");
  $("sum").innerHTML = `
    <span><b>${fmt(shown.length)}</b>yer · ${fmt(pop)} kişi</span>
    <span><b>${fmt(done)}</b>karar verilen (${pct(done, shown.length)})</span>
    <span><b>${pct(kent, kent + kir)}</b>kent payı (senin, karar verilen nüfus)</span>
    <span><b>${pct(oKent, pop)}</b>kent payı (öneri)</span>
    <span><b><span class="ih uyumlu">${fmt(ih.uyumlu)}</span> · <span class="ih hafif">${fmt(ih.hafif)}</span> · <span class="ih cok">${fmt(ih.cok)}</span></b>uyumlu · hafif · çok ihtilaflı</span>
    <div id="save" class="${Object.keys(pending).length ? "err" : ""}">${Object.keys(pending).length ? "gönderilmemiş karar var" : ""}</div>`;
}

function head() {
  const cols = visibleCols();
  let grp = "", prev = null, span = 0;
  const cells = [];
  for (const c of cols) {
    if (c[2] !== prev) { if (prev) cells.push([prev, span]); prev = c[2]; span = 0; }
    span++;
  }
  cells.push([prev, span]);
  grp = cells.map(([g, n]) => `<th colspan="${n}" class="sep" style="${g === "you" ? "color:#e8d27a" : ""}">${GROUPS[g]}</th>`).join("");
  const pc = Object.fromEntries(parties.map(([p, , fill]) => [p, fill]));
  const line = cols.map((c, i) => {
    const st = c[3] === "party" ? `style="background:#${pc[c[0]]};color:${["FFFF00", "00B0F0"].includes(pc[c[0]]) ? "#111" : "#fff"}"` : "";
    const sep = i === 0 || cols[i - 1][2] !== c[2] ? "sep" : "";
    const so = sortKey === c[0] ? `sorted ${sortAsc ? "asc" : ""}` : "";
    return `<th data-k="${c[0]}" class="${sep} ${so}" ${st}>${c[1]}</th>`;
  }).join("");
  $("th").innerHTML = `<tr class="grp">${grp}</tr><tr class="cols">${line}</tr>`;
}

function cell(r, c, i, cols) {
  const [k, , g, kind, d] = c;
  const sep = i === 0 || cols[i - 1][2] !== g ? " sep" : "";
  const id = get(r, "id"), my = decOf(id);
  switch (kind) {
    case "t": return `<td class="${sep}">${esc(get(r, k))}</td>`;
    case "c": return `<td class="c${sep}">${esc(get(r, k))}</td>`;
    case "n": return `<td class="num${sep}">${fmt(get(r, k), d)}</td>`;
    case "party": return `<td class="num${sep}">${fmt(get(r, k), d)}</td>`;
    case "name": {
      const w = parties.find(([p]) => p === get(r, "win"));
      const bg = w ? `#${w[2]}` : get(r, "win") ? "#7f7f7f" : "transparent";
      const fg = w && ["FFFF00", "00B0F0"].includes(w[2]) ? "#111" : "#fff";
      return `<td class="name${sep}" style="background:${bg};color:${fg}" title="${esc(get(r, "win") || "seçim eşleşmedi")}">${esc(get(r, k))}</td>`;
    }
    case "src": {
      const o = get(r, "oy")[+k[3]];
      const full = [get(r, "stat"), get(r, "aat"), get(r, "deg"), get(r, "bina")][+k[3]];
      return `<td class="c${sep}" title="${esc(full)}"><span class="pill ${o === "-" ? "N" : o}">${o === "K" ? "kent" : o === "R" ? "kır" : "belde"}</span></td>`;
    }
    case "ih": return `<td class="c${sep}"><span class="ih ${get(r, "ih")}">${IH[get(r, "ih")]}</span></td>`;
    case "oneri": return `<td class="oneri${sep}" style="color:${URBAN.has(get(r, "os")) ? "var(--kent)" : "var(--kir)"}">${esc(get(r, "os"))}</td>`;
    case "sel": return `<td class="you${sep}"><select data-id="${id}" data-f="s" class="${my.s ? "set" : ""}"><option value="">—</option>${
      CLASSES.map((x) => `<option ${my.s === x ? "selected" : ""}>${x}</option>`).join("")}</select><button class="acc" data-acc="${id}" title="Öneriyi yaz: ${esc(get(r, "os"))}">✓</button></td>`;
    case "kk": { const t = kentKir(my.s); return `<td class="you c"><span class="kk ${t}">${t}</span></td>`; }
    case "y": return `<td class="you"><input class="y" data-id="${id}" data-f="y" value="${esc(my.y)}" placeholder="${esc(get(r, "yer"))}"></td>`;
    case "nt": return `<td class="you"><input class="n" data-id="${id}" data-f="n" value="${esc(my.n)}"></td>`;
    case "note": { const t = get(r, "not") || ""; return `<td class="note${sep}" title="${esc(t)}">${t.startsWith("KURUM") ? `<span class="kurum">${esc(t)}</span>` : esc(t)}</td>`; }
    case "kurum": return `<td class="${sep}"><span class="kurum">${esc(get(r, k))}</span></td>`;
  }
  return "<td></td>";
}

function render() {
  head();
  const cols = visibleCols();
  $("tb").innerHTML = shown.slice(0, limit).map((r) => `<tr data-id="${get(r, "id")}">${cols.map((c, i) => cell(r, c, i, cols)).join("")}</tr>`).join("");
  $("more").innerHTML = shown.length > limit
    ? `${fmt(limit)} / ${fmt(shown.length)} gösteriliyor · <button id="moreBtn">${fmt(PAGE)} daha</button>`
    : shown.length ? `${fmt(shown.length)} yer` : "Bu filtrede yer yok.";
  const mb = $("moreBtn");
  if (mb) mb.onclick = () => { limit += PAGE; render(); };
}

function wire() {
  $("th").onclick = (ev) => {
    const k = ev.target.dataset && ev.target.dataset.k;
    if (!k) return;
    if (sortKey === k) sortAsc = !sortAsc; else { sortKey = k; sortAsc = !["n", "g", "dens", "leke", "kpb"].includes(k) && !parties.some(([p]) => p === k); }
    apply();
  };
  $("tb").addEventListener("change", (ev) => {
    const t = ev.target, id = t.dataset.id;
    if (!id) return;
    setDecision(id, { [t.dataset.f]: t.value.trim() });
    if (t.dataset.f === "s") {
      t.classList.toggle("set", !!t.value);
      const kk = t.closest("tr").querySelector(".kk");
      if (kk) { kk.textContent = kentKir(t.value); kk.className = `kk ${kentKir(t.value)}`; }
    }
  });
  $("tb").addEventListener("click", (ev) => {
    const a = ev.target.dataset && ev.target.dataset.acc;
    if (a) {
      const r = rows.find((x) => get(x, "id") === a);
      setDecision(a, { s: get(r, "os") });
      const s = ev.target.previousElementSibling;
      s.value = get(r, "os"); s.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }
    const td = ev.target.closest("td.note");
    if (td) td.classList.toggle("open");
  });
  $("bulk").onclick = () => {
    const todo = shown.filter((r) => !decOf(get(r, "id")).s);
    if (!todo.length) return;
    if (!confirm(`Görünen ve kararı boş ${fmt(todo.length)} yere öneri yazılsın mı? (${fmt(todo.reduce((a, r) => a + get(r, "n"), 0))} kişi)`)) return;
    for (const r of todo) pending[get(r, "id")] = { ...decOf(get(r, "id")), s: get(r, "os") };
    try { localStorage.setItem(PENDING_KEY, JSON.stringify(pending)); } catch (e) { /* ignore */ }
    flush().then(apply);
  };
  let t = null;
  $("q").oninput = $("nMin").oninput = () => { clearTimeout(t); t = setTimeout(apply, 250); };
}

async function main() {
  $("tb").innerHTML = `<tr><td class="muted" style="padding:20px">Yükleniyor… (19 MB)</td></tr>`;
  const data = await (await fetch(DATA_URL)).json();
  K = Object.fromEntries(data.keys.map((k, i) => [k, i]));
  rows = data.rows; parties = data.parties;
  try { const r = await fetch(DEC_URL, { cache: "no-store" }); if (r.ok) dec = await r.json(); } catch (e) { /* none yet */ }
  try { pending = JSON.parse(localStorage.getItem(PENDING_KEY) || "{}"); } catch (e) { pending = {}; }

  const onIl = () => { drawIlce(); apply(); totals(); };
  buildDrop($("dIl"), "İl", () => counts("il"), selIl, onIl);
  const ilceItems = () => {
    const m = new Map();
    for (const r of rows) if (!selIl.size || selIl.has(get(r, "il"))) { const k = `${get(r, "il")} · ${get(r, "ilce")}`; m.set(k, (m.get(k) || 0) + 1); }
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0], "tr"));
  };
  const drawIlce = buildDrop($("dIlce"), "İlçe", ilceItems, selIlce, () => { apply(); totals(); });
  $("lvl").innerHTML = Object.entries(LEVELS).map(([k, t]) => `<option value="${k}" ${k === lvl ? "selected" : ""}>${t}</option>`).join("");
  $("lvl").onchange = (ev) => { lvl = ev.target.value; totals(); };
  $("tot").ontoggle = totals;
  $("totBody").onclick = (ev) => { const s = ev.target.dataset && ev.target.dataset.s; if (s) { lvlSort = s; totals(); } };
  chips($("cIh"), [["uyumlu", "Uyumlu", "#6cc38a"], ["hafif", "Hafif", "#e8b64c"], ["cok", "Çok", "#ef7d73"]], f.ih, apply);
  chips($("cOn"), CLASSES.map((c) => [c, c]), f.on, apply);
  const kr = new Set([...f.kr, ...(f.kurum ? ["kurum"] : [])]);
  chips($("cKr"), [["bos", "Bekleyen"], ["dolu", "Verilmiş"], ["kurum", "Yalnız kurum"]], kr, () => {
    f.kr = new Set([...kr].filter((x) => x !== "kurum")); f.kurum = kr.has("kurum"); apply();
  });
  chips($("cGr"), TOGGLE.map((g) => [g, GROUPS[g].split(" (")[0]]), f.groups, render);
  wire();
  apply();
  if (Object.keys(pending).length) flush();
}
main();
