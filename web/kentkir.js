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
const BANDS = [["0", "0-2", "#6cc38a"], ["2", "2-4", "#a9c46a"], ["4", "4-6", "#e2b458"], ["6", "6-8", "#e8955e"], ["8", "8-10", "#ec7f75"]];
const band = (u) => String(Math.min(8, Math.floor(u / 2) * 2));
// the user's decision, else a provisional placement for near-certain rows (uncertainty < 2), else open
const placed = (r) => decOf(get(r, "id")).s || (get(r, "bs") < 2 ? get(r, "os") : "");
const f = { bs: new Set(BANDS.map((b) => b[0])), ih: new Set(["uyumlu", "hafif", "cok"]), on: new Set(CLASSES), kr: new Set(["bos", "dolu"]), kurum: false,
            groups: new Set(["temel", "kaynak", "not", "you2"]) };

const $ = (id) => document.getElementById(id);
const fmt = (v, d = 0) => v == null || v === "" ? "" : Number(v).toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const fold = (s) => String(s || "").toLocaleLowerCase("tr").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ı/g, "i");
const get = (r, k) => r[K[k]];
const kentKir = (s) => (s ? (URBAN.has(s) ? "KENT" : "KIR") : "");
const ilceKey = (r) => `${get(r, "il")} · ${get(r, "ilce")}`;

// --- interface settings (panels, columns, density, accent, font), kept in localStorage
const UI_KEY = "kentkir.ui";
const PANELS = { cards: true, prog: true, filters: true, info: true, detail: true };
const ui = { panels: { ...PANELS }, den: "normal", acc: "amber", font: "mono", hidden: [], open: [], widths: {} };
try {
  const saved = JSON.parse(localStorage.getItem(UI_KEY) || "{}");
  Object.assign(ui, saved);
  ui.panels = { ...PANELS, ...(saved.panels || {}) };
  ui.widths = saved.widths || {};
} catch (e) { /* defaults */ }
const saveUi = () => { try { localStorage.setItem(UI_KEY, JSON.stringify(ui)); } catch (e) { /* ignore */ } };
function applyUi() {
  const d = document.documentElement.dataset;
  d.acc = ui.acc; d.den = ui.den; d.font = ui.font;
  for (const [k, v] of Object.entries(ui.panels)) document.body.classList.toggle(`hide-${k}`, !v);
}
// extra numeric filters set from the command line (mahalle tab)
const xf = { bsMin: 0, bsMax: 10, nMax: Infinity };
// the user's own semt: a name and one of two kinds
const SEMT_KINDS = ["Merkez semti", "Kırsal belde"];
const NO_SEMT = "— girilmemiş";
const semtOf = (r) => decOf(get(r, "id")).sm || NO_SEMT;

// --- neighbourhood table columns: [key, header, group, render kind, digits]
const COLS = () => [
  ["il", "İl", "id", "t"], ["ilce", "İlçe", "id", "t"], ["yer", "Yerleşim", "id", "t"], ["ad", "Mahalle / köy", "id", "name"],
  ["n", "Nüfus", "temel", "n", 0], ["g", "2013→25 %", "temel", "g", 1], ["dens", "Kişi/km²", "temel", "n", 0],
  ["leke", "Merkez lekesi %", "temel", "n", 0], ["kpb", "Konut/bina", "temel", "n", 2],
  ["oy", "TÜİK · AAT · DEG · Bina", "kaynak", "srcs"], ["bs", "Belirsizlik", "kaynak", "bs", 1], ["os", "Öneri", "kaynak", "oneri"],
  ["not", "Otomatik not", "not", "note"],
  ["n0", "Nüfus 2013", "nufus", "n", 0], ["area", "Alan km²", "nufus", "n", 2], ["kur", "Kuruluş", "nufus", "c"], ["tur", "Tür", "nufus", "c"],
  ["er", "Erkek %", "yas", "n", 1], ["u17", "0-17 %", "yas", "n", 1], ["o65", "65+ %", "yas", "n", 1], ["med", "Ortanca yaş", "yas", "n", 1], ["uni", "Üniversiteli %", "yas", "n", 1],
  ["hh", "Hane", "konut", "n", 0], ["hs", "Hane büy.", "konut", "n", 2], ["dw", "Konut", "konut", "n", 0], ["bl", "Bina (MS)", "konut", "n", 0],
  ["kpbl", "Kişi/bina", "konut", "n", 1], ["hpb", "Hane/bina", "konut", "n", 2], ["prs", "Parsel", "konut", "n", 0], ["yaz", "Yazlık %", "konut", "n", 1],
  ["k23", "Kayıtlı", "secim", "n", 0], ["g23", "Geçerli", "secim", "n", 0], ["kn", "Kayıtlı/nüfus %", "secim", "n", 1],
  ...parties.map(([p, short]) => [p, short, "secim", "party", 1]),
  ["stat", "TÜİK statü", "kaynakx", "t"], ["aat", "AATOPLU", "kaynakx", "t"], ["deg", "DEGURBA", "kaynakx", "t"], ["bina", "Bina analizi", "kaynakx", "t"],
  ["u_st", "Semt türü", "you2", "st"], ["u_sm", "Semt (senin)", "you2", "sm"], ["u_y", "Yerleşim (senin)", "you2", "y"], ["u_n", "Not (senin)", "you2", "nt"],
  ["u_s", "Karar", "you", "sel"],
];
const GROUPS = { id: "", temel: "Temel", kaynak: "Kaynaklar ve öneri", not: "", nufus: "Nüfus", yas: "Yaş · eğitim (2024)",
                 konut: "Hane · konut · bina", secim: "Seçim 2023", kaynakx: "Kaynak ayrıntı", you2: "Senin", you: "" };
const TOGGLE = [["temel", "Temel"], ["kaynak", "Kaynaklar"], ["not", "Not"], ["nufus", "Nüfus"], ["yas", "Yaş · eğitim"],
                ["konut", "Hane · konut · bina"], ["secim", "Seçim 2023"], ["kaynakx", "Kaynak ayrıntı"], ["you2", "Yerleşim/not (senin)"]];
const visibleCols = () => COLS().filter((c) => (c[2] === "id" || c[2] === "you" || f.groups.has(c[2])) && !ui.hidden.includes(c[0]));

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
  const label = () => {
    const all = items().length;
    btn.textContent = sel.size >= all ? `${title}: tümü` : sel.size === 0 ? `${title}: hiçbiri` : sel.size === 1 ? [...sel][0] : `${title}: ${sel.size} / ${all}`;
  };
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
  if (!selIl.has(get(r, "il"))) return false;
  if (!selIlce.has(ilceKey(r))) return false;
  if (focus && (focus.k === "semt" ? semtOf(r) : get(r, focus.k)) !== focus.v) return false;
  return true;
}

// --- summary tabs
function groupKey(r) {
  if (tab === "il") return [get(r, "il")];
  if (tab === "ilce") return [get(r, "il"), get(r, "ilce")];
  return [get(r, "il"), get(r, "ilce"), tab === "semt" ? semtOf(r) : get(r, tab)];
}
function summaryTable() {
  const q = fold($("q").value), m = new Map();
  for (const r of rows) {
    if (!inScope(r)) continue;
    const key = groupKey(r), k = key.join(" · ");
    if (q && !fold(k).includes(q)) continue;
    const n = get(r, "n"), s = decOf(get(r, "id")).s, ih = get(r, "ih");
    const t = m.get(k) || { key, n: 0, c: 0, ok: 0, mk: 0, done: 0, hafif: 0, cok: 0, open: 0, pk: 0, pn: 0, un: 0 };
    t.n += n; t.c++;
    const pl = placed(r);
    if (pl) { t.pn += n; if (URBAN.has(pl)) t.pk += n; } else t.un += n;
    if (URBAN.has(get(r, "os"))) t.ok += n;
    if (URBAN.has(s || get(r, "os"))) t.mk += n;
    if (s) t.done += n;
    if (ih !== "uyumlu") { t[ih]++; if (!s) t.open++; }
    m.set(k, t);
  }
  const list = [...m.values()].map((t) => ({ ...t, po: t.ok / t.n * 100, pm: t.mk / t.n * 100, pd: t.done / t.n * 100,
    pp: t.pn / t.n * 100, lo: t.pk / t.n * 100, hi: (t.pk + t.un) / t.n * 100, pu: t.un / t.n * 100 }));
  const sk = sumSort;
  list.sort((a, b) => {
    const x = sk === "name" ? a.key.join() : a[sk], y = sk === "name" ? b.key.join() : b[sk];
    const c = typeof x === "string" ? x.localeCompare(y, "tr") : x - y;
    return sumAsc ? c : -c;
  });
  shown = list;
  const names = { il: ["İl"], ilce: ["İl", "İlçe"], yer: ["İl", "İlçe", "Yerleşim"], semt: ["İl", "İlçe", "Semt (senin)"] }[tab];
  const H = (k, t, cls = "num") => `<th data-s="${k}" class="${cls} ${sumSort === k ? `sorted ${sumAsc ? "asc" : ""}` : ""}">${t}</th>`;
  $("th").innerHTML = `<tr class="cols">${names.map((n, i) => i === names.length - 1 ? H("name", n, "") : `<th></th>`).join("")}
    ${H("n", "Nüfus")}${H("c", "Yer")}${H("pm", "Kent % (senin + öneri)")}${H("po", "Kent % (öneri)")}
    ${H("pp", "Yerleşen nüfus %")}${H("lo", "Kent % aralığı (0 ─ 100, çizgi: senin + öneri)", "")}${H("pu", "Belirsiz nüfus %")}
    ${H("pd", "Karar verilen nüfus %")}${H("hafif", "Hafif ihtilaf")}${H("cok", "Çok ihtilaf")}${H("open", "Bekleyen ihtilaf")}</tr>`;
  const bar = (v, cls) => `<span class="bar ${cls}" style="width:${Math.max(0, Math.min(100, v)) * 0.6}px"></span>`;
  $("tb").innerHTML = list.slice(0, limit).map((t) => {
    const d = t.pm - t.po;
    return `<tr class="drill" data-k="${esc(t.key.join("\u0001"))}">${t.key.map((x, i) => `<td class="${i === t.key.length - 1 ? "name2" : "muted"}">${esc(x)}</td>`).join("")}
      <td class="num">${fmt(t.n)}</td><td class="num muted">${fmt(t.c)}</td>
      <td class="num"><span class="cell-bar">${bar(t.pm, "k")}<b>${fmt(t.pm, 1)}</b></span></td>
      <td class="num">${fmt(t.po, 1)}${t.done && Math.abs(d) >= 0.05 ? ` <span class="${d > 0 ? "up" : "down"}">${d > 0 ? "+" : ""}${fmt(d, 1)}</span>` : ""}</td>
      <td class="num">${fmt(t.pp, 0)}</td><td class="rng" title="alt ${fmt(t.lo, 1)} · üst ${fmt(t.hi, 1)} · senin + öneri ${fmt(t.pm, 1)}"><span class="track"><i class="band" style="left:${t.lo}%;width:${Math.max(0.8, t.hi - t.lo)}%"></i><i class="dot" style="left:${t.pm}%"></i></span>${fmt(t.lo, 0)}–${fmt(t.hi, 0)}</td><td class="num ${t.pu >= 30 ? "warn" : ""}">${fmt(t.pu, 1)}</td>
      <td class="num"><span class="cell-bar">${bar(t.pd, "d")}${fmt(t.pd, 0)}</span></td>
      <td class="num ${t.hafif ? "warn" : "muted"}">${fmt(t.hafif)}</td><td class="num ${t.cok ? "bad" : "muted"}">${fmt(t.cok)}</td>
      <td class="num ${t.open ? "" : "muted"}">${fmt(t.open)}</td></tr>`;
  }).join("");
  fitTable([...names.map((_, i) => `s_${tab}${i}`), ...["n", "c", "pm", "po", "pp", "lo", "pu", "pd", "hafif", "cok", "open"].map((k) => `s_${k}`)]);
  more();
}
function drill(key) {
  const [il, ilce, v] = key.split("\u0001");
  selIl.clear(); selIl.add(il); resetIlce();
  if (tab === "il") { drawIl(); drawIlce(); setTab("ilce"); return; }
  selIlce.clear(); selIlce.add(`${il} · ${ilce}`); drawIl(); drawIlce();
  focus = tab === "yer" || tab === "semt" ? { k: tab, v, label: `${tab === "yer" ? "Yerleşim" : "Semt"}: ${v}` } : null;
  setTab("mah");
}

// --- neighbourhood table
function mahTable() {
  const q = fold($("q").value), nMin = +$("nMin").value || 0;
  shown = rows.filter((r) => {
    if (!inScope(r)) return false;
    if (!f.ih.has(get(r, "ih"))) return false;
    if (!f.bs.has(band(get(r, "bs")))) return false;
    if (!f.on.has(get(r, "os"))) return false;
    if (f.kurum && !get(r, "kurum")) return false;
    if (!f.kr.has(decOf(get(r, "id")).s ? "dolu" : "bos")) return false;
    if (get(r, "n") < nMin) return false;
    if (q && !fold(`${get(r, "ad")} ${get(r, "yer")} ${get(r, "ilce")} ${decOf(get(r, "id")).sm || ""}`).includes(q)) return false;
    const b = get(r, "bs");
    if (b < xf.bsMin || b > xf.bsMax || get(r, "n") > xf.nMax) return false;
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
  cur = -1;
  panel(null);
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
    case "srcs": {
      const full = [["TÜİK", get(r, "stat")], ["AATOPLU", get(r, "aat")], ["DEGURBA", get(r, "deg")], ["Bina", get(r, "bina")]];
      return `<td class="c${sep}">${[...get(r, "oy")].map((o, j) => `<i class="sq ${o === "-" ? "N" : o}" title="${full[j][0]}: ${esc(full[j][1])}"></i>`).join("")}</td>`;
    }
    case "src": {
      const o = get(r, "oy")[+k[3]];
      const full = [get(r, "stat"), get(r, "aat"), get(r, "deg"), get(r, "bina")][+k[3]];
      return `<td class="c${sep}" title="${esc(full)}"><span class="pill ${o === "-" ? "N" : o}">${o === "K" ? "kent" : o === "R" ? "kır" : "belde"}</span></td>`;
    }
    case "bs": { const v = get(r, "bs"), c = BANDS.find((b) => b[0] === band(v))[2];
      return `<td class="num${sep}" title="kent olasılığı ${fmt(get(r, "pk") * 100)} %"><span class="bsbar" style="width:${v * 4}px;background:${c}"></span><b style="color:${c}">${fmt(v, 1)}</b></td>`; }
    case "ih": return `<td class="c${sep}"><span class="ih ${get(r, "ih")}">${IH[get(r, "ih")]}</span></td>`;
    case "oneri": return `<td class="oneri${sep} ${URBAN.has(get(r, "os")) ? "k" : "r"}">${esc(get(r, "os"))}</td>`;
    case "sel": {
      const t = kentKir(my.s);
      return `<td class="you"><select data-id="${id}" data-f="s" class="${my.s ? "set" : ""}"><option value="">—</option>${
        CLASSES.map((x) => `<option ${my.s === x ? "selected" : ""}>${x}</option>`).join("")}</select><button class="acc" data-acc="${id}" title="Öneriyi yaz: ${esc(get(r, "os"))}">✓</button><span class="kk ${t}">${t}</span></td>`;
    }
    case "y": return `<td class="${sep}"><input class="y" data-id="${id}" data-f="y" value="${esc(my.y)}" placeholder="${esc(get(r, "yer"))}"></td>`;
    case "st": return `<td class="${sep}"><select class="st ${my.st ? "set" : ""}" data-id="${id}" data-f="st"><option value="">—</option>${
      SEMT_KINDS.map((x) => `<option ${my.st === x ? "selected" : ""}>${x}</option>`).join("")}</select></td>`;
    case "sm": return `<td><input class="y" data-id="${id}" data-f="sm" value="${esc(my.sm)}"></td>`;
    case "nt": return `<td><input class="n" data-id="${id}" data-f="n" value="${esc(my.n)}"></td>`;
    case "note": { const t = get(r, "not") || ""; return `<td class="note${sep}" title="${esc(t)}">${t.startsWith("KURUM") ? `<span class="kurum">${esc(t)}</span>` : esc(t)}</td>`; }
  }
  return "<td></td>";
}
function renderMah() {
  const cols = visibleCols();
  headMah(cols);
  $("tb").innerHTML = shown.slice(0, limit).map((r, i) =>
    `<tr data-i="${i}" class="ih-${get(r, "ih")} ${i === cur ? "cur" : ""}">${cols.map((c, j) => cell(r, c, j, cols)).join("")}</tr>`).join("");
  fitTable(cols.map((c) => c[0]));
  more();
  if (cur >= 0 && shown[cur]) panel(shown[cur]);
}

// --- resizable columns: fixed layout over a colgroup; the natural width is measured once per
// column, a drag on the header's right edge sets it (kept in ui.widths), double click resets it
const colAuto = {};
function fitTable(keys) {
  const t = $("tbl");
  t.classList.remove("fixed"); t.style.width = "";
  const old = $("cg"); if (old) old.remove();
  const ths = [...$("th").querySelectorAll("tr.cols th")];
  if (ths.length !== keys.length) return;
  const W = keys.map((k, i) => ui.widths[k] || colAuto[k] || (colAuto[k] = Math.max(36, Math.ceil(ths[i].getBoundingClientRect().width))));
  const cg = document.createElement("colgroup");
  cg.id = "cg";
  cg.innerHTML = W.map((w) => `<col style="width:${w}px">`).join("");
  t.insertBefore(cg, t.firstChild);
  const cols = [...cg.children];
  const apply = () => { cols.forEach((c, i) => { c.style.width = `${W[i]}px`; }); t.style.width = `${W.reduce((a, b) => a + b, 0)}px`; };
  t.classList.add("fixed");
  apply();
  ths.forEach((th, i) => {
    const g = document.createElement("span");
    g.className = "grip";
    g.title = "sürükle: genişlik · çift tık: sıfırla";
    g.onclick = (ev) => ev.stopPropagation();
    g.ondblclick = (ev) => { ev.stopPropagation(); delete ui.widths[keys[i]]; delete colAuto[keys[i]]; saveUi(); tab === "mah" ? renderMah() : summaryTable(); };
    g.onmousedown = (ev) => {
      ev.preventDefault(); ev.stopPropagation();
      const x0 = ev.clientX, w0 = W[i];
      g.classList.add("drag");
      const move = (e) => { W[i] = Math.max(36, w0 + e.clientX - x0); apply(); };
      const up = () => {
        document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up);
        g.classList.remove("drag"); ui.widths[keys[i]] = Math.round(W[i]); saveUi();
      };
      document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
    };
    th.appendChild(g);
  });
}

// --- current row, detail panel, keyboard
let cur = -1;
function select(i, scroll = true) {
  if (tab !== "mah" || i < 0 || i >= shown.length) return;
  if (i >= limit) { limit = Math.ceil((i + 1) / PAGE) * PAGE; cur = i; renderMah(); }
  const old = $("tb").querySelector("tr.cur");
  if (old) old.classList.remove("cur");
  cur = i;
  const tr = $("tb").querySelector(`tr[data-i="${i}"]`);
  if (tr) { tr.classList.add("cur"); if (scroll) tr.scrollIntoView({ block: "nearest" }); }
  panel(shown[i]);
}
function decide(r, cls) {
  setDecision(get(r, "id"), { s: cls });
  const tr = $("tb").querySelector(`tr[data-i="${shown.indexOf(r)}"]`);
  if (!tr) return;
  const sel = tr.querySelector("select[data-f=s]");
  if (sel) { sel.value = cls; sel.classList.toggle("set", !!cls); }
  const kk = tr.querySelector(".kk");
  if (kk) { kk.textContent = kentKir(cls); kk.className = `kk ${kentKir(cls)}`; }
}
function closePanel() {
  cur = -1;
  const o = $("tb").querySelector("tr.cur");
  if (o) o.classList.remove("cur");
  panel(null);
}
function panel(r) {
  const P = $("panel");
  if (!r || !ui.panels.detail) { P.hidden = true; document.body.classList.remove("with-panel"); return; }
  P.hidden = false;
  document.body.classList.add("with-panel");
  const my = decOf(get(r, "id")), xy = get(r, "xy");
  const stat = (t, k, d = 0, suf = "") => get(r, k) == null ? "" : `<div><span>${t}</span><b>${fmt(get(r, k), d)}${suf}</b></div>`;
  const w = parties.find(([p]) => p === get(r, "win"));
  const votes = parties.filter(([p]) => get(r, p)).map(([p, sh, fill]) =>
    `<div class="vb"><span>${sh}</span><i style="width:${get(r, p) * 1.6}px;background:#${fill}"></i><b>${fmt(get(r, p), 1)}</b></div>`).join("");
  const srcs = [["TÜİK statü", "stat"], ["AATOPLU 2015", "aat"], ["DEGURBA", "deg"], ["Bina analizi", "bina"]].map(([t, k], j) => {
    const o = get(r, "oy")[j];
    return `<div class="src"><span class="pill ${o === "-" ? "N" : o}">${o === "K" ? "kent" : o === "R" ? "kır" : "belde"}</span><b>${t}</b>${esc(get(r, k))}</div>`;
  }).join("");
  const bsv = get(r, "bs"), bc = BANDS.find((b) => b[0] === band(bsv))[2];
  P.innerHTML = `
    <div class="ph"><div><h2 style="--pc:${w ? "#" + w[2] : "#6b7280"}">${esc(get(r, "ad"))}</h2>
      <div class="muted">${esc(get(r, "il"))} · ${esc(get(r, "ilce"))} · ${esc(get(r, "yer"))}${my.sm ? " · semt " + esc(my.sm) : ""} · ${esc(get(r, "tur"))}</div></div>
      <button id="pclose" title="Kapat (Esc)">✕</button></div>
    <div class="pbig">
      <div><span>Öneri</span><b class="${URBAN.has(get(r, "os")) ? "k" : "r"}">${esc(get(r, "os"))}</b></div>
      <div><span>Belirsizlik</span><b style="color:${bc}">${fmt(bsv, 1)}</b></div>
      <div><span>Kent olasılığı</span><b>${fmt(get(r, "pk") * 100)} %</b></div>
      <div><span>İhtilaf</span><b class="ih ${get(r, "ih")}">${IH[get(r, "ih")]}</b></div>
    </div>
    <div class="pdec">${CLASSES.map((c, i) => `<button data-cls="${c}" class="${my.s === c ? "on" : ""} ${URBAN.has(c) ? "k" : "r"} ${get(r, "os") === c ? "sug" : ""}"><kbd>${i + 1}</kbd>${c}</button>`).join("")}
      <button data-cls="" class="clr"><kbd>0</kbd>temizle</button></div>
    <div class="pin"><select id="pst"><option value="">semt türü (senin) —</option>${SEMT_KINDS.map((x) => `<option ${my.st === x ? "selected" : ""}>${x}</option>`).join("")}</select>
      <input id="psm" placeholder="semt adı (senin)" value="${esc(my.sm)}"><input id="py" placeholder="yerleşim (senin): ${esc(get(r, "yer"))}" value="${esc(my.y)}"><input id="pn" placeholder="not (senin)" value="${esc(my.n)}"></div>
    ${get(r, "not") ? `<div class="pnote">${esc(get(r, "not"))}</div>` : ""}
    <h3>Kaynaklar</h3>${srcs}
    <h3>Göstergeler</h3><div class="pstats">
      ${stat("Nüfus 2025", "n")}${stat("Nüfus 2013", "n0")}${stat("Değişim 13-25", "g", 1, " %")}${stat("Kişi / km²", "dens")}
      ${stat("Merkez lekesi", "leke", 0, " %")}${stat("Konut / bina", "kpb", 2)}${stat("Kişi / bina", "kpbl", 1)}${stat("Hane büy.", "hs", 2)}
      ${stat("Hane", "hh")}${stat("Konut", "dw")}${stat("Bina (MS)", "bl")}${stat("Yazlık", "yaz", 1, " %")}
      ${stat("Erkek", "er", 1, " %")}${stat("0-17", "u17", 1, " %")}${stat("65+", "o65", 1, " %")}${stat("Ortanca yaş", "med", 1)}
      ${stat("Üniversiteli", "uni", 1, " %")}${stat("Alan km²", "area", 2)}${stat("Kayıtlı 2023", "k23")}${stat("Kayıtlı/nüfus", "kn", 0, " %")}
      ${get(r, "kur") ? `<div><span>Kuruluş</span><b>${esc(get(r, "kur"))}</b></div>` : ""}</div>
    ${votes ? `<h3>Seçim 2023</h3><div class="votes">${votes}</div>` : ""}
    ${xy ? `<div class="links"><a target="_blank" rel="noopener" href="https://www.google.com/maps/@${xy[0]},${xy[1]},15z/data=!3m1!1e3">Uydu görüntüsü (Google Haritalar) ↗</a></div>` : ""}
    <div class="keys muted">↑↓ satır · 1-6 sınıf · Enter öneri · 0 temizle · Esc kapat. Karar verince bir alta geçer.</div>`;
  $("pclose").onclick = closePanel;
  P.querySelector(".pdec").onclick = (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    decide(r, b.dataset.cls);
    if (b.dataset.cls) select(cur + 1); else panel(r);
  };
  $("pst").onchange = (ev) => setDecision(get(r, "id"), { st: ev.target.value });
  $("psm").onchange = (ev) => setDecision(get(r, "id"), { sm: ev.target.value.trim() });
  $("py").onchange = (ev) => setDecision(get(r, "id"), { y: ev.target.value.trim() });
  $("pn").onchange = (ev) => setDecision(get(r, "id"), { n: ev.target.value.trim() });
}
document.addEventListener("keydown", (ev) => {
  if (tab !== "mah" || ev.ctrlKey || ev.metaKey || ev.altKey) return;
  if (/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) { if (ev.key === "Escape") document.activeElement.blur(); return; }
  const r = shown[cur];
  if (ev.key === "ArrowDown" || ev.key === "j") { select(Math.min(shown.length - 1, cur + 1)); ev.preventDefault(); return; }
  if (ev.key === "ArrowUp" || ev.key === "k") { select(Math.max(0, cur - 1)); ev.preventDefault(); return; }
  if (!r) return;
  if (ev.key >= "1" && ev.key <= "6") { decide(r, CLASSES[+ev.key - 1]); select(cur + 1); }
  else if (ev.key === "Enter") { decide(r, get(r, "os")); select(cur + 1); ev.preventDefault(); }
  else if (ev.key === "0" || ev.key === "Backspace") { decide(r, ""); panel(r); }
  else if (ev.key === "Escape") closePanel();
});
function more() {
  $("more").innerHTML = shown.length > limit
    ? `${fmt(limit)} / ${fmt(shown.length)} · <button id="moreBtn">${fmt(PAGE)} daha</button>`
    : shown.length ? `${fmt(shown.length)} satır` : "Bu filtrede satır yok.";
  const mb = $("moreBtn");
  if (mb) mb.onclick = () => { limit += PAGE; tab === "mah" ? renderMah() : summaryTable(); };
}

// --- cards: always over the province/district scope
function cards() {
  let pop = 0, done = 0, c = 0, mk = 0, ok = 0, open = 0, pn = 0, pkent = 0, un = 0, uc = 0, donePop = 0;
  const ih = { uyumlu: 0, hafif: 0, cok: 0 };
  for (const r of rows) {
    if (!inScope(r)) continue;
    const n = get(r, "n"), s = decOf(get(r, "id")).s;
    pop += n; c++; ih[get(r, "ih")]++;
    if (URBAN.has(get(r, "os"))) ok += n;
    if (URBAN.has(s || get(r, "os"))) mk += n;
    if (s) { done++; donePop += n; } else if (get(r, "ih") !== "uyumlu") open++;
    const pl = placed(r);
    if (pl) { pn += n; if (URBAN.has(pl)) pkent += n; } else { un += n; uc++; }
  }
  const pct = (a, b) => (b ? fmt((a / b) * 100, 1) : "–");
  $("sum").innerHTML = `
    <span><b>${fmt(pn)} <small>${pct(pn, pop)} %</small></b>yerleşen kişi (senin + belirsizliği 2'nin altı)</span>
    <span><b>${fmt(pkent)} · ${fmt(pn - pkent)}</b>kent · kır</span>
    <span><b>${pct(pkent, pop)} – ${pct(pkent + un, pop)} %</b>kent payı aralığı (belirsizlerin hepsi kır … hepsi kent)</span>
    <span><b>${fmt(uc)} <small>${fmt(un)} kişi</small></b>belirsiz yer</span>
    <span><b>${pct(mk, pop)} %</b>kent payı (senin + öneri)</span>
    <span><b>${pct(ok, pop)} %</b>kent payı (öneri)</span>
    <span><b>${fmt(done)} <small>/ ${fmt(c)}</small></b>karar verilen yer</span>
    <span><b>${fmt(open)}</b>bekleyen ihtilaflı yer</span>
    <span><b><em class="ok">${fmt(ih.uyumlu)}</em> · <em class="warn">${fmt(ih.hafif)}</em> · <em class="bad">${fmt(ih.cok)}</em></b>uyumlu · hafif · çok</span>
    <span><b>${fmt(pop)}</b>kişi</span>
    <div class="prog" title="nüfusa göre"><i class="p1" style="width:${pop ? donePop / pop * 100 : 0}%"></i><i class="p2" style="width:${pop ? (pn - donePop) / pop * 100 : 0}%"></i>
      <em>senin kararın ${pct(donePop, pop)} % · geçici yerleşen ${pct(pn - donePop, pop)} % · belirsiz ${pct(un, pop)} %</em></div>`;
}

// --- tabs and redraw
function setTab(t) {
  if (t !== "mah") closePanel();
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
// a change of provinces selects every district of the selected provinces
function resetIlce() { selIlce.clear(); for (const r of rows) if (selIl.has(get(r, "il"))) selIlce.add(ilceKey(r)); }

function krChips() {
  const kr = new Set([...f.kr, ...(f.kurum ? ["kurum"] : [])]);
  chips($("cKr"), [["bos", "bekleyen"], ["dolu", "verilmiş"], ["kurum", "yalnız kurum"]], kr, () => {
    f.kr = new Set([...kr].filter((x) => x !== "kurum")); f.kurum = kr.has("kurum"); limit = PAGE; mahTable();
  });
}

function wire() {
  $("tabs").onclick = (ev) => { const t = ev.target.closest("button")?.dataset.t; if (t) setTab(t); };
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
    const row = ev.target.closest("tr[data-i]");
    if (row && !ev.target.closest("select,input,button")) select(+row.dataset.i, false);
  });
  $("preset").onclick = () => {
    f.bs = new Set(["2", "4", "6", "8"]); f.kr = new Set(["bos"]); f.kurum = false; sortKey = "bs"; sortAsc = false;
    chips($("cBs"), BANDS, f.bs, () => { limit = PAGE; mahTable(); });
    krChips();
    setTab("mah");
  };
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

  $("tabs").innerHTML = Object.entries(TABS).map(([k, t], i) => `<button data-t="${k}"><span class="fk">F${i + 1}</span>${t}</button>`).join("");
  const count = (fn) => { const m = new Map(); for (const r of rows) { const k = fn(r); if (k) m.set(k, (m.get(k) || 0) + 1); } return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0], "tr")); };
  for (const r of rows) { selIl.add(get(r, "il")); selIlce.add(ilceKey(r)); }
  drawIl = buildDrop($("dIl"), "İl", () => count((r) => get(r, "il")), selIl, () => {
    resetIlce();
    drawIlce(); limit = PAGE; refresh();
  });
  drawIlce = buildDrop($("dIlce"), "İlçe", () => count((r) => (selIl.has(get(r, "il")) ? ilceKey(r) : null)), selIlce, () => { limit = PAGE; refresh(); });
  buildChips();
  wire();
  wireUi();
  wireCmd();
  applyUi();
  uiPanel();
  setTab("il");
  if (Object.keys(pending).length) flush();
}

function buildChips() {
  chips($("cBs"), BANDS, f.bs, () => { limit = PAGE; mahTable(); });
  chips($("cIh"), [["uyumlu", "uyumlu", "#6cc38a"], ["hafif", "hafif", "#e8b64c"], ["cok", "çok", "#ef7d73"]], f.ih, () => { limit = PAGE; mahTable(); });
  chips($("cOn"), CLASSES.map((c) => [c, c]), f.on, () => { limit = PAGE; mahTable(); });
  krChips();
  chips($("cGr"), TOGGLE, f.groups, () => { renderMah(); uiPanel(); });
  $("legend").innerHTML = `<span class="lg">mahalle adının solu: 2023 birinci parti →</span>` + parties.map(([, sh, fill]) => `<span class="lg"><i style="background:#${fill}"></i>${sh}</span>`).join("")
    + `<span class="lg"><i style="background:#6b7280"></i>diğer</span><span class="lg">· satırın solu: <i style="background:#8a6f2e"></i>hafif <i style="background:#a83f36"></i>çok ihtilaf</span>`;
}

// --- interface menu: every panel, column group and column, density, accent, font
const COL_LABEL = { id: "Yer", temel: "Temel", kaynak: "Kaynaklar", not: "Not", nufus: "Nüfus", yas: "Yaş · eğitim", konut: "Hane · konut · bina",
                    secim: "Seçim 2023", kaynakx: "Kaynak ayrıntı", you2: "Senin (semt, yerleşim, not)", you: "Karar" };
function uiPanel() {
  const P = $("ui");
  const chk = (id, label) => `<label class="opt"><input type="checkbox" data-p="${id}" ${ui.panels[id] ? "checked" : ""}>${label}</label>`;
  const seg = (name, opts, cur) => `<div class="seg">${opts.map(([v, t]) => `<button data-${name}="${v}" class="${cur === v ? "on" : ""}">${t}</button>`).join("")}</div>`;
  const byGroup = new Map();
  for (const c of COLS()) if (c[0] !== "ad") { if (!byGroup.has(c[2])) byGroup.set(c[2], []); byGroup.get(c[2]).push(c); }
  // a group is one row; its columns list only while the group is on and expanded
  const colsHtml = [...byGroup.entries()].map(([g, cs]) => {
    const always = g === "id" || g === "you";
    const on = always || f.groups.has(g);
    const open = on && ui.open.includes(g);
    const nOn = cs.filter((c) => !ui.hidden.includes(c[0])).length;
    const head = always ? `<span class="gl">${COL_LABEL[g]}</span>` : `<label class="gl"><input type="checkbox" data-g="${g}" ${on ? "checked" : ""}>${COL_LABEL[g]}</label>`;
    return `<div class="opt grp">${head}<span class="cnt">${on ? `${nOn}/${cs.length}` : "kapalı"}</span><button class="chev" data-open="${g}" ${on ? "" : "disabled"}>${open ? "▾" : "▸"}</button></div>`
      + (open ? cs.map((c) => `<label class="opt sub"><input type="checkbox" data-c="${c[0]}" ${ui.hidden.includes(c[0]) ? "" : "checked"}>${esc(c[1])}</label>`).join("") : "");
  }).join("");
  P.innerHTML = `
    <h4>Bölümler</h4>${chk("cards", "Özet kartları")}${chk("prog", "İlerleme çubuğu")}${chk("filters", "Filtre çubukları")}${chk("info", "Açıklama")}${chk("detail", "Ayrıntı paneli")}
    <h4>Yoğunluk</h4>${seg("den", [["compact", "Sıkı"], ["normal", "Normal"], ["wide", "Geniş"]], ui.den)}
    <h4>Vurgu rengi</h4>${seg("acc", [["amber", "Kehribar"], ["green", "Yeşil"], ["cyan", "Cam"], ["white", "Beyaz"]], ui.acc)}
    <h4>Yazı</h4>${seg("font", [["mono", "Tek aralıklı"], ["sans", "Sans"]], ui.font)}
    <h4>Sütunlar <span class="rowbtn"><button data-cols="all">Hepsi</button> <button data-cols="none">Hiçbiri</button></span></h4>${colsHtml}
    <button class="rst" data-reset="1">Görünümü sıfırla</button>`;
}
function wireUi() {
  const P = $("ui");
  $("uibtn").onclick = () => { P.hidden = !P.hidden; };
  document.addEventListener("mousedown", (ev) => { if (!P.hidden && !P.contains(ev.target) && ev.target !== $("uibtn")) P.hidden = true; });
  const redraw = () => { saveUi(); applyUi(); if (tab === "mah") renderMah(); };
  P.addEventListener("change", (ev) => {
    const d = ev.target.dataset;
    if (d.p) { ui.panels[d.p] = ev.target.checked; redraw(); if (d.p === "detail" && cur >= 0) panel(shown[cur]); }
    else if (d.g) {
      if (ev.target.checked) { f.groups.add(d.g); if (!ui.open.includes(d.g)) ui.open.push(d.g); } else f.groups.delete(d.g);
      buildChips(); redraw(); uiPanel();
    }
    else if (d.c) { ui.hidden = ev.target.checked ? ui.hidden.filter((k) => k !== d.c) : [...ui.hidden, d.c]; redraw(); }
  });
  P.addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    const d = b.dataset;
    if (d.den) ui.den = d.den; else if (d.acc) ui.acc = d.acc; else if (d.font) ui.font = d.font;
    else if (d.open) ui.open = ui.open.includes(d.open) ? ui.open.filter((x) => x !== d.open) : [...ui.open, d.open];
    else if (d.cols) ui.hidden = d.cols === "all" ? [] : COLS().map((c) => c[0]).filter((k) => k !== "ad");
    else if (d.reset) { Object.assign(ui, { panels: { ...PANELS }, den: "normal", acc: "amber", font: "mono", hidden: [], open: [], widths: {} }); f.groups = new Set(["temel", "kaynak", "not", "you2"]); buildChips(); }
    else return;
    redraw(); uiPanel();
  });
}

// --- command line
const TAB_ALIAS = { iller: "il", il: "il", ilceler: "ilce", ilce: "ilce", yerlesim: "yer", yerlesimler: "yer", semt: "semt", semtler: "semt", mahalle: "mah", mah: "mah", koy: "mah" };
const HELP = "16 nilüfer · bursa · hatay antakya   → il / ilçe (plaka da olur)\nbs>6  bs<3   belirsizlik · n>5000  n<300   nüfus\nbekleyen · verilmis · kurum   → karar / kurum filtresi\niller ilceler yerlesim semt mahalle   → sekme (F1-F5)\nsifirla   → filtreleri temizle";
function cmdMsg(t) {
  const m = $("cmdmsg");
  m.textContent = t; m.style.display = t ? "block" : "none";
  clearTimeout(cmdMsg.t);
  if (t) cmdMsg.t = setTimeout(() => { m.style.display = "none"; }, 6000);
}
function runCmd(text) {
  text = text.trim();
  if (!text) return;
  if (text === "?") { cmdMsg(HELP); return; }
  const done = [], free = [];
  let goTab = null;
  for (const tok of text.split(/\s+/)) {
    const low = fold(tok);
    let m;
    if ((m = /^bs(>=|<=|>|<|=)(\d+(?:[.,]\d+)?)$/.exec(low))) {
      const v = parseFloat(m[2].replace(",", "."));
      if (m[1][0] === ">") xf.bsMin = v; else if (m[1][0] === "<") xf.bsMax = v; else { xf.bsMin = v; xf.bsMax = v; }
      done.push(`belirsizlik ${m[1]} ${fmt(v, v % 1 ? 1 : 0)}`); goTab = "mah";
    } else if ((m = /^n(>=|<=|>|<)(\d+)$/.exec(low))) {
      if (m[1][0] === ">") $("nMin").value = m[2]; else xf.nMax = +m[2];
      done.push(`nüfus ${m[1]} ${fmt(+m[2])}`); goTab = "mah";
    } else if (low === "bekleyen") { f.kr = new Set(["bos"]); f.kurum = false; done.push("karar bekleyen"); goTab = "mah"; }
    else if (low === "verilmis") { f.kr = new Set(["dolu"]); f.kurum = false; done.push("karar verilmiş"); goTab = "mah"; }
    else if (low === "kurum") { f.kurum = true; done.push("yalnız kurum"); goTab = "mah"; }
    else if (low === "sifirla") {
      f.ih = new Set(["uyumlu", "hafif", "cok"]); f.bs = new Set(BANDS.map((b) => b[0])); f.on = new Set(CLASSES); f.kr = new Set(["bos", "dolu"]); f.kurum = false;
      Object.assign(xf, { bsMin: 0, bsMax: 10, nMax: Infinity }); $("nMin").value = ""; $("q").value = "";
      for (const r of rows) { selIl.add(get(r, "il")); selIlce.add(ilceKey(r)); }
      focus = null; drawIl(); drawIlce(); done.push("filtreler sıfırlandı");
    } else if (TAB_ALIAS[low]) goTab = TAB_ALIAS[low];
    else free.push(tok);
  }
  // place names: plate number or province name, then a district name inside it
  const ilNames = [...new Set(rows.map((r) => get(r, "il")))];
  const plate = new Map(rows.map((r) => [+get(r, "id").slice(3, 5), get(r, "il")]));
  const rest = [];
  let ilHit = null;
  for (const tok of free) {
    const t = fold(tok);
    const il = /^\d{1,2}$/.test(t) ? plate.get(+t) : ilNames.find((n) => fold(n) === t) || (t.length >= 3 && ilNames.find((n) => fold(n).startsWith(t)));
    if (il && !ilHit) ilHit = il; else rest.push(tok);
  }
  let ilceHit = null;
  const pool = new Set(rows.filter((r) => !ilHit || get(r, "il") === ilHit).map((r) => get(r, "ilce")));
  for (const tok of [...rest]) {
    const t = fold(tok);
    const hit = [...pool].find((n) => fold(n) === t) || (t.length >= 3 && [...pool].find((n) => fold(n).startsWith(t)));
    if (hit && !ilceHit) { ilceHit = hit; rest.splice(rest.indexOf(tok), 1); }
  }
  if (ilceHit) {
    const keys = rows.filter((r) => get(r, "ilce") === ilceHit && (!ilHit || get(r, "il") === ilHit));
    selIl.clear(); selIlce.clear();
    for (const r of keys) { selIl.add(get(r, "il")); selIlce.add(ilceKey(r)); }
    focus = null; drawIl(); drawIlce(); done.unshift(`${[...selIl].join("/")} · ${ilceHit}`); goTab = goTab || "mah";
  } else if (ilHit) {
    selIl.clear(); selIl.add(ilHit); resetIlce(); focus = null; drawIl(); drawIlce(); done.unshift(ilHit); goTab = goTab || "ilce";
  }
  if (free.length) { $("q").value = rest.join(" "); if (rest.length) done.push(`ara: ${rest.join(" ")}`); }
  buildChips(); limit = PAGE;
  if (goTab && goTab !== tab) setTab(goTab); else refresh();
  cmdMsg(done.length ? `› ${done.join(" · ")}  →  ${fmt(shown.length)} satır` : `komut anlaşılmadı: ${text}   (? yardım)`);
}
function wireCmd() {
  $("cmd").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") { runCmd(ev.target.value); ev.target.value = ""; }
    else if (ev.key === "Escape") { ev.target.blur(); cmdMsg(""); }
  });
  document.addEventListener("keydown", (ev) => {
    if (/^F[1-5]$/.test(ev.key) && !ev.ctrlKey && !ev.shiftKey && !ev.altKey) { ev.preventDefault(); setTab(Object.keys(TABS)[+ev.key[1] - 1]); return; }
    if ((ev.key === "/" || ev.key === ":") && !/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) { ev.preventDefault(); $("cmd").focus(); $("cmd").select(); }
  });
  const tick = () => { const d = new Date(); $("clock").textContent = `${d.toLocaleDateString("tr-TR")} ${d.toLocaleTimeString("tr-TR")}`; };
  tick(); setInterval(tick, 1000);
}
main();
