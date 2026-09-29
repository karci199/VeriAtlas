// Urban/rural review page. Rows come as arrays keyed by data.keys; the user's decisions
// ({area_id: {s: class, y: settlement, n: note}}) are loaded from kullanici_karar.json and
// saved back through POST /karar, with localStorage holding anything not yet accepted.
// Tabs: province, district, settlement and semt summaries (the user's decision where given,
// else the suggestion) drill down into the neighbourhood/village table.
"use strict";

const DATA_URL = "../public/kentkir_kontrol.json";
const DEC_URL = "../scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json";
const PENDING_KEY = "kentkir.pending";
const PAGE = 250;
const CLASSES = ["İl Merkezi", "İlçe Merkezi", "Kentsel Belde", "Kasaba", "Kırsal Belde", "Köy"];
const URBAN = new Set(["İl Merkezi", "İlçe Merkezi", "Kentsel Belde"]);
const IH = { uyumlu: "uyumlu", hafif: "hafif", cok: "çok" };
const TABS = { il: "İller", ilce: "İlçeler", yer: "Yerleşimler", semt: "Semtler", mah: "Mahalle / köy" };

let K = {}, rows = [], parties = [], dec = {}, pending = {};
let tab = "il", shown = [], limit = PAGE, sortKey = null, sortAsc = true, sumSort = "n", sumAsc = false;
let focus = null; // {k: "yer" | "semt", v, label} from a summary drill-down
const selIl = new Set(), selIlce = new Set();
const f = { ih: new Set(["uyumlu", "hafif", "cok"]), on: new Set(CLASSES), kr: new Set(["bos", "dolu"]), kurum: false,
            groups: new Set(["temel", "kaynak", "not", "you2"]) };

const $ = (id) => document.getElementById(id);
const fmt = (v, d = 0) => v == null || v === "" ? "" : Number(v).toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const fold = (s) => String(s || "").toLocaleLowerCase("tr").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ı/g, "i");
const get = (r, k) => r[K[k]];
const kentKir = (s) => (s ? (URBAN.has(s) ? "KENT" : "KIR") : "");
const ilceKey = (r) => `${get(r, "il")} · ${get(r, "ilce")}`;

// --- neighbourhood table columns: [key, header, group, render kind, digits]
const COLS = () => [
  ["il", "İl", "id", "t"], ["ilce", "İlçe", "id", "t"], ["yer", "Yerleşim", "id", "t"], ["semt", "Semt", "semt", "t"], ["ad", "Mahalle / köy", "id", "name"],
  ["n", "Nüfus", "temel", "n", 0], ["g", "2013→25 %", "temel", "g", 1], ["dens", "Kişi/km²", "temel", "n", 0],
  ["leke", "Merkez lekesi %", "temel", "n", 0], ["kpb", "Konut/bina", "temel", "n", 2],
  ["src0", "TÜİK", "kaynak", "src"], ["src1", "AATOPLU", "kaynak", "src"], ["src2", "DEGURBA", "kaynak", "src"], ["src3", "Bina", "kaynak", "src"],
  ["ih", "İhtilaf", "kaynak", "ih"], ["os", "Öneri", "kaynak", "oneri"],
  ["not", "Otomatik not", "not", "note"],
  ["n0", "Nüfus 2013", "nufus", "n", 0], ["area", "Alan km²", "nufus", "n", 2], ["kur", "Kuruluş", "nufus", "c"], ["tur", "Tür", "nufus", "c"],
  ["er", "Erkek %", "yas", "n", 1], ["u17", "0-17 %", "yas", "n", 1], ["o65", "65+ %", "yas", "n", 1], ["med", "Ortanca yaş", "yas", "n", 1], ["uni", "Üniversiteli %", "yas", "n", 1],
  ["hh", "Hane", "konut", "n", 0], ["hs", "Hane büy.", "konut", "n", 2], ["dw", "Konut", "konut", "n", 0], ["bl", "Bina (MS)", "konut", "n", 0],
  ["kpbl", "Kişi/bina", "konut", "n", 1], ["hpb", "Hane/bina", "konut", "n", 2], ["prs", "Parsel", "konut", "n", 0], ["yaz", "Yazlık %", "konut", "n", 1],
  ["k23", "Kayıtlı", "secim", "n", 0], ["g23", "Geçerli", "secim", "n", 0], ["kn", "Kayıtlı/nüfus %", "secim", "n", 1],
  ...parties.map(([p, short]) => [p, short, "secim", "party", 1]),
  ["stat", "TÜİK statü", "kaynakx", "t"], ["aat", "AATOPLU", "kaynakx", "t"], ["deg", "DEGURBA", "kaynakx", "t"], ["bina", "Bina analizi", "kaynakx", "t"],
  ["u_y", "Yerleşim (senin)", "you2", "y"], ["u_n", "Not (senin)", "you2", "nt"],
  ["u_s", "Karar", "you", "sel"],
];
const GROUPS = { id: "", semt: "", temel: "Temel", kaynak: "Kaynaklar ve öneri", not: "", nufus: "Nüfus", yas: "Yaş · eğitim (2024)",
                 konut: "Hane · konut · bina", secim: "Seçim 2023", kaynakx: "Kaynak ayrıntı", you2: "Senin", you: "" };
const TOGGLE = [["semt", "Semt"], ["temel", "Temel"], ["kaynak", "Kaynaklar"], ["not", "Not"], ["nufus", "Nüfus"], ["yas", "Yaş · eğitim"],
                ["konut", "Hane · konut · bina"], ["secim", "Seçim 2023"], ["kaynakx", "Kaynak ayrıntı"], ["you2", "Yerleşim/not (senin)"]];
const visibleCols = () => COLS().filter((c) => c[2] === "id" || c[2] === "you" || f.groups.has(c[2]));

// --- decisions
const decOf = (id) => pending[id] || dec[id] || {};
const classOf = (r) => decOf(get(r, "id")).s || get(r, "os");
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
    cards();
    status(`kaydedildi ✓ · ${fmt(res.kayit)} karar`, "ok");
  } catch (e) {
    status("sunucuya yazılamadı, tarayıcıda tutuluyor (serve.py açık mı?)", "err");
  }
}
function status(t, cls) { const s = $("save"); s.textContent = t; s.className = cls; }

// --- filter widgets
function buildDrop(el, title, items, sel, onChange) {
  const btn = el.querySelector("button");
  let panel = null;
  const label = () => { btn.textContent = sel.size === 0 ? `${title}: tümü` : sel.size === 1 ? [...sel][0] : `${title}: ${sel.size} seçili`; };
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

// rows inside the province/district selection (and the drill-down focus)
function inScope(r) {
  if (selIl.size && !selIl.has(get(r, "il"))) return false;
  if (selIlce.size && !selIlce.has(ilceKey(r))) return false;
  if (focus && get(r, focus.k) !== focus.v) return false;
  return true;
}

// --- summary tabs
function groupKey(r) {
  if (tab === "il") return [get(r, "il")];
  if (tab === "ilce") return [get(r, "il"), get(r, "ilce")];
  return [get(r, "il"), get(r, "ilce"), get(r, tab)];
}
function summaryTable() {
  const q = fold($("q").value), m = new Map();
  for (const r of rows) {
    if (!inScope(r)) continue;
    const key = groupKey(r), k = key.join(" · ");
    if (q && !fold(k).includes(q)) continue;
    const n = get(r, "n"), s = decOf(get(r, "id")).s, ih = get(r, "ih");
    const t = m.get(k) || { key, n: 0, c: 0, ok: 0, mk: 0, done: 0, hafif: 0, cok: 0, open: 0 };
    t.n += n; t.c++;
    if (URBAN.has(get(r, "os"))) t.ok += n;
    if (URBAN.has(s || get(r, "os"))) t.mk += n;
    if (s) t.done += n;
    if (ih !== "uyumlu") { t[ih]++; if (!s) t.open++; }
    m.set(k, t);
  }
  const list = [...m.values()].map((t) => ({ ...t, po: t.ok / t.n * 100, pm: t.mk / t.n * 100, pd: t.done / t.n * 100 }));
  const sk = sumSort;
  list.sort((a, b) => {
    const x = sk === "name" ? a.key.join() : a[sk], y = sk === "name" ? b.key.join() : b[sk];
    const c = typeof x === "string" ? x.localeCompare(y, "tr") : x - y;
    return sumAsc ? c : -c;
  });
  shown = list;
  const names = { il: ["İl"], ilce: ["İl", "İlçe"], yer: ["İl", "İlçe", "Yerleşim"], semt: ["İl", "İlçe", "Semt"] }[tab];
  const H = (k, t, cls = "num") => `<th data-s="${k}" class="${cls} ${sumSort === k ? `sorted ${sumAsc ? "asc" : ""}` : ""}">${t}</th>`;
  $("th").innerHTML = `<tr class="cols">${names.map((n, i) => i === names.length - 1 ? H("name", n, "") : `<th></th>`).join("")}
    ${H("n", "Nüfus")}${H("c", "Yer")}${H("pm", "Kent % (senin + öneri)")}${H("po", "Kent % (öneri)")}
    ${H("pd", "Karar verilen nüfus %")}${H("hafif", "Hafif ihtilaf")}${H("cok", "Çok ihtilaf")}${H("open", "Bekleyen ihtilaf")}</tr>`;
  const bar = (v, cls) => `<span class="bar ${cls}" style="width:${Math.max(0, Math.min(100, v)) * 0.6}px"></span>`;
  $("tb").innerHTML = list.slice(0, limit).map((t) => {
    const d = t.pm - t.po;
    return `<tr class="drill" data-k="${esc(t.key.join("\u0001"))}">${t.key.map((x, i) => `<td class="${i === t.key.length - 1 ? "name2" : "muted"}">${esc(x)}</td>`).join("")}
      <td class="num">${fmt(t.n)}</td><td class="num muted">${fmt(t.c)}</td>
      <td class="num"><span class="cell-bar">${bar(t.pm, "k")}<b>${fmt(t.pm, 1)}</b></span></td>
      <td class="num">${fmt(t.po, 1)}${t.done && Math.abs(d) >= 0.05 ? ` <span class="${d > 0 ? "up" : "down"}">${d > 0 ? "+" : ""}${fmt(d, 1)}</span>` : ""}</td>
      <td class="num"><span class="cell-bar">${bar(t.pd, "d")}${fmt(t.pd, 0)}</span></td>
      <td class="num ${t.hafif ? "warn" : "muted"}">${fmt(t.hafif)}</td><td class="num ${t.cok ? "bad" : "muted"}">${fmt(t.cok)}</td>
      <td class="num ${t.open ? "" : "muted"}">${fmt(t.open)}</td></tr>`;
  }).join("");
  more();
}
function drill(key) {
  const [il, ilce, v] = key.split("\u0001");
  if (tab === "il") { selIl.clear(); selIl.add(il); selIlce.clear(); drawIl(); drawIlce(); setTab("ilce"); return; }
  selIl.clear(); selIl.add(il); selIlce.clear(); selIlce.add(`${il} · ${ilce}`); drawIl(); drawIlce();
  focus = tab === "yer" || tab === "semt" ? { k: tab, v, label: `${tab === "yer" ? "Yerleşim" : "Semt"}: ${v}` } : null;
  setTab("mah");
}

// --- neighbourhood table
function mahTable() {
  const q = fold($("q").value), nMin = +$("nMin").value || 0;
  shown = rows.filter((r) => {
    if (!inScope(r)) return false;
    if (!f.ih.has(get(r, "ih"))) return false;
    if (!f.on.has(get(r, "os"))) return false;
    if (f.kurum && !get(r, "kurum")) return false;
    if (!f.kr.has(decOf(get(r, "id")).s ? "dolu" : "bos")) return false;
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
  renderMah();
}
function headMah(cols) {
  const groups = [];
  for (const c of cols) {
    if (groups.length && groups[groups.length - 1][0] === c[2]) groups[groups.length - 1][1]++;
    else groups.push([c[2], 1]);
  }
  const pc = Object.fromEntries(parties.map(([p, , fill]) => [p, fill]));
  const grp = groups.map(([g, n]) => `<th colspan="${n}" class="sep ${g === "you" ? "you" : ""}">${GROUPS[g]}</th>`).join("");
  const line = cols.map((c, i) => {
    const st = c[3] === "party" ? `style="box-shadow:inset 0 -3px 0 #${pc[c[0]]}"` : "";
    const sep = i === 0 || cols[i - 1][2] !== c[2] ? "sep" : "";
    const so = sortKey === c[0] ? `sorted ${sortAsc ? "asc" : ""}` : "";
    const cls = ["n", "g", "party"].includes(c[3]) ? "num" : "";
    return `<th data-k="${c[0]}" class="${sep} ${so} ${cls} ${c[2] === "you" ? "you" : ""}" ${st}>${c[1]}</th>`;
  }).join("");
  $("th").innerHTML = `<tr class="grp">${grp}</tr><tr class="cols">${line}</tr>`;
}
function cell(r, c, i, cols) {
  const [k, , g, kind, d] = c;
  const sep = i === 0 || cols[i - 1][2] !== g ? " sep" : "";
  const id = get(r, "id"), my = decOf(id);
  switch (kind) {
    case "t": return `<td class="${k === "il" || k === "ilce" ? "muted" : ""}${sep}">${esc(get(r, k))}</td>`;
    case "c": return `<td class="c${sep}">${esc(get(r, k))}</td>`;
    case "n": case "party": return `<td class="num${sep}">${fmt(get(r, k), d)}</td>`;
    case "g": { const v = get(r, k); return `<td class="num${sep} ${v == null ? "" : v >= 40 ? "up" : v <= -30 ? "down" : ""}">${fmt(v, d)}</td>`; }
    case "name": {
      const w = parties.find(([p]) => p === get(r, "win"));
      const col = w ? `#${w[2]}` : "#6b7280";
      const kur = get(r, "kurum") ? ` <span class="kurum" title="${esc(get(r, "kurum"))}">●</span>` : "";
      return `<td class="name${sep}" style="--pc:${col}" title="${esc(get(r, "win") || "seçim eşleşmedi")}">${esc(get(r, k))}${kur}</td>`;
    }
    case "src": {
      const o = get(r, "oy")[+k[3]];
      const full = [get(r, "stat"), get(r, "aat"), get(r, "deg"), get(r, "bina")][+k[3]];
      return `<td class="c${sep}" title="${esc(full)}"><span class="pill ${o === "-" ? "N" : o}">${o === "K" ? "kent" : o === "R" ? "kır" : "belde"}</span></td>`;
    }
    case "ih": return `<td class="c${sep}"><span class="ih ${get(r, "ih")}">${IH[get(r, "ih")]}</span></td>`;
    case "oneri": return `<td class="oneri${sep} ${URBAN.has(get(r, "os")) ? "k" : "r"}">${esc(get(r, "os"))}</td>`;
    case "sel": {
      const t = kentKir(my.s);
      return `<td class="you"><select data-id="${id}" data-f="s" class="${my.s ? "set" : ""}"><option value="">—</option>${
        CLASSES.map((x) => `<option ${my.s === x ? "selected" : ""}>${x}</option>`).join("")}</select><button class="acc" data-acc="${id}" title="Öneriyi yaz: ${esc(get(r, "os"))}">✓</button><span class="kk ${t}">${t}</span></td>`;
    }
    case "y": return `<td class="${sep}"><input class="y" data-id="${id}" data-f="y" value="${esc(my.y)}" placeholder="${esc(get(r, "yer"))}"></td>`;
    case "nt": return `<td><input class="n" data-id="${id}" data-f="n" value="${esc(my.n)}"></td>`;
    case "note": { const t = get(r, "not") || ""; return `<td class="note${sep}" title="${esc(t)}">${t.startsWith("KURUM") ? `<span class="kurum">${esc(t)}</span>` : esc(t)}</td>`; }
  }
  return "<td></td>";
}
function renderMah() {
  const cols = visibleCols();
  headMah(cols);
  $("tb").innerHTML = shown.slice(0, limit).map((r) => `<tr>${cols.map((c, i) => cell(r, c, i, cols)).join("")}</tr>`).join("");
  more();
}
function more() {
  $("more").innerHTML = shown.length > limit
    ? `${fmt(limit)} / ${fmt(shown.length)} · <button id="moreBtn">${fmt(PAGE)} daha</button>`
    : shown.length ? `${fmt(shown.length)} satır` : "Bu filtrede satır yok.";
  const mb = $("moreBtn");
  if (mb) mb.onclick = () => { limit += PAGE; tab === "mah" ? renderMah() : summaryTable(); };
}

// --- cards: always over the province/district scope
function cards() {
  let pop = 0, done = 0, c = 0, mk = 0, ok = 0, open = 0;
  const ih = { uyumlu: 0, hafif: 0, cok: 0 };
  for (const r of rows) {
    if (!inScope(r)) continue;
    const n = get(r, "n"), s = decOf(get(r, "id")).s;
    pop += n; c++; ih[get(r, "ih")]++;
    if (URBAN.has(get(r, "os"))) ok += n;
    if (URBAN.has(s || get(r, "os"))) mk += n;
    if (s) done++; else if (get(r, "ih") !== "uyumlu") open++;
  }
  const pct = (a, b) => (b ? fmt((a / b) * 100, 1) : "–");
  $("sum").innerHTML = `
    <span><b>${pct(mk, pop)} %</b>kent payı (senin + öneri)</span>
    <span><b>${pct(ok, pop)} %</b>kent payı (öneri)</span>
    <span><b>${fmt(done)} <small>/ ${fmt(c)}</small></b>karar verilen yer</span>
    <span><b>${fmt(open)}</b>bekleyen ihtilaflı yer</span>
    <span><b><em class="ok">${fmt(ih.uyumlu)}</em> · <em class="warn">${fmt(ih.hafif)}</em> · <em class="bad">${fmt(ih.cok)}</em></b>uyumlu · hafif · çok</span>
    <span><b>${fmt(pop)}</b>kişi</span>`;
}

// --- tabs and redraw
function setTab(t) {
  tab = t; limit = PAGE;
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.t === t));
  document.body.dataset.tab = t;
  if (t !== "mah") focus = null;
  refresh();
}
function refresh() {
  $("focus").innerHTML = focus ? `<span class="chip on">${esc(focus.label)} <b data-x="1">✕</b></span>` : "";
  cards();
  tab === "mah" ? mahTable() : summaryTable();
}
let drawIl = () => {}, drawIlce = () => {};

function wire() {
  $("tabs").onclick = (ev) => { const t = ev.target.dataset.t; if (t) setTab(t); };
  $("focus").onclick = (ev) => { if (ev.target.dataset.x) { focus = null; refresh(); } };
  $("th").onclick = (ev) => {
    const th = ev.target.closest("th");
    if (!th) return;
    if (tab !== "mah") {
      const s = th.dataset.s;
      if (!s) return;
      if (sumSort === s) sumAsc = !sumAsc; else { sumSort = s; sumAsc = s === "name"; }
      summaryTable();
      return;
    }
    const k = th.dataset.k;
    if (!k) return;
    if (sortKey === k) sortAsc = !sortAsc; else { sortKey = k; sortAsc = ["t", "c", "name", "src", "ih", "oneri", "sel"].includes(COLS().find((c) => c[0] === k)?.[3]); }
    limit = PAGE; mahTable();
  };
  $("tb").addEventListener("change", (ev) => {
    const t = ev.target, id = t.dataset.id;
    if (!id) return;
    setDecision(id, { [t.dataset.f]: t.value.trim() });
    if (t.dataset.f === "s") {
      t.classList.toggle("set", !!t.value);
      const kk = t.parentElement.querySelector(".kk");
      kk.textContent = kentKir(t.value); kk.className = `kk ${kentKir(t.value)}`;
    }
  });
  $("tb").addEventListener("click", (ev) => {
    const a = ev.target.dataset && ev.target.dataset.acc;
    if (a) {
      const r = rows.find((x) => get(x, "id") === a);
      const s = ev.target.previousElementSibling;
      s.value = get(r, "os"); s.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }
    const tr = ev.target.closest("tr.drill");
    if (tr) { drill(tr.dataset.k); return; }
    const td = ev.target.closest("td.note");
    if (td) td.classList.toggle("open");
  });
  $("bulk").onclick = () => {
    const todo = shown.filter((r) => !decOf(get(r, "id")).s);
    if (!todo.length) return;
    if (!confirm(`Görünen ve kararı boş ${fmt(todo.length)} yere öneri yazılsın mı? (${fmt(todo.reduce((a, r) => a + get(r, "n"), 0))} kişi)`)) return;
    for (const r of todo) pending[get(r, "id")] = { ...decOf(get(r, "id")), s: get(r, "os") };
    try { localStorage.setItem(PENDING_KEY, JSON.stringify(pending)); } catch (e) { /* ignore */ }
    flush().then(refresh);
  };
  let t = null;
  $("q").oninput = $("nMin").oninput = () => { clearTimeout(t); t = setTimeout(() => { limit = PAGE; refresh(); }, 250); };
}

async function main() {
  $("tb").innerHTML = `<tr><td class="muted" style="padding:20px">Yükleniyor… (20 MB)</td></tr>`;
  const data = await (await fetch(DATA_URL)).json();
  K = Object.fromEntries(data.keys.map((k, i) => [k, i]));
  rows = data.rows; parties = data.parties;
  try { const r = await fetch(DEC_URL, { cache: "no-store" }); if (r.ok) dec = await r.json(); } catch (e) { /* none yet */ }
  try { pending = JSON.parse(localStorage.getItem(PENDING_KEY) || "{}"); } catch (e) { pending = {}; }

  $("tabs").innerHTML = Object.entries(TABS).map(([k, t]) => `<button data-t="${k}">${t}</button>`).join("");
  const count = (fn) => { const m = new Map(); for (const r of rows) { const k = fn(r); if (k) m.set(k, (m.get(k) || 0) + 1); } return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0], "tr")); };
  drawIl = buildDrop($("dIl"), "İl", () => count((r) => get(r, "il")), selIl, () => {
    for (const k of [...selIlce]) if (selIl.size && !selIl.has(k.split(" · ")[0])) selIlce.delete(k);
    drawIlce(); limit = PAGE; refresh();
  });
  drawIlce = buildDrop($("dIlce"), "İlçe", () => count((r) => (!selIl.size || selIl.has(get(r, "il")) ? ilceKey(r) : null)), selIlce, () => { limit = PAGE; refresh(); });
  chips($("cIh"), [["uyumlu", "uyumlu", "#6cc38a"], ["hafif", "hafif", "#e8b64c"], ["cok", "çok", "#ef7d73"]], f.ih, () => { limit = PAGE; mahTable(); });
  chips($("cOn"), CLASSES.map((c) => [c, c]), f.on, () => { limit = PAGE; mahTable(); });
  const kr = new Set(f.kr);
  chips($("cKr"), [["bos", "bekleyen"], ["dolu", "verilmiş"], ["kurum", "yalnız kurum"]], kr, () => {
    f.kr = new Set([...kr].filter((x) => x !== "kurum")); f.kurum = kr.has("kurum"); limit = PAGE; mahTable();
  });
  chips($("cGr"), TOGGLE, f.groups, renderMah);
  wire();
  setTab("il");
  if (Object.keys(pending).length) flush();
}
main();
