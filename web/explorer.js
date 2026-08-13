// The explorer shell: one skeleton every indicator is drawn through (decision K10).
//
// Three rules keep it reusable:
//   - nothing is spelled out here. Labels, units, precision, which breakdowns exist and
//     which views are allowed all come from the dictionary through meta.json (K1, K7).
//   - the shell decides layout, the indicator decides content. Adding an indicator is a
//     dictionary + export change; this file should not need to know.
//   - colours and sizes come from theme.css tokens, never from literals, so the settings
//     panel can restyle the whole page including the charts (K5).

// region Look — reader-adjustable theme axes

// OWID's accent hues: their link blue, teal, salmon and purple.
const ACCENTS = [
    {id: "mavi", dark: "#7fa8d8", light: "#286bbb"},
    {id: "yesil", dark: "#6fbfae", light: "#00847e"},
    {id: "turuncu", dark: "#e8735c", light: "#e56e5a"},
    {id: "mor", dark: "#b98ad6", light: "#6d3e91"},
];

// Typeface is a setting, not a constant: OWID's pairing is the default, but a reader on
// a machine without those faces (or who simply prefers the system UI font) should not be
// stuck with the fallback. Empty strings mean "use the token from theme.css".
const FACES = [
    {id: "owid", label: "OWID", text: "", display: ""},
    {
        id: "sistem",
        label: "Sistem",
        text: '"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif',
        display: '"Segoe UI Variable Display", "Segoe UI", system-ui, sans-serif',
    },
    {
        id: "serif",
        label: "Serif",
        text: 'Georgia, "Times New Roman", serif',
        display: 'Georgia, "Times New Roman", serif',
    },
];

const DEFAULT_LOOK = {theme: "dark", font: 100, density: 100, accent: "mavi", face: "owid"};
const LOOK_KEY = "veriatlas.look";

function loadLook() {
    try {
        return {...DEFAULT_LOOK, ...JSON.parse(localStorage.getItem(LOOK_KEY) || "{}")};
    } catch {
        return {...DEFAULT_LOOK};
    }
}

let look = loadLook();

function applyLook() {
    const root = document.documentElement;
    root.dataset.theme = look.theme;
    root.style.setProperty("--font-scale", look.font / 100);
    root.style.setProperty("--density", look.density / 100);

    const face = FACES.find((f) => f.id === look.face) || FACES[0];
    root.style.setProperty("--font", face.text); // "" clears the inline override
    root.style.setProperty("--font-display", face.display);

    const accent = ACCENTS.find((a) => a.id === look.accent) || ACCENTS[0];
    root.style.setProperty("--accent", look.theme === "light" ? accent.light : accent.dark);
    root.style.setProperty("--panel-heading", look.theme === "light" ? accent.light : accent.dark);

    localStorage.setItem(LOOK_KEY, JSON.stringify(look));
    syncSettingsPanel();
}

function syncSettingsPanel() {
    $("set-font").value = look.font;
    $("set-density").value = look.density;
    $("set-font-value").textContent = "%" + look.font;
    $("set-density-value").textContent = "%" + look.density;

    for (const button of $("set-theme").children) {
        button.classList.toggle("on", button.dataset.value === look.theme);
    }
    for (const button of $("set-accent").children) {
        button.classList.toggle("on", button.dataset.value === look.accent);
    }
    for (const button of $("set-face").children) {
        button.classList.toggle("on", button.dataset.value === look.face);
    }
}

function buildSettingsPanel() {
    $("set-accent").innerHTML = ACCENTS.map(
        (a) => '<button data-value="' + a.id + '" title="' + a.id +
               '" style="background:' + a.dark + '"></button>'
    ).join("");

    $("set-face").innerHTML = FACES.map(
        (f) => '<button data-value="' + f.id + '">' + f.label + "</button>"
    ).join("");

    $("settings-toggle").onclick = () => {
        const body = $("settings-body");
        body.hidden = !body.hidden;
        $("settings-toggle").setAttribute("aria-expanded", String(!body.hidden));
    };

    $("set-theme").onclick = (ev) => pick(ev, (v) => { look.theme = v; });
    $("set-accent").onclick = (ev) => pick(ev, (v) => { look.accent = v; });
    $("set-face").onclick = (ev) => pick(ev, (v) => { look.face = v; });
    $("set-font").oninput = (ev) => { look.font = Number(ev.target.value); applyLook(); };
    $("set-density").oninput = (ev) => { look.density = Number(ev.target.value); applyLook(); render(); };
    $("set-reset").onclick = () => { look = {...DEFAULT_LOOK}; applyLook(); render(); };

    function pick(ev, set) {
        const button = ev.target.closest("button");
        if (!button) {
            return;
        }
        set(button.dataset.value);
        applyLook();
        // Charts read their colours from tokens, so they have to be redrawn.
        render();
    }
}

// endregion

// region Reading data

function $(id) {
    return document.getElementById(id);
}

function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

async function read(path) {
    try {
        const response = await fetch(path);
        if (!response.ok) {
            throw new Error(response.status + " " + response.statusText);
        }
        return response;
    } catch (cause) {
        cause.path = path;
        throw cause;
    }
}

function parseCsv(text) {
    const [header, ...lines] = text.trim().split(/\r?\n/);
    const cols = header.split(",");
    return lines.map((line) => {
        const cells = line.split(",");
        const row = Object.fromEntries(cols.map((c, i) => [c, cells[i]]));
        row.year = Number(row.year);
        row.value = Number(row.value);
        return row;
    });
}

const datasets = new Map();

async function dataset(indicator) {
    if (!indicator.dataset) {
        return null;
    }
    if (!datasets.has(indicator.dataset)) {
        const text = await (await read("../public/" + indicator.dataset)).text();
        datasets.set(indicator.dataset, parseCsv(text));
    }
    return datasets.get(indicator.dataset);
}

// Area levels are ids in the fact table; these are their Turkish names. They belong in
// the area registry the way indicator labels belong in the dictionary — until the
// registry exports them, this is the one label map left in the page.
const LEVEL_LABELS = {
    district: "İlçe",
    province: "İl",
    nuts2: "İBBS-2",
    nuts1: "İBBS-1",
    region: "Coğrafi bölge",
    country: "Türkiye",
};

/** Turkish for a dimension and for the ids it stores; both come from the dictionary. */
function dimLabel(dim) {
    return meta.dimensions?.[dim]?.label || dim;
}

function dimValue(dim, value) {
    if (value === TOTAL) {
        return "Tümü (topla)";
    }
    return meta.dimensions?.[dim]?.values?.[value] || value;
}
const VIEW_LABELS = {
    table: "▦ Tablo",
    map: "◍ Harita",
    line: "📈 Çizgi",
    bar: "📊 Sütun",
    pyramid: "⧗ Piramit",
};

const TOTAL = "__total__";

// endregion

// region State

const state = {
    indicator: null,
    rows: [],
    view: "line",
    level: "province",
    selection: [],
    dims: {},
    year: null,
    search: "",
    //: Chosen but hidden from the chart. Kept apart from the selection so muting is
    //: reversible without losing the area's place — and its colour.
    muted: [],
    //: Map colour ramp. Log by default; see the note in map().
    scale: "log",
    //: Pyramid panels: one shared scale, or each panel scaled to itself.
    panelScale: "shared",
    //: Province the map is opened into, or null for the whole country.
    focus: null,
};

let meta = null;
let catalogue = [];
let geometry = undefined; // undefined = not tried yet, null = absent

// Districts are fetched per province when one is opened: all 973 at once is 14 MB to
// draw a map the reader looks at one province of at a time.
const districts = new Map();

async function districtsOf(provinceId) {
    if (!districts.has(provinceId)) {
        try {
            const body = await (await read("../public/geo/districts/" + provinceId + ".geojson")).json();
            districts.set(provinceId, body);
        } catch {
            districts.set(provinceId, null);
        }
    }
    return districts.get(provinceId);
}

function levelsInData() {
    return [...new Set(state.rows.map((r) => r.level))]
        .sort((a, b) => Object.keys(LEVEL_LABELS).indexOf(a) - Object.keys(LEVEL_LABELS).indexOf(b));
}

function valuesOf(dim) {
    return [...new Set(state.rows.map((r) => r[dim]).filter((v) => v !== undefined))]
        .sort((a, b) => String(a).localeCompare(String(b), "tr", {numeric: true}));
}

function years() {
    return [...new Set(state.rows.map((r) => r.year))].sort((a, b) => a - b);
}

/** Rows matching the current breakdown choice, summed where a dim is set to "all".
 *  Summing is only offered for additive units, so this never adds up rates. */
function slice(level = state.level) {
    const rows = state.rows.filter(
        (r) => r.level === level &&
               (state.indicator.dims || []).every(
                   (d) => state.dims[d] === TOTAL || String(r[d]) === String(state.dims[d])
               )
    );

    const totals = new Map();
    for (const row of rows) {
        const key = row.area + "|" + row.year;
        const seen = totals.get(key);
        if (seen) {
            seen.value += row.value;
        } else {
            totals.set(key, {...row});
        }
    }
    return [...totals.values()];
}

function seriesFor(area) {
    return slice().filter((r) => r.area === area).sort((a, b) => a.year - b.year);
}

function areasAtLevel() {
    return [...new Set(state.rows.filter((r) => r.level === state.level).map((r) => r.area))]
        .sort((a, b) => a.localeCompare(b, "tr"));
}

function fmt(value) {
    if (value === undefined || Number.isNaN(value)) {
        return "—";
    }
    return value.toLocaleString("tr-TR", {
        minimumFractionDigits: state.indicator.decimals,
        maximumFractionDigits: state.indicator.decimals,
    });
}

// endregion

// region Left rail

function drawRail() {
    $("level").innerHTML = levelsInData()
        .map((l) => '<option value="' + l + '"' + (l === state.level ? " selected" : "") +
                    ">" + (LEVEL_LABELS[l] || l) + "</option>")
        .join("");

    // Chosen areas get their own block above the list. Searching filters the list, and
    // a selection that scrolls out of sight — or filters away — is a selection the
    // reader cannot undo.
    $("chosen").innerHTML = state.selection
        .map((area, i) => {
            const muted = state.muted.includes(area);
            return "<li class='" + (muted ? "muted" : "") + "' data-area='" + area + "'>" +
                   "<span class='dot' style='background:" + colour(i) + "'></span>" +
                   "<span class='name'>" + area + "</span>" +
                   "<button class='chip' data-act='mute' title='" +
                   (muted ? "Grafiğe geri koy" : "Grafikten gizle") + "'>" +
                   (muted ? "◎" : "◉") + "</button>" +
                   "<button class='chip' data-act='drop' title='Seçimden çıkar'>✕</button></li>";
        })
        .join("");
    $("chosen-head").hidden = !state.selection.length;

    const needle = state.search.toLocaleLowerCase("tr");
    const areas = areasAtLevel().filter((a) => a.toLocaleLowerCase("tr").includes(needle));

    $("entities").innerHTML = areas
        .map((area) => {
            const on = state.selection.includes(area);
            return '<li class="' + (on ? "on" : "") + '" data-area="' + area + '">' +
                   '<input type="checkbox" tabindex="-1"' + (on ? " checked" : "") + ">" +
                   '<span class="name">' + area + "</span>" +
                   '<span class="lvl">' + (LEVEL_LABELS[state.level] || state.level) + "</span></li>";
        })
        .join("");
}

/** Areas that are selected and not muted — what the charts actually draw. */
function drawn() {
    return state.selection.filter((a) => !state.muted.includes(a));
}

/** Default selection: the largest few at this level, so the page is never blank. */
function seedSelection() {
    const latest = Math.max(...years());
    state.muted = [];
    state.selection = slice()
        .filter((r) => r.year === latest)
        .sort((a, b) => b.value - a.value)
        .slice(0, 5)
        .map((r) => r.area);
}

// endregion

// region Breakdown strip

function drawDims() {
    const groups = [indicatorControl()];

    for (const dim of state.indicator.dims || []) {
        const options = valuesOf(dim);
        if (!options.length) {
            continue;
        }
        // "Tümü" means summing across the breakdown, which only means something for a
        // unit that adds up. A rate gets the raw values and nothing else.
        const all = state.indicator.additive
            ? '<option value="' + TOTAL + '"' + (state.dims[dim] === TOTAL ? " selected" : "") +
              ">" + dimValue(dim, TOTAL) + "</option>"
            : "";

        groups.push(
            "<div><div class='dim-label'>" + dimLabel(dim) + "</div>" +
            "<select data-dim='" + dim + "'>" + all +
            options
                .map((v) => '<option value="' + v + '"' +
                            (String(state.dims[dim]) === String(v) ? " selected" : "") + ">" +
                            dimValue(dim, v) + "</option>")
                .join("") +
            "</select></div>"
        );
    }

    $("dims").innerHTML = groups.join("");
}

function indicatorControl() {
    const options = meta.tree
        .map((topic) => {
            const items = topic.indicators
                .map((ind) => '<option value="' + ind.id + '"' +
                              (ind.id === state.indicator.id ? " selected" : "") +
                              (ind.available ? "" : " disabled") + ">" + ind.label +
                              (ind.available ? "" : " (veri yok)") + "</option>")
                .join("");
            return "<optgroup label='" + topic.topic + "'>" + items + "</optgroup>";
        })
        .join("");

    return "<div><div class='dim-label'>Gösterge</div>" +
           "<select id='indicator'>" + options + "</select></div>";
}

// endregion

// region Views

/** Which views this indicator offers, and why one may still be unusable right now. */
function viewState(view) {
    if (!(state.indicator.views || []).includes(view)) {
        return {enabled: false, reason: "Bu gösterge için tanımlı değil"};
    }
    if (view === "map" && !geometry) {
        return {enabled: false, reason: "Sınır geometrisi henüz çekilmedi"};
    }
    if (view === "map" && !levelsWithGeometry().includes(state.level)) {
        return {
            enabled: false,
            reason: (LEVEL_LABELS[state.level] || state.level) + " düzeyinde sınır yok",
        };
    }
    return {enabled: true, reason: ""};
}

function drawTabs() {
    $("tabs").innerHTML = Object.keys(VIEW_LABELS)
        .map((view) => {
            const {enabled, reason} = viewState(view);
            return "<button data-view='" + view + "'" +
                   (enabled ? "" : " disabled title='" + reason + "'") +
                   (view === state.view ? " class='on'" : "") + ">" + VIEW_LABELS[view] + "</button>";
        })
        .join("");
}

const PLOT_W = 1000;
const PLOT_H = 420;

/** A series keeps its colour by its place in the selection, muted or not. */
function colour(index) {
    return token("--series-" + ((index % 10) + 1));
}

function colourOf(area) {
    return colour(state.selection.indexOf(area));
}

function niceTicks(max) {
    const raw = max / 5;
    const magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) || magnitude * 10;
    return {step, top: Math.ceil(max / step) * step};
}

function lineChart() {
    const rows = drawn()
        .map((area) => ({area, pts: seriesFor(area), colour: colourOf(area)}))
        .filter((r) => r.pts.length);
    if (!rows.length) {
        return empty("Soldan en az bir alan seçin.");
    }

    const span = years();
    const [minYear, maxYear] = [span[0], span[span.length - 1]];
    const max = Math.max(...rows.flatMap((r) => r.pts.map((p) => p.value)));
    const {step, top} = niceTicks(max);

    const L = 96, R = 190, T = 16, B = 38;
    const x = (y) => L + ((y - minYear) / Math.max(1, maxYear - minYear)) * (PLOT_W - L - R);
    const yv = (v) => T + (1 - v / top) * (PLOT_H - T - B);

    let svg = '<svg class="plot" viewBox="0 0 ' + PLOT_W + " " + PLOT_H + '" role="img">';

    for (let v = 0; v <= top + step / 2; v += step) {
        svg += '<line x1="' + L + '" x2="' + (PLOT_W - R) + '" y1="' + yv(v) + '" y2="' + yv(v) +
               '" stroke="' + token("--stroke-divider") + '" stroke-dasharray="4 5"/>' +
               axisText(L - 12, yv(v) + 4, fmt(v), "end");
    }

    // The last year always gets a tick; a decade tick too close to it is dropped.
    const ticks = [];
    for (let y = Math.ceil(minYear / 10) * 10; y < maxYear - 3; y += 10) {
        ticks.push(y);
    }
    ticks.unshift(minYear);
    ticks.push(maxYear);
    for (const y of [...new Set(ticks)]) {
        svg += axisText(x(y), PLOT_H - 12, y, "middle");
    }

    // Right-hand labels are pushed apart from the bottom up so close series stay legible.
    const labels = rows
        .map((r) => ({r, y: yv(r.pts[r.pts.length - 1].value)}))
        .sort((a, b) => b.y - a.y);
    labels.forEach((l, i) => {
        if (i && labels[i - 1].y - l.y < 16) {
            l.y = labels[i - 1].y - 16;
        }
    });

    for (const row of rows) {
        const d = row.pts
            .map((p, i) => (i ? "L" : "M") + x(p.year).toFixed(1) + " " + yv(p.value).toFixed(1))
            .join(" ");
        const last = row.pts[row.pts.length - 1];
        const ly = labels.find((l) => l.r === row).y;

        svg += '<path d="' + d + '" fill="none" stroke="' + row.colour + '" stroke-width="2.5" stroke-linejoin="round"/>' +
               '<circle cx="' + x(last.year) + '" cy="' + yv(last.value) + '" r="3" fill="' + row.colour + '"/>' +
               '<path d="M' + (x(last.year) + 4) + " " + yv(last.value) + "L" + (PLOT_W - R + 8) + " " + ly +
               '" fill="none" stroke="' + row.colour + '" stroke-width="1" opacity=".55"/>' +
               '<text class="legend-label" x="' + (PLOT_W - R + 14) + '" y="' + (ly + 4) +
               '" fill="' + row.colour + '">' + row.area + "</text>";
    }

    hover = {kind: "line", rows, years: span, left: L, right: PLOT_W - R, x};
    return wrapPlot(svg + "</svg>");
}

// region Cursor readout
//
// What the eye cannot do off a chart is read a value. The line chart snaps to the
// nearest year and lists every drawn series at once — comparing five provinces means
// five numbers at the same instant, not five separate hovers. Bars and map areas answer
// for themselves, so those report just the shape under the cursor.

let hover = null;

function wrapPlot(svg) {
    return "<div class='plot-wrap'>" + svg +
           "<div class='guide' hidden></div><div class='tip' hidden></div></div>";
}

function tipRow(colour, name, value) {
    return "<div class='tip-row'><span class='dot' style='background:" + colour + "'></span>" +
           "<span class='tip-name'>" + name + "</span>" +
           "<span class='tip-value'>" + value + "</span></div>";
}

function bindHover() {
    const wrap = document.querySelector(".plot-wrap");
    if (!wrap || !hover) {
        return;
    }
    const svg = wrap.querySelector("svg");
    const tip = wrap.querySelector(".tip");
    const guide = wrap.querySelector(".guide");

    const place = (event, html, x) => {
        tip.innerHTML = html;
        tip.hidden = false;
        // Flip to the left of the cursor near the right edge so the box stays inside.
        const width = tip.offsetWidth;
        const left = event.offsetX + 16 + width > wrap.clientWidth
            ? event.offsetX - width - 16
            : event.offsetX + 16;
        tip.style.left = Math.max(0, left) + "px";
        tip.style.top = Math.min(event.offsetY + 12, wrap.clientHeight - tip.offsetHeight) + "px";

        guide.hidden = x === null;
        if (x !== null) {
            guide.style.left = x + "px";
        }
    };

    svg.onmouseleave = () => {
        tip.hidden = true;
        guide.hidden = true;
    };

    svg.onmousemove = (event) => {
        const scale = wrap.clientWidth / PLOT_W;

        if (hover.kind === "line") {
            const units = event.offsetX / scale;
            if (units < hover.left - 8 || units > hover.right + 8) {
                tip.hidden = true;
                guide.hidden = true;
                return;
            }
            const span = hover.years;
            const ratio = (units - hover.left) / Math.max(1, hover.right - hover.left);
            const year = span[Math.min(span.length - 1, Math.max(0, Math.round(ratio * (span.length - 1))))];

            const body = hover.rows
                .map((r) => {
                    const point = r.pts.find((p) => p.year === year);
                    return point ? tipRow(r.colour, r.area, fmt(point.value)) : "";
                })
                .join("");
            place(event, "<div class='tip-head'>" + year + " · " + state.indicator.unit + "</div>" + body,
                  hover.x(year) * scale);
            return;
        }

        const shape = event.target.closest("[data-value]");
        if (!shape) {
            tip.hidden = true;
            guide.hidden = true;
            return;
        }
        place(event,
              "<div class='tip-head'>" + shape.dataset.name + "</div>" +
              tipRow(shape.dataset.colour || token("--accent"), state.indicator.unit, shape.dataset.value),
              null);
    };
}

// endregion

function axisText(x, y, text, anchor) {
    return '<text x="' + x + '" y="' + y + '" text-anchor="' + anchor + '" fill="' +
           token("--text-tertiary") + '" font-size="13">' + text + "</text>";
}

function barChart() {
    const rows = drawn()
        .map((area) => {
            const point = seriesFor(area).find((p) => p.year === state.year);
            return point ? {area, value: point.value, colour: colourOf(area)} : null;
        })
        .filter(Boolean)
        .sort((a, b) => b.value - a.value);
    if (!rows.length) {
        return empty("Seçili alanların bu yıl için değeri yok.");
    }

    const L = 150, R = 130, T = 16;
    const max = Math.max(...rows.map((r) => r.value));
    const band = (PLOT_H - T - 16) / rows.length;

    let svg = '<svg class="plot" viewBox="0 0 ' + PLOT_W + " " + PLOT_H + '" role="img">';
    rows.forEach((row, i) => {
        const y = T + i * band + band * 0.18;
        const h = band * 0.64;
        const w = (row.value / max) * (PLOT_W - L - R);
        svg += '<rect x="' + L + '" y="' + y + '" width="' + w + '" height="' + h +
               '" rx="2" fill="' + row.colour + '" data-value="' + fmt(row.value) +
               '" data-name="' + row.area + '" data-colour="' + row.colour + '"/>' +
               axisText(L - 12, y + h / 2 + 5, row.area, "end") +
               axisText(L + w + 12, y + h / 2 + 5, fmt(row.value), "start");
    });

    hover = {kind: "shape"};
    return wrapPlot(svg + "</svg>");
}

function table() {
    const span = years();
    const columns = span.length > 8
        ? span.filter((_, i) => i % Math.ceil(span.length / 8) === 0).concat(span[span.length - 1])
        : span;
    const shown = [...new Set(columns)];

    if (!drawn().length) {
        return empty("Soldan en az bir alan seçin.");
    }

    let html = "<div style='max-height:" + PLOT_H + "px;overflow:auto'><table class='grid'><thead><tr><th>" +
               (LEVEL_LABELS[state.level] || state.level) + "</th>" +
               shown.map((y) => "<th>" + y + "</th>").join("") + "</tr></thead><tbody>";

    for (const area of drawn()) {
        const points = seriesFor(area);
        html += "<tr><td>" + area + "</td>" +
                shown.map((y) => "<td>" + fmt(points.find((p) => p.year === y)?.value) + "</td>").join("") +
                "</tr>";
    }
    return html + "</tbody></table></div>";
}

/** One pyramid per selected area, side by side, drawn on a shared scale.
 *
 *  A shared scale is the point: two pyramids each normalised to their own maximum
 *  compare shapes but hide that one province is ten times the other. Every pyramid is
 *  a fixed share of the width, so adding a third narrows all three rather than
 *  squeezing the last one. */
function pyramid() {
    const areas = drawn();
    if (!areas.length) {
        return empty("Soldan en az bir alan seçin.");
    }
    if (areas.length > 4) {
        return empty("Piramit en çok dört alan çizer; " + areas.length + " seçili.",
                     "Fazlasını soldaki listeden gizleyin");
    }

    const rowsOf = (area) =>
        state.rows.filter(
            (r) => r.level === state.level && r.year === state.year && r.area === area
        );

    const all = areas.flatMap(rowsOf);
    if (!all.length) {
        return empty("Bu yıl için kırılımlı değer yok.");
    }

    const bands = [...new Set(all.map((r) => r.age))].sort((a, b) =>
        String(a).localeCompare(String(b), "tr", {numeric: true}));
    const sexes = [...new Set(all.map((r) => r.sex))].sort();

    // Two questions, two scales. "How many people" wants one shared scale — İstanbul
    // towering over Afyonkarahisar is the answer. "What shape is this population" wants
    // each panel scaled to itself, or the smaller one is a sliver you cannot read.
    const shared = Math.max(...all.map((r) => r.value));
    const maxOf = (rows) => (state.panelScale === "own" ? Math.max(...rows.map((r) => r.value)) : shared);

    const T = 34;
    const cell = PLOT_W / areas.length;
    const band = (PLOT_H - T - 16) / bands.length;

    let svg = '<svg class="plot" viewBox="0 0 ' + PLOT_W + " " + PLOT_H + '" role="img">';

    areas.forEach((area, ai) => {
        const rows = rowsOf(area);
        const max = maxOf(rows);
        const mid = cell * ai + cell / 2;
        const arm = cell / 2 - 34;

        svg += '<text x="' + mid + '" y="14" text-anchor="middle" fill="' + colourOf(area) +
               '" font-size="13">' + area +
               (state.panelScale === "own" ? " · " + fmt(max) + " ölçek" : "") + "</text>";

        bands.forEach((label, i) => {
            const y = PLOT_H - 16 - (i + 1) * band + band * 0.15;
            const h = band * 0.7;
            sexes.forEach((s, si) => {
                const row = rows.find((r) => r.age === label && r.sex === s);
                if (!row) {
                    return;
                }
                const w = (row.value / max) * (arm - 16);
                svg += '<rect x="' + (si === 0 ? mid - 16 - w : mid + 16) + '" y="' + y +
                       '" width="' + w + '" height="' + h + '" fill="' + colour(si) +
                       '" rx="1" data-colour="' + colour(si) + '" data-name="' + area + " · " +
                       dimValue("sex", s) + " " + label + '" data-value="' + fmt(row.value) + '"/>';
            });
            if (ai === 0) {
                svg += axisText(4, y + h / 2 + 4, label, "start");
            }
        });
    });

    hover = {kind: "shape"};

    // Legend and scale switch live in HTML above the drawing: inside the SVG they sat at
    // the far edges and collided with the panel titles.
    const head = "<div class='map-head'>" +
        sexes
            .map((s, si) => "<span class='tip-row'><span class='dot' style='background:" +
                            colour(si) + "'></span>" + dimValue("sex", s) + "</span>")
            .join("") +
        "<span class='spacer'></span><span>Ölçek</span>" +
        "<button class='chip" + (state.panelScale !== "own" ? " on" : "") + "' data-panel='shared'>Ortak</button>" +
        "<button class='chip" + (state.panelScale === "own" ? " on" : "") + "' data-panel='own'>Kendi içinde</button>" +
        "</div>";

    return head + wrapPlot(svg + "</svg>");
}

/** Which area levels the geometry file actually carries shapes for. */
function levelsWithGeometry() {
    if (!geometry) {
        return [];
    }
    return [...new Set(geometry.features.map((f) => f.properties.area_level))];
}

function map() {
    if (!geometry) {
        return empty(
            "Harita için sınır geometrisi gerekiyor; henüz çekilmedi.",
            "uv run python scripts/fetch_geometry.py"
        );
    }

    const opened = state.focus ? districts.get(state.focus) : null;
    const features = opened
        ? opened.features
        : geometry.features.filter((f) => f.properties.area_level === state.level);
    if (!features.length) {
        return empty((LEVEL_LABELS[state.level] || state.level) + " düzeyinde sınır geometrisi yok.");
    }

    // Opened into a province, the map is a district map: it must read district rows and
    // scale to the largest district, not to İstanbul.
    const rows = slice(state.focus ? "district" : state.level).filter((r) => r.year === state.year);
    const byId = new Map(rows.map((r) => [r.area_id, r.value]));
    const values = features.map((f) => byId.get(f.properties.area_id)).filter((v) => v !== undefined);

    // An opened province usually has no values yet — the fact table stops at province
    // level. Draw the borders anyway and say so; an empty frame would read as an error.
    const [low, high] = values.length ? [Math.min(...values), Math.max(...values)] : [0, 0];

    // Equirectangular, which needs no projection library, but with the longitude scaled
    // by cos(latitude): without it Turkey comes out about a quarter too wide.
    const points = features.flatMap((f) => rings(f).flat());
    const lon = points.map((p) => p[0]);
    const lat = points.map((p) => p[1]);
    const [x0, x1, y0, y1] = [Math.min(...lon), Math.max(...lon), Math.min(...lat), Math.max(...lat)];
    const squeeze = Math.cos((((y0 + y1) / 2) * Math.PI) / 180);

    const scale = Math.min(
        (PLOT_W - 40) / ((x1 - x0) * squeeze),
        (PLOT_H - 56) / (y1 - y0)
    );
    const width = (x1 - x0) * squeeze * scale;
    const left = (PLOT_W - width) / 2;
    const px = (p) => [
        left + (p[0] - x0) * squeeze * scale,
        PLOT_H - 36 - (p[1] - y0) * scale,
    ];

    const base = token("--bg-control");
    const ink = token("--accent");

    // Population is spread over three orders of magnitude: on a linear ramp İstanbul is
    // the only province with any colour in it and the other eighty read as empty. Log is
    // the default for that reason; linear stays one click away because a ratio the
    // reader wants to see literally — a rate, a percentage — is better off on it.
    const logging = state.scale === "log" && low > 0;
    const position = (v) => {
        if (v === undefined) {
            return null;
        }
        if (logging) {
            return (Math.log(v) - Math.log(low)) / Math.max(1e-9, Math.log(high) - Math.log(low));
        }
        return (v - low) / Math.max(1e-9, high - low);
    };

    let svg = '<svg class="plot ' + (state.focus ? "" : "drillable") + '" viewBox="0 0 ' +
              PLOT_W + " " + PLOT_H + '" role="img">';
    for (const feature of features) {
        const value = byId.get(feature.properties.area_id);
        const t = position(value);
        const d = rings(feature)
            .map((ring) => "M" + ring.map((p) => px(p).map((n) => n.toFixed(1)).join(" ")).join("L") + "Z")
            .join(" ");
        svg += '<path class="area" data-area="' + feature.properties.area_id + '" d="' + d +
               '" fill="' + (t === null ? base : ink) + '" fill-opacity="' +
               (t === null ? 0.35 : (0.15 + 0.85 * t).toFixed(2)) + '" stroke="' +
               token("--bg-card") + '" stroke-width="0.6" data-name="' +
               feature.properties.name_tr + '" data-value="' +
               (value === undefined ? "veri yok" : fmt(value)) + '" data-colour="' + ink + '"/>';
    }
    svg += "</svg>";
    hover = {kind: "shape"};

    const scaleToggle = values.length
        ? "<span class='spacer'></span><span>Renk ölçeği</span>" +
          "<button class='chip" + (state.scale === "log" ? " on" : "") + "' data-scale='log'>Log</button>" +
          "<button class='chip" + (state.scale === "linear" ? " on" : "") + "' data-scale='linear'>Doğrusal</button>"
        : "";

    const head = "<div class='map-head'>" +
        (state.focus
            ? "<button class='link-inline' id='map-back'>← Türkiye</button><span>" +
              opened.name_tr + " · " + features.length + " ilçe" +
              (values.length ? "" : " · ilçe düzeyinde veri yok, sınırlar gösteriliyor") + "</span>"
            : "<span>Bir ile tıklayınca ilçeleri açılır.</span>") +
        scaleToggle + "</div>";

    return head + wrapPlot(svg) + (values.length ? legend(low, high, ink) : "");
}

function rings(feature) {
    const g = feature.geometry;
    return g.type === "Polygon" ? g.coordinates : g.coordinates.flat();
}

function legend(low, high, ink) {
    const stops = [0, 0.25, 0.5, 0.75, 1];
    return "<div style='display:flex;align-items:center;gap:8px;justify-content:flex-end;" +
           "color:var(--text-tertiary);font-size:var(--text-xs)'>" + fmt(low) +
           stops.map((t) => "<span style='width:26px;height:12px;background:" + ink +
                            ";opacity:" + (0.15 + 0.85 * t).toFixed(2) + "'></span>").join("") +
           fmt(high) + "</div>";
}

function empty(message, hint) {
    return "<div class='placeholder'><div>" + message + "</div>" +
           (hint ? "<pre>" + hint + "</pre>" : "") + "</div>";
}

const RENDERERS = {line: lineChart, bar: barChart, table, pyramid, map};

// endregion

// region Render

function render() {
    if (!state.indicator) {
        return; // the settings panel is live before the first dataset arrives
    }
    // A view can stop being available under you — switching to a level with no
    // boundaries, say. Fall back rather than draw an empty frame.
    if (!viewState(state.view).enabled) {
        state.view = (state.indicator.views || ["table"]).find((v) => viewState(v).enabled) || "table";
    }

    drawRail();
    drawDims();
    drawTabs();

    $("chart-title").textContent = state.indicator.label;
    $("chart-definition").textContent = state.indicator.definition || "";

    hover = null;
    $("view").innerHTML = RENDERERS[state.view]();
    bindHover();

    // The time control means different things per view: a line already shows every year,
    // the others stand on one. Rather than a control that lies, it hides.
    const perYear = state.view !== "line" && state.view !== "table";
    $("time").style.visibility = perYear ? "visible" : "hidden";

    const span = years();
    $("year").min = span[0];
    $("year").max = span[span.length - 1];
    $("year").value = state.year;
    $("year-from").textContent = span[0];
    $("year-to").textContent = state.year;

    $("chart-subtitle").textContent =
        state.indicator.unit + " · " + (LEVEL_LABELS[state.level] || state.level) +
        " · " + (perYear ? state.year : span[0] + "–" + span[span.length - 1]);

    drawSource();
    writeHash();
}

function drawSource() {
    const rows = slice();
    const flags = [...new Set(rows.map((r) => r.quality_flag).filter(Boolean))];
    const vintage = rows[0]?.vintage;
    const source = rows[0]?.source_id;

    $("source").innerHTML =
        "<b>Kaynak:</b> " + (source || "—") +
        flags.map((f) => "<span class='badge " + (f === "measured" ? "measured" : "estimated") + "'>" +
                         (f === "measured" ? "ölçüm" : "tahmin") + "</span>").join("") +
        "<br><span class='provenance'>veriatlas / " + state.indicator.id +
        (vintage ? " · sürüm " + vintage : "") + " · CC BY</span>";
}

// endregion

// region Sharing the current screen

function writeHash() {
    const params = new URLSearchParams({
        i: state.indicator.id,
        v: state.view,
        l: state.level,
        y: state.year,
        f: state.focus || "",
        a: state.selection.join("~"),
        ...Object.fromEntries(Object.entries(state.dims).map(([k, v]) => ["d." + k, v])),
    });
    history.replaceState(null, "", "#" + params);
}

function readHash() {
    return new URLSearchParams(location.hash.slice(1));
}

function downloadShown() {
    const rows = slice().filter((r) => drawn().includes(r.area));
    const header = "area,year,value,unit,indicator\n";
    const body = rows
        .map((r) => [r.area, r.year, r.value, state.indicator.unit, state.indicator.id].join(","))
        .join("\n");

    const url = URL.createObjectURL(new Blob([header + body], {type: "text/csv;charset=utf-8"}));
    const a = document.createElement("a");
    a.href = url;
    a.download = "veriatlas-" + state.indicator.id + ".csv";
    a.click();
    URL.revokeObjectURL(url);
}

// endregion

// region Switching indicator

async function useIndicator(id) {
    const indicator = catalogue.find((i) => i.id === id);
    state.indicator = indicator;

    const rows = await dataset(indicator);
    state.rows = rows || [];

    if (!state.rows.length) {
        // Still draw the strip: without it there is no way back to an indicator that
        // does have data.
        state.dims = {};
        drawDims();
        drawTabs();
        $("view").innerHTML = empty(
            indicator.label + " için henüz veri yüklenmedi.",
            "uv run python scripts/load.py"
        );
        return false;
    }

    const levels = levelsInData();
    state.level = levels.includes(state.level) ? state.level : levels[0];

    state.dims = {};
    for (const dim of indicator.dims || []) {
        const values = valuesOf(dim);
        // Default to the whole population where summing is meaningful, else the first
        // value: a chart of one arbitrary age band would be a lie by omission.
        state.dims[dim] = indicator.additive ? TOTAL : values[0];
    }

    const span = years();
    state.year = span[span.length - 1];
    if (!(indicator.views || []).includes(state.view)) {
        state.view = indicator.views[0];
    }

    seedSelection();
    return true;
}

// endregion

// region Wiring

function wire() {
    $("entities").onclick = (ev) => {
        const li = ev.target.closest("li");
        if (!li) {
            return;
        }
        const area = li.dataset.area;
        state.selection = state.selection.includes(area)
            ? state.selection.filter((a) => a !== area)
            : [...state.selection, area];
        render();
    };

    $("entity-search").oninput = (ev) => {
        state.search = ev.target.value;
        drawRail();
    };

    // "Select all" follows the search box: with a filter typed, it selects what the
    // reader is looking at, not all eighty-one.
    $("select-all").onclick = () => {
        const needle = state.search.toLocaleLowerCase("tr");
        const visible = areasAtLevel().filter((a) => a.toLocaleLowerCase("tr").includes(needle));
        state.selection = [...new Set([...state.selection, ...visible])];
        render();
    };

    $("select-none").onclick = () => {
        const needle = state.search.toLocaleLowerCase("tr");
        const visible = areasAtLevel().filter((a) => a.toLocaleLowerCase("tr").includes(needle));
        state.selection = state.selection.filter((a) => !visible.includes(a));
        render();
    };

    $("clear-selection").onclick = () => {
        state.selection = [];
        state.muted = [];
        render();
    };

    $("level").onchange = (ev) => {
        state.level = ev.target.value;
        state.focus = null;
        seedSelection();
        render();
    };

    $("dims").onchange = async (ev) => {
        if (ev.target.id === "indicator") {
            if (await useIndicator(ev.target.value)) {
                render();
            }
            return;
        }
        state.dims[ev.target.dataset.dim] = ev.target.value;
        render();
    };

    // The chosen block: hide a series without losing it, or drop it outright.
    $("chosen").onclick = (ev) => {
        const button = ev.target.closest("button");
        const area = ev.target.closest("li")?.dataset.area;
        if (!button || !area) {
            return;
        }
        if (button.dataset.act === "drop") {
            state.selection = state.selection.filter((a) => a !== area);
            state.muted = state.muted.filter((a) => a !== area);
        } else {
            state.muted = state.muted.includes(area)
                ? state.muted.filter((a) => a !== area)
                : [...state.muted, area];
        }
        render();
    };

    // Map drill-down: a province opens into its districts, and back out again.
    $("view").onclick = async (ev) => {
        if (ev.target.id === "map-back") {
            state.focus = null;
            render();
            return;
        }

        const scale = ev.target.closest("[data-scale]");
        if (scale) {
            state.scale = scale.dataset.scale;
            render();
            return;
        }

        const panel = ev.target.closest("[data-panel]");
        if (panel) {
            state.panelScale = panel.dataset.panel;
            render();
            return;
        }

        const area = ev.target.closest(".area");
        if (!area || state.view !== "map" || state.focus) {
            return;
        }

        const provinceId = area.dataset.area;
        if (await districtsOf(provinceId)) {
            state.focus = provinceId;
        }
        render();
    };

    $("tabs").onclick = (ev) => {
        const button = ev.target.closest("button");
        if (!button || button.disabled) {
            return;
        }
        state.view = button.dataset.view;
        render();
    };

    $("year").oninput = (ev) => {
        state.year = Number(ev.target.value);
        render();
    };

    $("play").onclick = playYears;
    $("download").onclick = downloadShown;
    $("share").onclick = async () => {
        await navigator.clipboard.writeText(location.href);
        $("share").textContent = "✓ Kopyalandı";
        setTimeout(() => { $("share").textContent = "↗ Bağlantı"; }, 1500);
    };

    document.addEventListener("click", (ev) => {
        if (!ev.target.closest(".settings")) {
            $("settings-body").hidden = true;
        }
    });
}

let playing = null;

function playYears() {
    if (playing) {
        clearInterval(playing);
        playing = null;
        $("play").textContent = "▶";
        return;
    }
    const span = years();
    $("play").textContent = "⏸";
    playing = setInterval(() => {
        const next = span[(span.indexOf(state.year) + 1) % span.length];
        state.year = next;
        render();
    }, 450);
}

// endregion

// region Start

async function start() {
    buildSettingsPanel();
    applyLook();
    wire();

    meta = await (await read("../public/meta.json")).json();
    catalogue = meta.tree.flatMap((t) => t.indicators);

    try {
        geometry = await (await read("../public/areas.geojson")).json();
    } catch {
        geometry = null; // absent, not broken: the map tab explains itself
    }

    const hash = readHash();
    const wanted = catalogue.find((i) => i.id === hash.get("i") && i.available);
    const first = wanted || catalogue.find((i) => i.available);
    if (!first) {
        $("view").innerHTML = empty("Sözlükte veri yüklenmiş gösterge yok.");
        return;
    }

    state.view = hash.get("v") || state.view;
    state.level = hash.get("l") || state.level;
    if (!(await useIndicator(first.id))) {
        return;
    }

    if (hash.get("a")) {
        state.selection = hash.get("a").split("~").filter(Boolean);
    }
    if (hash.get("y")) {
        state.year = Number(hash.get("y"));
    }
    if (hash.get("f") && (await districtsOf(hash.get("f")))) {
        state.focus = hash.get("f");
    }
    for (const dim of state.indicator.dims || []) {
        if (hash.get("d." + dim)) {
            state.dims[dim] = hash.get("d." + dim);
        }
    }

    $("rail-title").textContent = "VeriAtlas Veri Gezgini";
    $("rail-note").textContent =
        "Kaynak dosyalar public/ altından okunuyor; etiketler ve birimler sözlükten geliyor.";
    render();
}

start().catch((error) => {
    document.querySelector(".explorer").innerHTML =
        "<section class='panel'><h3>Veri okunamadı</h3>" +
        "<p>Sayfa dosyadan açıldığında tarayıcı yerel veriyi okumuyor. Bir sunucu üzerinden aç:</p>" +
        "<pre>cd C:\\veri\nuv run python -m http.server 8123</pre>" +
        "<p>Sonra: <a href='http://127.0.0.1:8123/web/explorer.html'>127.0.0.1:8123/web/explorer.html</a></p>" +
        "<p class='provenance'>Okunamayan yol: " + (error.path || "—") + " — " + error.message + "</p></section>";
});

// endregion
