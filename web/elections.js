/* Election comparison page.
 *
 * Everything shown here is derived in the browser from raw counts in
 * public/elections/: the files hold registered / voted / valid / votes-per-party and
 * nothing else, so a change to a definition (which party sits in which bloc, how the
 * effective number of parties is normalised) is a change to this file alone.
 *
 * Three scopes are always compared: the selected district, its province, and the
 * country. Picking no district drops the page to province vs country.
 */

const IDX = "../public/elections/index.json";
const PROV = (slug) => `../public/elections/${slug}.json`;

const state = { index: null, province: null, year: null, provinceSlug: null, districtSlug: "" };

const fmt = (n) => n.toLocaleString("tr-TR");
const pct = (n) => (n === null || n === undefined ? "—" : n.toFixed(1).replace(".", ",") + "%");
const num2 = (n) => (n === null || n === undefined ? "—" : n.toFixed(2).replace(".", ","));

/* ---- derived measures -------------------------------------------------- */

// YTP is two unrelated parties: right in 1961-69, İsmail Cem's centre-left party in 2002.
function blocOf(party, year) {
  if (party === "YTP") return year === "2002" ? "left" : "right";
  return state.index.blocs[party] || "other";
}

function measures(entry, year) {
  if (!entry) return null;
  const kurdish = new Set(state.index.kurdish);
  const indep = state.index.independent;
  let partyTotal = 0, left = 0, right = 0, other = 0, kurd = 0;
  const shares = [];
  for (const [party, votes] of Object.entries(entry.p)) {
    partyTotal += votes;
    const b = blocOf(party, year);
    if (b === "left") left += votes; else if (b === "right") right += votes; else other += votes;
    if (kurdish.has(party)) kurd += votes;
    shares.push({ party, votes });
  }
  // Effective number of parties (Laakso-Taagepera). Independents are a pooled column,
  // not a party, so they are dropped and the shares renormalised.
  const forEnp = shares.filter((s) => s.party !== indep);
  const enpBase = forEnp.reduce((a, s) => a + s.votes, 0);
  const enp = enpBase ? 1 / forEnp.reduce((a, s) => a + (s.votes / enpBase) ** 2, 0) : null;

  shares.sort((a, b) => b.votes - a.votes);
  const valid = entry.g || partyTotal;
  return {
    registered: entry.e,
    voted: entry.v,
    valid: entry.g,
    partyTotal,
    shares: shares.map((s) => ({ ...s, share: (100 * s.votes) / valid })),
    turnout: entry.e ? (100 * entry.v) / entry.e : null,
    invalid: entry.v ? (100 * (entry.v - entry.g)) / entry.v : null,
    lost: entry.e ? (100 * (entry.e - entry.g)) / entry.e : null,
    left: partyTotal ? (100 * left) / partyTotal : null,
    right: partyTotal ? (100 * right) / partyTotal : null,
    other: partyTotal ? (100 * other) / partyTotal : null,
    leftNoKurdish: partyTotal ? (100 * (left - kurd)) / partyTotal : null,
    enp,
    winner: shares.length ? (100 * shares[0].votes) / valid : null,
    winnerName: shares.length ? shares[0].party : "—",
  };
}

/* ---- current selection ------------------------------------------------- */

function scopes() {
  const out = [];
  const p = state.province;
  const d = state.districtSlug && p.districts[state.districtSlug];
  if (d) out.push({ key: "unit", name: d.name, colour: "var(--unit)", years: d.years });
  out.push({
    key: "prov",
    name: p.name,
    colour: d ? "var(--prov)" : "var(--unit)",
    years: p.total,
  });
  out.push({ key: "tr", name: "Türkiye", colour: "var(--tr)", years: state.index.national });
  return out;
}

/* ---- chart helpers ----------------------------------------------------- */

const SVGNS = "http://www.w3.org/2000/svg";
function el(name, attrs, text) {
  const node = document.createElementNS(SVGNS, name);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
}

// Axis ticks on a round step, so the labels read 0/10/20/… rather than 0/13/25/….
function axisTicks(max) {
  if (!(max > 0)) return { top: 1, ticks: [0, 1] };
  const raw = max / 4;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * p).find((s) => s >= raw) || 10 * p;
  const top = Math.ceil(max / step) * step;
  const ticks = [];
  for (let v = 0; v <= top + step / 1000; v += step) ticks.push(v);
  return { top, ticks };
}

const tickLabel = (v, unit) =>
  (unit === "%" ? "%" : "") + (Number.isInteger(v) ? v : v.toFixed(1).replace(".", ","));

/* ---- party columns ----------------------------------------------------- */

function drawParties() {
  const host = document.getElementById("parties");
  host.textContent = "";
  const year = state.year;
  const rows = scopes().map((s) => ({ ...s, m: measures(s.years[year], year) }));
  const lead = rows[0].m;
  if (!lead) {
    host.textContent = "Bu seçim için bu birimde veri yok.";
    document.getElementById("partyKeys").textContent = "";
    return;
  }
  // Parties worth a column: top of the selected unit, plus anything above 3% anywhere.
  const seen = new Map();
  for (const r of rows) {
    if (!r.m) continue;
    for (const s of r.m.shares) if (s.share >= 3) seen.set(s.party, true);
  }
  for (const s of lead.shares.slice(0, 6)) seen.set(s.party, true);
  const parties = [...seen.keys()]
    .map((p) => ({ p, share: lead.shares.find((s) => s.party === p)?.share || 0 }))
    .sort((a, b) => b.share - a.share)
    .slice(0, 10)
    .map((x) => x.p);

  const W = Math.max(620, parties.length * 92), H = 300;
  const pad = { l: 40, r: 8, t: 30, b: 30 }; // top: room for the sideways value labels
  const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
  const { top, ticks } = axisTicks(
    Math.max(...rows.flatMap((r) => (r.m ? parties.map((p) => r.m.shares.find((s) => s.party === p)?.share || 0) : [0])))
  );
  const svg = el("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` });

  for (const v of ticks) {
    const y = pad.t + plotH - (plotH * v) / top;
    svg.appendChild(el("line", { class: "grid", x1: pad.l, x2: W - pad.r, y1: y, y2: y }));
    svg.appendChild(el("text", { x: pad.l - 6, y: y + 3.5, "text-anchor": "end" }, tickLabel(v, "%")));
  }

  const bandW = plotW / parties.length;
  const drawn = rows.filter((r) => r.m);
  const barW = Math.min(20, (bandW * 0.7) / drawn.length);
  parties.forEach((party, i) => {
    const cx = pad.l + bandW * (i + 0.5);
    const x0 = cx - (barW * drawn.length) / 2;
    drawn.forEach((r, j) => {
      const share = r.m.shares.find((s) => s.party === party)?.share || 0;
      const h = (plotH * share) / top;
      const bx = x0 + j * barW, by = pad.t + plotH - h;
      svg.appendChild(
        el("rect", { x: bx, y: by, width: barW - 2, height: Math.max(h, 0), fill: r.colour, rx: 1 })
      ).appendChild(el("title", {}, `${r.name} — ${party}: ${pct(share)}`));
      // Every bar carries its own number, turned on its side so three fit in a band:
      // hover is not a way to read a chart on paper or at a glance.
      const tx = bx + (barW - 2) / 2, ty = by - 4;
      svg.appendChild(
        el(
          "text",
          { class: "val", x: tx, y: ty, "text-anchor": "start", transform: `rotate(-90 ${tx} ${ty})` },
          share >= 0.05 ? share.toFixed(1).replace(".", ",") : ""
        )
      );
    });
    svg.appendChild(el("text", { x: cx, y: H - pad.b + 15, "text-anchor": "middle" }, party));
  });
  svg.appendChild(el("line", { class: "axis", x1: pad.l, x2: W - pad.r, y1: pad.t + plotH, y2: pad.t + plotH }));
  host.appendChild(svg);

  document.getElementById("partyKeys").innerHTML = drawn
    .map((r) => `<span><i style="background:${r.colour}"></i>${r.name}</span>`)
    .join("");
  const missing = lead.valid - lead.partyTotal;
  document.getElementById("partyNote").textContent =
    missing > 0
      ? `Çubukların üzerindeki sayı geçerli oy içindeki paydır (%). Tabloda ayrı satırı ` +
        `olmayan küçük partiler (${fmt(missing)} oy, geçerli oyun ` +
        `%${((100 * missing) / lead.valid).toFixed(1).replace(".", ",")}'i) dökümde yer almıyor.`
      : "Çubukların üzerindeki sayı geçerli oy içindeki paydır (%).";
}

/* ---- summary table ----------------------------------------------------- */

function drawSummary() {
  const year = state.year;
  const rows = scopes().map((s) => ({ ...s, m: measures(s.years[year], year) })).filter((r) => r.m);
  const lines = [
    ["Kayıtlı seçmen", (m) => fmt(m.registered)],
    ["Geçerli oy", (m) => fmt(m.valid)],
    ["Katılım", (m) => pct(m.turnout)],
    ["Geçersiz oy (kullanılan içinde)", (m) => pct(m.invalid)],
    ["Kayıp oy (kayıtlı içinde)", (m) => pct(m.lost)],
    ["Birinci parti", (m) => `${m.winnerName} ${pct(m.winner)}`],
    ["Sol blok", (m) => pct(m.left)],
    ["Sağ blok", (m) => pct(m.right)],
    ["Blok dışı", (m) => pct(m.other)],
    ["Etkin parti sayısı", (m) => num2(m.enp)],
  ];
  document.getElementById("summary").innerHTML =
    `<thead><tr><th>Ölçüt</th>${rows.map((r) => `<th>${r.name}</th>`).join("")}</tr></thead>` +
    `<tbody>${lines
      .map(
        ([label, f]) =>
          `<tr><td>${label}</td>${rows.map((r) => `<td class="n">${f(r.m)}</td>`).join("")}</tr>`
      )
      .join("")}</tbody>`;
}

/* ---- time series ------------------------------------------------------- */

const METRIC_UNIT = { enp: "", left: "%", right: "%", leftNoKurdish: "%", turnout: "%", invalid: "%", lost: "%", winner: "%" };

function drawSeries() {
  const host = document.getElementById("series");
  host.textContent = "";
  const metric = document.getElementById("metric").value;
  const years = state.index.years;
  const rows = scopes().map((s) => ({
    ...s,
    points: years.map((y, i) => {
      const m = measures(s.years[y.id], y.id);
      const v = m ? m[metric] : null;
      return v === null || v === undefined ? null : { i, v };
    }),
  }));

  const all = rows.flatMap((r) => r.points.filter(Boolean).map((p) => p.v));
  if (!all.length) { host.textContent = "Veri yok."; return; }
  const W = 900, H = 320, pad = { l: 44, r: 34, t: 16, b: 50 };
  const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
  const { top, ticks } = axisTicks(Math.max(...all));
  const svg = el("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` });
  const unit = METRIC_UNIT[metric];

  for (const v of ticks) {
    const y = pad.t + plotH - (plotH * v) / top;
    svg.appendChild(el("line", { class: "grid", x1: pad.l, x2: W - pad.r, y1: y, y2: y }));
    svg.appendChild(el("text", { x: pad.l - 6, y: y + 3.5, "text-anchor": "end" }, tickLabel(v, unit)));
  }
  const x = (i) => pad.l + (plotW * i) / Math.max(years.length - 1, 1);
  const y = (v) => pad.t + plotH - (plotH * v) / top;

  years.forEach((yr, i) => {
    const label = yr.label.replace("2015 ", "15-");
    svg.appendChild(
      el("text", {
        x: x(i), y: H - pad.b + 16, "text-anchor": "end",
        transform: `rotate(-45 ${x(i)} ${H - pad.b + 16})`,
      }, label)
    );
  });

  for (const r of rows) {
    // Gaps are real: a district can be missing from an election (renamed, split, or the
    // report lists it under its province centre). Segments are broken, not bridged.
    let run = [];
    const flush = () => {
      if (run.length > 1) {
        svg.appendChild(el("polyline", {
          points: run.map((p) => `${x(p.i)},${y(p.v)}`).join(" "),
          fill: "none", stroke: r.colour, "stroke-width": 2,
        }));
      }
      run = [];
    };
    for (const p of r.points) { if (p) run.push(p); else flush(); }
    flush();
    const drawnPoints = r.points.filter(Boolean);
    for (const p of drawnPoints) {
      const dot = el("circle", { cx: x(p.i), cy: y(p.v), r: 3, fill: r.colour });
      dot.appendChild(el("title", {}, `${r.name} — ${years[p.i].label}: ${unit === "%" ? pct(p.v) : num2(p.v)}`));
      svg.appendChild(dot);
    }
    // Numbers on the chart itself: every point of the selected place, and the last
    // point of the two reference lines. Hover alone is not readable at a glance.
    const labelled = r === rows[0] ? drawnPoints : drawnPoints.slice(-1);
    for (const p of labelled) {
      // Put the number on the side of the line that is free: above when this series
      // runs highest at that election, below when another line sits over it.
      const above = rows.every((o) => {
        const q = o.points[p.i];
        return o === r || !q || q.v <= p.v;
      });
      const last = p.i === years.length - 1;
      svg.appendChild(
        el(
          "text",
          {
            class: "val",
            x: x(p.i) + (last ? 6 : p.i === 0 ? -2 : 0),
            y: y(p.v) + (above ? -8 : 14),
            "text-anchor": last ? "start" : p.i === 0 ? "start" : "middle",
            style: `fill:${r.colour}`,
          },
          unit === "%" ? p.v.toFixed(1).replace(".", ",") : num2(p.v)
        )
      );
    }
  }
  svg.appendChild(el("line", { class: "axis", x1: pad.l, x2: W - pad.r, y1: pad.t + plotH, y2: pad.t + plotH }));
  host.appendChild(svg);

  document.getElementById("seriesKeys").innerHTML = rows
    .map((r) => `<span><i style="background:${r.colour}"></i>${r.name}</span>`)
    .join("");
  const blocMetric = metric === "left" || metric === "right" || metric === "leftNoKurdish";
  document.getElementById("seriesNote").textContent = blocMetric
    ? "2007 ve 2011'de Kürt siyaseti bağımsız adaylarla girdi; o iki seçimde bu oylar blok " +
      "dışında, 'bağımsız' sütununda görünür. Blok ayrımı bir yorumdur; " +
      "scripts/build_election_series.py içinde açıkça listelenmiştir."
    : "";
}

/* ---- wiring ------------------------------------------------------------ */

function draw() {
  const p = state.province;
  const d = state.districtSlug && p.districts[state.districtSlug];
  const yearLabel = state.index.years.find((y) => y.id === state.year).label;
  document.getElementById("title").textContent = d ? `${d.name}, ${p.name}` : p.name;
  document.getElementById("lead").textContent =
    `${yearLabel} milletvekili genel seçimi — ` +
    (d ? `ilçe, il ve Türkiye karşılaştırması` : `il ve Türkiye karşılaştırması`);
  document.getElementById("source").textContent = state.index.source;
  drawParties();
  drawSummary();
  drawSeries();
  const q = new URLSearchParams({ il: state.provinceSlug, yil: state.year });
  if (state.districtSlug) q.set("ilce", state.districtSlug);
  history.replaceState(null, "", "?" + q);
}

function fillDistricts() {
  const sel = document.getElementById("district");
  const entry = state.index.provinces.find((p) => p.slug === state.provinceSlug);
  sel.innerHTML =
    `<option value="">— il geneli —</option>` +
    entry.districts.map((d) => `<option value="${d.slug}">${d.name}</option>`).join("");
  sel.value = state.districtSlug;
}

async function loadProvince(slug) {
  state.province = await (await fetch(PROV(slug))).json();
  state.provinceSlug = slug;
}

async function init() {
  state.index = await (await fetch(IDX)).json();
  const q = new URLSearchParams(location.search);

  const ysel = document.getElementById("year");
  ysel.innerHTML = state.index.years.map((y) => `<option value="${y.id}">${y.label}</option>`).join("");
  state.year = state.index.years.some((y) => y.id === q.get("yil"))
    ? q.get("yil")
    : state.index.years[state.index.years.length - 1].id;
  ysel.value = state.year;

  const psel = document.getElementById("province");
  psel.innerHTML = state.index.provinces.map((p) => `<option value="${p.slug}">${p.name}</option>`).join("");
  const wanted = state.index.provinces.some((p) => p.slug === q.get("il")) ? q.get("il") : "bursa";
  psel.value = wanted;
  await loadProvince(wanted);
  // Opening the page with nothing selected lands on the İznik pilot.
  const askedDistrict = q.has("il") || q.has("ilce") ? q.get("ilce") : "iznik";
  state.districtSlug = state.province.districts[askedDistrict] ? askedDistrict : "";
  fillDistricts();

  ysel.onchange = () => { state.year = ysel.value; draw(); };
  psel.onchange = async () => {
    await loadProvince(psel.value);
    state.districtSlug = "";
    fillDistricts();
    draw();
  };
  document.getElementById("district").onchange = (e) => { state.districtSlug = e.target.value; draw(); };
  document.getElementById("metric").onchange = drawSeries;

  draw();
}

init();
