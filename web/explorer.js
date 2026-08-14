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

/** Read a dataset, unpacking it if it arrived gzipped.
 *
 *  The district slice is 53 MB of CSV and 3.9 MB packed. The page unpacks it rather than
 *  leaving it to the server because it has to work off `python -m http.server`, which
 *  serves what it is given and negotiates nothing — an encoding the page arranges itself
 *  cannot be undone by where it is hosted. */
async function textOf(file) {
    const response = await read("../public/" + file);
    if (!file.endsWith(".gz")) {
        return response.text();
    }
    if (!window.DecompressionStream) {
        const error = new Error("Bu tarayıcı gzip açamıyor (DecompressionStream yok)");
        error.path = file;
        throw error;
    }
    const stream = response.body.pipeThrough(new DecompressionStream("gzip"));
    return new Response(stream).text();
}

async function part(file) {
    if (!datasets.has(file)) {
        datasets.set(file, parseCsv(await textOf(file)));
    }
    return datasets.get(file);
}

async function dataset(indicator) {
    if (!indicator.dataset) {
        return null;
    }
    return part(indicator.dataset);
}

/** Fetch the rows for a level that ships in its own file, if it has not arrived yet.
 *
 *  District population broken down by sex and age is fifty megabytes; sending it to
 *  every reader who came for a province line chart would be absurd, so the dictionary
 *  names a separate file per lazily-held level and the page collects it the first time
 *  the reader actually asks for that level (see LAZY_LEVELS in export_web.py). */
async function ensureLevel(level) {
    const file = state.indicator?.parts?.[level];
    if (!file || datasets.has(file)) {
        return;
    }
    const note = $("rail-note");
    const said = note.textContent;
    note.textContent = (LEVEL_LABELS[level] || level) + " verisi indiriliyor…";
    try {
        state.rows = state.rows.concat(await part(file));
        invalidate();
    } finally {
        note.textContent = said;
    }
}

// Area levels are ids in the fact table; these are their Turkish names. They belong in
// the area registry the way indicator labels belong in the dictionary — until the
// registry exports them, this is the one label map left in the page.
const LEVEL_LABELS = {
    neighbourhood: "Mahalle",
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
    //: Narrow the list by what an area sits inside, one entry per level above this one:
    //: {province: "Bursa", district: ""}. Empty means all of them.
    filters: {},
    //: Chosen but hidden from the chart. Kept apart from the selection so muting is
    //: reversible without losing the area's place — and its colour.
    muted: [],
    //: How the colour classes are cut: "quantile" (about as many areas in each) or
    //: "equal" (equal-width slices of the range). See the note above binEdges().
    scale: "quantile",
    //: Pyramid panels: one shared scale, or each panel scaled to itself.
    panelScale: "shared",
    //: Map ramp ends: "year" recomputes them per year, "fixed" spans every year drawn.
    scaleSpan: "year",
    //: Country map showing all 973 districts instead of the 81 provinces.
    districtView: false,
    //: The map's viewBox — what the reader has panned and zoomed to.
    mapView: {x: 0, y: 0, w: 1000, h: 420},
    //: Active derivation id, or "" for the measurement itself.
    derivation: "",
    //: Show each value as a share of its area's own total instead of the count itself.
    //: Absolute and relative answer different questions and the map needs both:
    //: Şanlıurfa's child population is smaller than Ankara's in people and much larger
    //: as a proportion.
    share: false,
    //: Province the map is opened into, or null for the whole country.
    focus: null,
};

let meta = null;
let catalogue = [];
let geometry = undefined; // undefined = not tried yet, null = absent

// Districts are fetched per province when one is opened: all 973 at once is 14 MB to
// draw a map the reader looks at one province of at a time.
const districts = new Map();

//: Flattened features for the country-wide district map, filled on first request.
let districtFeatures = [];

/** Every province's districts at once, for the country-wide district map. */
async function allDistricts() {
    const provinces = [...new Set(rowsAt("province").map((r) => r.area_id))];
    const files = await Promise.all(provinces.map(districtsOf));
    return files.filter(Boolean).flatMap((file) => file.features);
}

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

/** Levels the menu offers. From the dictionary, not from the rows in hand: a level whose
 *  file has not been fetched yet would otherwise be missing from the very menu that is
 *  supposed to trigger the fetch. */
function levelsInData() {
    const declared = state.indicator?.levels?.length
        ? state.indicator.levels
        : [...new Set(state.rows.map((r) => r.level))];
    return [...new Set(declared)]
        .sort((a, b) => Object.keys(LEVEL_LABELS).indexOf(a) - Object.keys(LEVEL_LABELS).indexOf(b));
}

/** The values a breakdown actually takes *at this level*.
 *
 *  The levels do not share a band set: the province file closes at 75+, the district
 *  export runs on to 90+. Listing every value found anywhere would offer 85-89 on a
 *  province map and draw nothing. A row whose dim is an empty string carries no
 *  breakdown at all and must not become a blank menu entry. */
/** The level actually on screen. The map draws districts whenever a province is opened
 *  or the country-wide district view is on, whatever the rail's level says — and the
 *  breakdown strip has to follow it, or the reader is offered province age bands over a
 *  district map. */
function effectiveLevel() {
    // Guarded on the indicator actually having districts. The district map is a mode the
    // reader turns on, and it used to survive a change of indicator: turning it on for
    // population and then picking median age left the map drawing districts for an
    // indicator published only per province, which came out as "İlçe düzeyinde kırılım
    // yok" while the level box still said İl.
    const districtMap =
        state.view === "map" &&
        (state.indicator.levels || []).includes("district") &&
        (state.focus || (state.districtView && districtFeatures.length));
    return districtMap ? "district" : state.level;
}

// region Working set
//
// The district slice is 697.000 rows, and almost everything the page draws starts by
// asking "the rows at this level". Done with a filter each time, one redraw walked the
// whole array a dozen times over — once per selected series in the line chart alone —
// and dragging the year slider became a slideshow. So the rows are bucketed by level
// once, and each derived answer is remembered until the rows or the choices change.

let working = {version: 0, byLevel: null, memo: new Map()};

/** Throw away everything derived from the rows. Called when the rows themselves change. */
function invalidate() {
    working = {version: working.version + 1, byLevel: null, memo: new Map()};
}

function rowsAt(level) {
    if (!working.byLevel) {
        working.byLevel = new Map();
        for (const row of state.rows) {
            const bucket = working.byLevel.get(row.level);
            if (bucket) {
                bucket.push(row);
            } else {
                working.byLevel.set(row.level, [row]);
            }
        }
    }
    return working.byLevel.get(level) || [];
}

/** Remember `build()` under a key that spells out everything it depends on.
 *
 *  Every key names its own dependencies, so nothing here has to be cleared as the reader
 *  works — only when the rows themselves change. Sliced answers do not name the year,
 *  which is what makes playing the years cheap. The cap is there because each breakdown
 *  the reader tries leaves a slice behind and a district slice is eighteen thousand
 *  objects; the row buckets and the small lookups are worth keeping, the slices are not. */
function remember(key, build) {
    if (!working.memo.has(key)) {
        if (working.memo.size > 24) {
            for (const old of [...working.memo.keys()]) {
                if (old.startsWith("slice|") || old.startsWith("byArea|")) {
                    working.memo.delete(old);
                }
            }
        }
        working.memo.set(key, build());
    }
    return working.memo.get(key);
}

/** The part of the state a sliced answer depends on, as a string. */
function choices() {
    return (
        state.indicator.id + "|" + state.share + "|" +
        (state.indicator.dims || []).map((d) => d + "=" + state.dims[d]).join(";")
    );
}

// endregion

function valuesOf(dim, level = effectiveLevel()) {
    return remember("values|" + dim + "|" + level, () => {
        const here = rowsAt(level);
        return [...new Set((here.length ? here : state.rows).map((r) => r[dim]))]
            .filter((v) => v !== undefined && v !== "")
            .sort((a, b) => String(a).localeCompare(String(b), "tr", {numeric: true}));
    });
}

/** Keep every breakdown choice on a value this level offers, preserving what it can.
 *  Moving province → district with age 75+ selected would otherwise draw an empty map
 *  that looks like missing data rather than a band that stops there. */
function clampDims() {
    for (const dim of state.indicator.dims || []) {
        const values = valuesOf(dim);
        if (state.dims[dim] === TOTAL || values.includes(state.dims[dim])) {
            continue;
        }
        state.dims[dim] = state.indicator.additive ? TOTAL : values[0];
    }
}

/** Years available *at the current level*.
 *
 *  The levels do not cover the same span: district totals run to 2025, the province
 *  age-and-sex file stops at 2023. A slider offering 2025 at province level lands the
 *  reader on an empty map that looks like a bug rather than a gap in the data. */
function years() {
    return remember("years|" + state.level, () => {
        const here = rowsAt(state.level);
        const span = [...new Set((here.length ? here : state.rows).map((r) => r.year))];
        return span.sort((a, b) => a - b);
    });
}

/** Rows matching the current breakdown choice, summed where a dim is set to "all".
 *  Summing is only offered for additive units, so this never adds up rates. */
function slice(level = state.level) {
    return remember("slice|" + level + "|" + choices(), () => {
        const dims = state.indicator.dims || [];
        const totals = new Map();

        for (const row of rowsAt(level)) {
            if (!dims.every((d) => state.dims[d] === TOTAL ||
                                   String(row[d]) === String(state.dims[d]))) {
                continue;
            }
            // Keyed by id, not name. Two districts are called Pınarbaşı and forty-odd
            // are called Merkez; keying by name made one of each pair swallow the other,
            // and the loser drew as "veri yok" on the map.
            const key = row.area_id + "|" + row.year;
            const seen = totals.get(key);
            if (seen) {
                seen.value += row.value;
            } else {
                totals.set(key, {...row});
            }
        }

        if (!state.share) {
            return [...totals.values()];
        }
        const whole = wholeOf(level);
        return [...totals.values()].map((row) => {
            const base = whole.get(row.area_id + "|" + row.year);
            return {...row, value: base ? (row.value / base) * 100 : NaN};
        });
    });
}

/** The current slice indexed by area, so a chart of five series does not walk the whole
 *  slice five times. */
function byArea(level = state.level) {
    return remember("byArea|" + level + "|" + choices(), () => {
        const index = new Map();
        for (const row of slice(level)) {
            for (const key of [row.area_id, row.area]) {
                const bucket = index.get(key);
                if (bucket) {
                    bucket.push(row);
                } else {
                    index.set(key, [row]);
                }
            }
        }
        for (const points of index.values()) {
            points.sort((a, b) => a.year - b.year);
        }
        return index;
    });
}

/** Each area-year's grand total at this level, ignoring the breakdown choice entirely.
 *
 *  This is the denominator of the share mode, and it has to be built from the unfiltered
 *  rows: dividing the selected slice by itself would give 100% everywhere. It is also
 *  why sharing is only offered on additive units — a share of a sum of rates is not a
 *  number that means anything. */
function wholeOf(level) {
    return remember("whole|" + level + "|" + state.indicator.id, () => buildWhole(level));
}

function buildWhole(level) {
    const whole = new Map();
    const counted = new Map();
    for (const row of rowsAt(level)) {
        const key = row.area_id + "|" + row.year;
        whole.set(key, (whole.get(key) || 0) + row.value);
        counted.set(key, (counted.get(key) || 0) + 1);
    }

    // An incomplete breakdown is not a denominator. TÜİK withholds the under-18 count in
    // 282 of Bursa's neighbourhoods — small populations — and those areas arrive with
    // only their 18+ row. Summing what happened to be published would report them as
    // "100% adult", which is a statement about our data pretending to be one about the
    // place. They lose their share and print as "—", which is what we actually know.
    const expected = (state.indicator.dims || [])
        .map((dim) => valuesOf(dim, level).length || 1)
        .reduce((a, b) => a * b, 1);
    for (const [key, rows] of counted) {
        if (rows < expected) {
            whole.delete(key);
        }
    }
    return whole;
}

// region Derivations
//
// A derived series is computed here and never stored: the fact table keeps measurements,
// and recomputing costs nothing while storing would lose which vintage the number came
// from (K12). What each one produces — its unit, its precision — is declared in the
// dictionary, so this function knows how to divide, not what to call the result.

const DERIVATIONS = {
    /** Each series against its own first year. Shows movement, not size. */
    index(points) {
        const base = points.find((p) => Number.isFinite(p.value))?.value;
        if (!base) {
            return [];
        }
        return points.map((p) => ({...p, value: (p.value / base) * 100}));
    },

    /** Change on the previous year. The first year has no predecessor and is dropped —
     *  an absent value, not a zero. */
    yoy(points) {
        return points
            .map((p, i) => {
                const previous = points[i - 1];
                if (!previous || !previous.value) {
                    return null;
                }
                return {...p, value: ((p.value - previous.value) / previous.value) * 100};
            })
            .filter(Boolean);
    },
};

/** The dictionary entry for the active derivation, or null when showing measurements. */
function derivation() {
    return state.derivation ? meta.derivations?.[state.derivation] : null;
}

function derive(points) {
    const active = state.derivation;
    if (!active || !DERIVATIONS[active]) {
        return points;
    }
    return DERIVATIONS[active](points.slice().sort((a, b) => a.year - b.year));
}

// endregion

function seriesFor(area) {
    return derive(byArea().get(area) || []);
}

// region Narrowing the list
//
// 973 districts, or fifty thousand neighbourhoods once the other provinces arrive, is not
// a list anyone finds anything in. Each level below province gets a box per level above
// it, and the boxes chain: pick Bursa and the district box offers Bursa's districts.
//
// Both keys come out of what the rows already carry — the province is the first two
// segments of any id below it (`TR-16-001-183537` is in `TR-16`), and a neighbourhood's
// district is the prefix the exporter put in its name (`Büyükorhan / Akçasaz Mah.`). No
// extra lookup table is shipped to the page for this.

const FILTERS = {
    district: ["province"],
    neighbourhood: ["province", "district"],
};

function filterLabel(key) {
    return LEVEL_LABELS[key] || key;
}

function filterValue(row, key) {
    if (key === "province") {
        return provinceNames().get(row.area_id.split("-").slice(0, 2).join("-")) || "";
    }
    return row.area.includes(" / ") ? row.area.split(" / ")[0] : "";
}

function filtersFor(level = state.level) {
    return FILTERS[level] || [];
}

function provinceNames() {
    return remember("provinceNames", () => {
        const names = new Map();
        for (const row of rowsAt("province")) {
            names.set(row.area_id, row.area);
        }
        return names;
    });
}

/** Every area at this level, once, with the values of each filter key — ordered by those
 *  first. An alphabetical run of 973 districts puts Adana's next to Ağrı's; grouped, the
 *  list reads the way the country is arranged. */
function areasAtLevel() {
    return remember("areas|" + state.level, () => {
        const keys = filtersFor();
        const seen = new Map();
        for (const row of rowsAt(state.level)) {
            // Keyed by id. Keying by name lost twenty-one districts outright — forty-odd
            // are called Merkez and two are called Pınarbaşı, and each set collapsed to
            // one row that the reader could not tell apart or select separately.
            if (!seen.has(row.area_id)) {
                seen.set(row.area_id, {
                    id: row.area_id,
                    name: row.area,
                    in: Object.fromEntries(keys.map((k) => [k, filterValue(row, k)])),
                });
            }
        }
        return [...seen.values()].sort((a, b) => {
            for (const key of keys) {
                const order = a.in[key].localeCompare(b.in[key], "tr");
                if (order) {
                    return order;
                }
            }
            return a.name.localeCompare(b.name, "tr");
        });
    });
}

/** The Turkish name of an area id, for anything the reader reads. */
function nameOf(id) {
    return remember("names|" + state.level, () =>
        new Map(areasAtLevel().map((a) => [a.id, a.name]))
    ).get(id) || id;
}

/** What one filter box may offer, given the boxes above it. Picking Bursa leaves the
 *  district box holding Bursa's districts rather than all 973. */
function optionsFor(key) {
    const above = filtersFor().slice(0, filtersFor().indexOf(key));
    return [
        ...new Set(
            areasAtLevel()
                .filter((a) => above.every((k) => !state.filters[k] || a.in[k] === state.filters[k]))
                .map((a) => a.in[key])

        ),
    ]
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b, "tr"));
}

/** The ids the rail is currently offering: what the filter boxes and the search leave. */
function areasShown() {
    const needle = state.search.toLocaleLowerCase("tr");
    return areasAtLevel()
        .filter((a) => filtersFor().every((k) => !state.filters[k] || a.in[k] === state.filters[k]))
        .filter((a) => a.name.toLocaleLowerCase("tr").includes(needle))
        .map((a) => a.id);
}

// endregion

/** Precision follows whatever is being shown: the indicator's unit, the share, or the
 *  derivation's. A derivation is computed on top of the share, so it names the result. */
function decimals() {
    if (derivation()) {
        return derivation().decimals;
    }
    return state.share ? 1 : state.indicator.decimals;
}

function unitLabel() {
    if (derivation()) {
        return derivation().unit;
    }
    return state.share ? "toplamın %'si" : state.indicator.unit;
}

/** Sharing divides by a total, so it needs a unit that adds up and a breakdown to be a
 *  share *of*. Without both, the control would only ever draw 100%. */
function canShare() {
    return Boolean(state.indicator.additive && (state.indicator.dims || []).length);
}

function fmt(value) {
    if (value === undefined || Number.isNaN(value)) {
        return "—";
    }
    return value.toLocaleString("tr-TR", {
        minimumFractionDigits: decimals(),
        maximumFractionDigits: decimals(),
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
        .map((id, i) => {
            const muted = state.muted.includes(id);
            return "<li class='" + (muted ? "muted" : "") + "' data-area='" + id + "'>" +
                   "<span class='dot' style='background:" + colour(i) + "'></span>" +
                   "<span class='name'>" + nameOf(id) + "</span>" +
                   "<button class='chip' data-act='mute' title='" +
                   (muted ? "Grafiğe geri koy" : "Grafikten gizle") + "'>" +
                   (muted ? "◎" : "◉") + "</button>" +
                   "<button class='chip' data-act='drop' title='Seçimden çıkar'>✕</button></li>";
        })
        .join("");
    $("chosen-head").hidden = !state.selection.length;

    drawFilterBoxes();

    // The right-hand tag is the level everywhere else, which says the same thing 973
    // times over. Where the area sits inside something, that is the useful tag — the
    // innermost one, since the name already carries the rest.
    const keys = filtersFor();
    const tags = new Map(areasAtLevel().map((a) => [a.id, a.in[keys[0]] || ""]));

    // Rewriting the list resets its scroll to the top, which reads as the page jumping
    // out from under you the moment you press "Tümünü seç". The list is the same list —
    // only the ticks changed — so it should stay where the reader left it.
    const list = $("entities");
    const wasAt = list.scrollTop;

    list.innerHTML = areasShown()
        .map((id) => {
            const on = state.selection.includes(id);
            return '<li class="' + (on ? "on" : "") + '" data-area="' + id + '">' +
                   '<input type="checkbox" tabindex="-1"' + (on ? " checked" : "") + ">" +
                   '<span class="name">' + nameOf(id) + "</span>" +
                   '<span class="lvl">' +
                   (keys.length ? tags.get(id) : LEVEL_LABELS[state.level] || state.level) +
                   "</span></li>";
        })
        .join("");

    list.scrollTop = wasAt;
}

function drawFilterBoxes() {
    const keys = filtersFor();
    $("group-row").hidden = !keys.length;
    if (!keys.length) {
        state.filters = {};
        return;
    }

    $("group-row").innerHTML = keys
        .map((key) => {
            const options = optionsFor(key);
            const chosen = state.filters[key] || "";
            return "<label for='f-" + key + "'>" + filterLabel(key) + "</label>" +
                   "<select id='f-" + key + "' data-filter='" + key + "'>" +
                   "<option value=''>Hepsi</option>" +
                   options
                       .map((o) => "<option" + (chosen === o ? " selected" : "") + ">" + o + "</option>")
                       .join("") +
                   "</select>";
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
        .map((r) => r.area_id);
}

// endregion

// region Breakdown strip

/** The derivation picker. Entries that need a span are hidden on single-year views —
 *  a year-on-year change has nothing to say about one year. */
function derivationControl() {
    const span = state.view !== "map" && state.view !== "bar" && state.view !== "pyramid";
    const options = Object.entries(meta.derivations || {})
        .filter(([, body]) => span || !body.needs_span)
        .map(([id, body]) => '<option value="' + id + '"' +
                             (state.derivation === id ? " selected" : "") + ">" + body.label + "</option>")
        .join("");

    if (!options) {
        return "";
    }
    return "<div><div class='dim-label'>Türetme</div><select id='derivation'>" +
           '<option value=""' + (state.derivation ? "" : " selected") + ">Ölçüm (ham)</option>" +
           options + "</select></div>";
}

/** Absolute or relative. Its own control rather than an entry in the derivation list:
 *  a share is a different *reading* of the same year, while the derivations there are
 *  all about movement over time, and the two combine — you can index a share. */
function shareControl() {
    if (!canShare()) {
        return "";
    }
    return "<div><div class='dim-label'>Değer</div><select id='share'>" +
           "<option value=''" + (state.share ? "" : " selected") + ">Mutlak sayı</option>" +
           "<option value='share'" + (state.share ? " selected" : "") +
           ">Toplamın %'si</option></select></div>";
}

function drawDims() {
    const groups = [indicatorControl(), shareControl(), derivationControl()];

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
        .map((id) => ({id, area: nameOf(id), pts: seriesFor(id), colour: colourOf(id)}))
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

/** Wheel to zoom about the cursor, drag to pan. Redrawn by writing the viewBox back. */
function bindMapNavigation() {
    const svg = document.getElementById("map-svg");
    if (!svg) {
        return;
    }
    const view = state.mapView;

    const apply = () => svg.setAttribute("viewBox", view.x + " " + view.y + " " + view.w + " " + view.h);

    svg.onwheel = (event) => {
        event.preventDefault();
        const box = svg.getBoundingClientRect();
        // Where the cursor is, in viewBox units — the point that must stay put.
        const px = view.x + ((event.clientX - box.left) / box.width) * view.w;
        const py = view.y + ((event.clientY - box.top) / box.height) * view.h;

        const factor = event.deltaY < 0 ? 0.85 : 1 / 0.85;
        const w = Math.min(PLOT_W * 1.5, Math.max(PLOT_W / 40, view.w * factor));
        const h = w * (PLOT_H / PLOT_W);

        view.x = px - ((px - view.x) * w) / view.w;
        view.y = py - ((py - view.y) * h) / view.h;
        view.w = w;
        view.h = h;
        apply();
    };

    let dragging = null;
    svg.onpointerdown = (event) => {
        dragging = {x: event.clientX, y: event.clientY, vx: view.x, vy: view.y};
        svg.setPointerCapture(event.pointerId);
        svg.style.cursor = "grabbing";
    };
    svg.onpointermove = (event) => {
        if (!dragging) {
            return;
        }
        const box = svg.getBoundingClientRect();
        view.x = dragging.vx - ((event.clientX - dragging.x) / box.width) * view.w;
        view.y = dragging.vy - ((event.clientY - dragging.y) / box.height) * view.h;
        // A drag that ends on a province must not also open it.
        if (Math.abs(event.clientX - dragging.x) + Math.abs(event.clientY - dragging.y) > 4) {
            svg.dataset.dragged = "1";
        }
        apply();
    };
    svg.onpointerup = () => {
        dragging = null;
        svg.style.cursor = "";
    };
}

function resetMapView() {
    state.mapView = {x: 0, y: 0, w: PLOT_W, h: PLOT_H};
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
            place(event, "<div class='tip-head'>" + year + " · " + unitLabel() + "</div>" + body,
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
              tipRow(shape.dataset.colour || token("--accent"), unitLabel(), shape.dataset.value),
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
        .map((id) => {
            const point = seriesFor(id).find((p) => p.year === state.year);
            return point ? {area: nameOf(id), value: point.value, colour: colourOf(id)} : null;
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
    if (!drawn().length) {
        return empty("Soldan en az bir alan seçin.");
    }

    // Every year, not a sample. Fitting nineteen columns into the panel width used to
    // mean showing 2007, 2010, 2013 … and the reader had no way to ask for 2011 — a
    // table that silently drops the year you came for is worse than one you scroll. The
    // area column is pinned so the row stays identifiable however far right you go.
    const shown = years();

    let html = "<div class='grid-wrap' style='max-height:" + PLOT_H +
               "px'><table class='grid'><thead><tr><th class='sticky-col'>" +
               (LEVEL_LABELS[state.level] || state.level) + "</th>" +
               shown.map((y) => "<th>" + y + "</th>").join("") + "</tr></thead><tbody>";

    for (const id of drawn()) {
        const points = seriesFor(id);
        html += "<tr><td class='sticky-col'>" + nameOf(id) + "</td>" +
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
    // Four is what fits side by side and stays readable. Refusing to draw at all past
    // that was wrong: the page seeds five areas, so the pyramid opened blocked every
    // single time and the reader had to go and hide one before seeing anything. Draw the
    // first four and say plainly that the rest are not in the picture.
    const chosen = drawn();
    if (!chosen.length) {
        return empty("Soldan en az bir alan seçin.");
    }
    const areas = chosen.slice(0, 4);
    const dropped = chosen.length - areas.length;

    // In share mode every band is a percentage of that area's own population, which is
    // what makes two pyramids of very different sizes comparable without a scale switch.
    const whole = state.share ? wholeOf(state.level) : null;

    // Every breakdown control applies here too — pick Kadın and you get the female side
    // alone, on a scale that fits it. Age is the exception: it is this chart's own
    // vertical axis, so narrowing it would leave a pyramid of one band. The head says so
    // rather than letting the control look broken.
    const others = (state.indicator.dims || []).filter((d) => d !== "age");
    const ignoringAge = state.dims.age && state.dims.age !== TOTAL;

    const rowsOf = (area) => {
        const rows = rowsAt(state.level).filter(
            (r) => r.year === state.year && r.area_id === area &&
                   others.every((d) => state.dims[d] === TOTAL ||
                                       String(r[d]) === String(state.dims[d]))
        );
        if (!whole) {
            return rows;
        }
        return rows.map((r) => {
            const base = whole.get(r.area_id + "|" + r.year);
            return {...r, value: base ? (r.value / base) * 100 : NaN};
        });
    };

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
               '" font-size="13">' + nameOf(area) +
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
                       '" rx="1" data-colour="' + colour(si) + '" data-name="' + nameOf(area) + " · " +
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
        (dropped
            ? "<span>· ilk 4 çiziliyor, " + dropped + " alan daha seçili</span>"
            : "") +
        (ignoringAge
            ? "<span>· yaş grubu piramidin kendi ekseni, seçim burada geçmiyor</span>"
            : "") +
        "<span class='spacer'></span><span>Eksen</span>" +
        "<button class='chip" + (state.panelScale !== "own" ? " on" : "") +
        "' data-panel='shared' title='Bütün panellerde aynı eksen: büyüklükler karşılaştırılabilir'>Ortak eksen</button>" +
        "<button class='chip" + (state.panelScale === "own" ? " on" : "") +
        "' data-panel='own' title='Her panel kendi en büyüğüne göre: şekiller karşılaştırılabilir'>Panel bazlı</button>" +
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
    const wide = !state.focus && state.districtView && districtFeatures.length;
    const features = opened
        ? opened.features
        : wide
          ? districtFeatures
          : geometry.features.filter((f) => f.properties.area_level === state.level);
    if (!features.length) {
        return empty((LEVEL_LABELS[state.level] || state.level) + " düzeyinde sınır geometrisi yok.");
    }

    // Drawing districts means reading district rows: the scale then belongs to the
    // largest district on screen, not to İstanbul.
    const level = effectiveLevel();
    const here = slice(level);
    const rows = here.filter((r) => r.year === state.year);
    const byId = new Map(rows.map((r) => [r.area_id, r.value]));
    const drawnIds = new Set(features.map((f) => f.properties.area_id));

    const thisYear = features.map((f) => byId.get(f.properties.area_id)).filter((v) => v !== undefined);

    // Two ways to set the ends of the ramp, and they answer different questions.
    // Per-year rescaling shows who is biggest *this* year — which barely moves, so the
    // map looks frozen as the years play. A scale fixed over the whole span keeps the
    // ends still and lets the colours actually travel: that is growth.
    const span = state.scaleSpan === "fixed"
        ? here.filter((r) => drawnIds.has(r.area_id)).map((r) => r.value)
        : thisYear;

    const values = thisYear;
    const [low, high] = span.length ? [Math.min(...span), Math.max(...span)] : [0, 0];

    // A share of everything is 100% everywhere, and a ramp whose two ends are both 100
    // paints the whole country one flat colour. That is arithmetic, not a finding, so it
    // says so instead of drawing it.
    if (state.share && !(state.indicator.dims || []).some((d) => state.dims[d] !== TOTAL)) {
        return empty(
            "Toplamın %'si için bir kırılım seçmek gerekiyor.",
            "Her kırılım 'Tümü' iken her alan kendi toplamının %100'ü — " +
            "üstteki " + (state.indicator.dims || []).map(dimLabel).join(" ya da ") +
            " kutusundan bir değer seçin"
        );
    }

    // District rows carry no age or sex. Asking for one and getting a blank country is
    // confusing; say which control is doing it.
    const narrowed = (state.indicator.dims || []).filter((d) => state.dims[d] !== TOTAL);
    if (level === "district" && !values.length && narrowed.length) {
        return empty(
            "İlçe düzeyinde " + narrowed.map(dimLabel).join(" / ") + " kırılımı yok.",
            "Kırılımı 'Tümü (topla)' yapın ya da il düzeyine dönün"
        );
    }

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

    // "No value" is not the bottom of the scale — the darkest class is a real, small
    // number, and an absent one drawn the same way is a lie. It gets its own flat grey
    // and its own legend entry.
    const base = token("--bg-control");
    const edges = binEdges(span);
    const colours = rampColours(edges.length + 1);
    const colourFor = (v) => (v === undefined ? base : colours[binOf(v, edges)]);

    // Pan and zoom are a viewBox, not a transform: the strokes then keep their width and
    // the shapes stay crisp however far in the reader goes.
    const view = state.mapView;
    let svg = '<svg id="map-svg" class="plot ' + (state.focus ? "" : "drillable") +
              '" viewBox="' + view.x + " " + view.y + " " + view.w + " " + view.h + '" role="img">';
    for (const feature of features) {
        const value = byId.get(feature.properties.area_id);
        const fill = colourFor(value);
        const d = rings(feature)
            .map((ring) => "M" + ring.map((p) => px(p).map((n) => n.toFixed(1)).join(" ")).join("L") + "Z")
            .join(" ");
        svg += '<path class="area" data-area="' + feature.properties.area_id + '" d="' + d +
               '" fill="' + fill + '" stroke="' +
               token("--bg-card") + '" stroke-width="0.6" data-name="' +
               feature.properties.name_tr + '" data-value="' +
               (value === undefined ? "veri yok" : fmt(value)) + '" data-colour="' + fill + '"/>';
    }
    svg += "</svg>";
    hover = {kind: "shape"};

    // Two separate questions, so two labelled pairs rather than four bare chips: how the
    // colour is spread across the range, and what range the ends of the ramp stand for.
    const ramp =
        "<span>Renk</span>" +
        "<button class='chip" + (state.scale !== "equal" ? " on" : "") +
        "' data-scale='quantile' title='Her renk kabaca eşit sayıda alan: İstanbul kadar aykırı bir değer varken tek okunur bölme budur'>Eşit sayı</button>" +
        "<button class='chip" + (state.scale === "equal" ? " on" : "") +
        "' data-scale='equal' title='Aralık eşit genişlikte bölünür: sayının kendisi okunur, ama aykırı değer varken çoğu alan tek renge yığılır'>Eşit aralık</button>";

    const scaleToggle = values.length
        ? "<span class='spacer'></span>" + ramp + "<span>Uçlar</span>" +
          "<button class='chip" + (state.scaleSpan === "fixed" ? " on" : "") +
          "' data-span='fixed' title='Ramp uçları bütün yıllara göre sabit: yıllar oynatılınca renk gerçekten değişir'>Tüm yıllar</button>" +
          "<button class='chip" + (state.scaleSpan !== "fixed" ? " on" : "") +
          "' data-span='year' title='Ramp uçları her yıl yeniden hesaplanır: o yılın sıralaması'>Bu yıl</button>" +
          "<button class='chip' id='map-fit' title='Tekerlek yakınlaştırır, sürükleme kaydırır'>⤢ Sığdır</button>"
        : "";

    const head = "<div class='map-head'>" +
        (state.focus
            ? "<button class='link-inline' id='map-back'>← Türkiye</button><span>" +
              opened.name_tr + " · " + features.length + " ilçe" +
              (values.length ? "" : " · ilçe düzeyinde veri yok, sınırlar gösteriliyor") + "</span>"
            : "<button class='chip" + (state.districtView ? " on" : "") + "' id='district-view'>" +
              (state.districtView ? "İlleri göster" : "Tüm ilçeleri göster") +
              "</button><span>" +
              (wide ? features.length + " ilçe · ölçek en büyük ilçeye göre" : "Bir ile tıklayınca ilçeleri açılır.") +
              "</span>") +
        scaleToggle + "</div>";

    return head + wrapPlot(svg) +
           (values.length
               ? legend(low, high, edges, colours, values.length < features.length)
               : "");
}

// region Colour axis
//
// The map used to paint one hue at varying transparency across a continuous range. Two
// things were wrong with that and both showed up as "everything is dark". A continuous
// ramp asks the eye to judge how much brown a brown is, which it cannot do; and a
// *linear* range spends nearly all of its length on the gap between İstanbul and
// everyone else, so eighty provinces shared the bottom of the scale.
//
// So: discrete classes, and by default classes holding about the same number of areas.
// Then every class is visible on the map by construction, and the reader compares
// against a legend that names its own edges instead of guessing at a gradient.

const BINS = 6;

/** Bin edges. `quantile` puts about as many areas in each class — the right default for
 *  anything as skewed as population. `equal` cuts the range into equal widths, which is
 *  the literal reading and what a bounded quantity like a percentage usually wants. */
function binEdges(values) {
    const sorted = [...values].sort((a, b) => a - b);
    if (sorted.length < 2) {
        return [];
    }
    const edges = [];
    for (let i = 1; i < BINS; i++) {
        edges.push(
            state.scale === "equal"
                ? sorted[0] + ((sorted[sorted.length - 1] - sorted[0]) * i) / BINS
                : sorted[Math.floor((i / BINS) * sorted.length)]
        );
    }
    // Ties collapse: with forty areas sharing a value, two edges land on it and the class
    // between them would be empty and unreachable.
    return [...new Set(edges)].filter((e) => e > sorted[0]);
}

function binOf(value, edges) {
    let index = 0;
    while (index < edges.length && value >= edges[index]) {
        index += 1;
    }
    return index;
}

function hexToHsl(hex) {
    const int = parseInt(hex.replace("#", ""), 16);
    const [r, g, b] = [(int >> 16) & 255, (int >> 8) & 255, int & 255].map((c) => c / 255);
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const l = (max + min) / 2;
    const d = max - min;
    if (!d) {
        return {h: 0, s: 0, l: l * 100};
    }
    const s = d / (1 - Math.abs(2 * l - 1));
    const h = max === r
        ? ((g - b) / d + (g < b ? 6 : 0))
        : max === g
          ? (b - r) / d + 2
          : (r - g) / d + 4;
    return {h: h * 60, s: s * 100, l: l * 100};
}

/** `count` colours of the reader's accent hue, darkest to brightest on a dark page and
 *  palest to deepest on a light one. Built from the accent rather than a fixed palette so
 *  the map still belongs to the theme the reader picked (K5). */
function rampColours(count) {
    const {h, s} = hexToHsl(token("--accent") || "#7fa8d8");
    const dark = look.theme !== "light";
    const [l0, l1] = dark ? [24, 76] : [93, 28];
    const [s0, s1] = dark ? [Math.min(s, 40), Math.min(95, s + 12)] : [Math.min(s, 35), s];

    return Array.from({length: Math.max(1, count)}, (_, i) => {
        const t = count < 2 ? 1 : i / (count - 1);
        return "hsl(" + h.toFixed(0) + " " + (s0 + (s1 - s0) * t).toFixed(0) + "% " +
               (l0 + (l1 - l0) * t).toFixed(0) + "%)";
    });
}

// endregion

function rings(feature) {
    const g = feature.geometry;
    return g.type === "Polygon" ? g.coordinates : g.coordinates.flat();
}

/** The colour classes with the numbers that separate them.
 *
 *  A gradient bar with only its two ends labelled asks the reader to interpolate a colour
 *  by eye. Discrete classes can say exactly where each one starts, so they do. */
function legend(low, high, edges, colours, gaps) {
    const bounds = [low, ...edges, high];
    const swatches = colours
        .map((colour, i) =>
            "<span class='key'>" +
            "<span class='chip-colour' style='background:" + colour + "'></span>" +
            "<span class='key-range'>" + fmt(bounds[i]) +
            (i === colours.length - 1 ? "+" : "–" + fmt(bounds[i + 1])) +
            "</span></span>")
        .join("");

    const missing = gaps
        ? "<span class='key'><span class='chip-colour' style='background:" +
          token("--bg-control") + "'></span><span class='key-range'>veri yok</span></span>"
        : "";

    return "<div class='map-legend'>" + swatches + missing + "</div>";
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

    // A derivation that needs a span cannot be shown standing on a single year, so
    // switching to the map drops it rather than drawing something meaningless.
    const spanView = state.view === "line" || state.view === "table";
    if (derivation()?.needs_span && !spanView) {
        state.derivation = "";
    }

    // The level on screen can change without the rail moving — opening a province on the
    // map switches to district bands — so the breakdown choice is checked every draw.
    clampDims();

    drawRail();
    drawDims();
    drawTabs();

    $("chart-title").textContent = state.indicator.label;
    $("chart-definition").textContent = state.indicator.definition || "";

    hover = null;
    $("view").innerHTML = RENDERERS[state.view]();
    bindHover();
    bindMapNavigation();

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
        unitLabel() + " · " + (LEVEL_LABELS[state.level] || state.level) +
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
        s: state.share ? "1" : "",
        a: state.selection.join("~"),
        ...Object.fromEntries(Object.entries(state.dims).map(([k, v]) => ["d." + k, v])),
    });
    history.replaceState(null, "", "#" + params);
}

function readHash() {
    return new URLSearchParams(location.hash.slice(1));
}

function downloadShown() {
    const shown = new Set(drawn());
    const rows = slice().filter((r) => shown.has(r.area_id));
    // The id goes out with the name: two districts called Pınarbaşı are two rows, and a
    // file that names them both "Pınarbaşı" cannot be joined back to anything.
    const header = "area_id,area,year,value,unit,indicator\n";
    const body = rows
        .map((r) => [r.area_id, r.area, r.year, r.value, unitLabel(), state.indicator.id].join(","))
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
    state.filters = {};
    invalidate();

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

    // A map mode belongs to the indicator it was turned on for, not to the session.
    state.focus = null;
    state.districtView = false;
    resetMapView();

    const levels = levelsInData();
    state.level = levels.includes(state.level) ? state.level : levels[0];
    await ensureLevel(state.level);

    // Sharing carries over between indicators where it still means something, and is
    // dropped where it does not — a share of a fertility rate is not a number.
    state.share = state.share && canShare();

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
        if (state.selection.includes(area)) {
            state.selection = state.selection.filter((a) => a !== area);
            state.muted = state.muted.filter((a) => a !== area);
        } else {
            // Re-selecting an area that was muted brings it back visible: the mute was a
            // property of the old selection, not a preference to remember.
            state.selection = [...state.selection, area];
            state.muted = state.muted.filter((a) => a !== area);
        }
        render();
    };

    $("entity-search").oninput = (ev) => {
        state.search = ev.target.value;
        drawRail();
    };

    $("group-row").onchange = (ev) => {
        const key = ev.target.dataset.filter;
        if (!key) {
            return;
        }
        state.filters = {...state.filters, [key]: ev.target.value};
        // A box below this one may now be offering something outside the new choice.
        for (const below of filtersFor().slice(filtersFor().indexOf(key) + 1)) {
            state.filters[below] = "";
        }
        drawRail();
    };

    // "Select all" follows whatever narrows the list — the search box and the group box.
    // With Bursa picked it selects Bursa's districts, not all 973.
    $("select-all").onclick = () => {
        state.selection = [...new Set([...state.selection, ...areasShown()])];
        render();
    };

    $("select-none").onclick = () => {
        const visible = new Set(areasShown());
        state.selection = state.selection.filter((a) => !visible.has(a));
        render();
    };

    $("clear-selection").onclick = () => {
        state.selection = [];
        state.muted = [];
        render();
    };

    $("level").onchange = async (ev) => {
        state.level = ev.target.value;
        state.focus = null;
        // The old filters belonged to the old level: "Bursa" means nothing in a list of
        // provinces, and would filter everything away.
        state.filters = {};
        await ensureLevel(state.level);
        // The new level may not cover the year we were standing on.
        const span = years();
        if (!span.includes(state.year)) {
            state.year = span[span.length - 1];
        }
        clampDims();
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
        if (ev.target.id === "share") {
            state.share = ev.target.value === "share";
            render();
            return;
        }
        if (ev.target.id === "derivation") {
            state.derivation = ev.target.value;
            render();
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
            resetMapView();
            render();
            return;
        }

        if (ev.target.id === "map-fit") {
            resetMapView();
            render();
            return;
        }

        const scale = ev.target.closest("[data-scale]");
        if (scale) {
            state.scale = scale.dataset.scale;
            render();
            return;
        }

        const span = ev.target.closest("[data-span]");
        if (span) {
            state.scaleSpan = span.dataset.span;
            render();
            return;
        }

        if (ev.target.id === "district-view") {
            state.districtView = !state.districtView;
            if (state.districtView) {
                ev.target.textContent = "İlçeler yükleniyor…";
                await ensureLevel("district");
                if (!districtFeatures.length) {
                    districtFeatures = await allDistricts();
                }
            }
            render();
            return;
        }

        const panel = ev.target.closest("[data-panel]");
        if (panel) {
            state.panelScale = panel.dataset.panel;
            render();
            return;
        }

        const svg = document.getElementById("map-svg");
        if (svg?.dataset.dragged) {
            delete svg.dataset.dragged;
            return;
        }

        const area = ev.target.closest(".area");
        if (!area || state.view !== "map" || state.focus) {
            return;
        }

        // In the country-wide district view a click is on a district; its province is the
        // first two segments of the id.
        const provinceId = area.dataset.area.split("-").slice(0, 2).join("-");
        resetMapView();
        await ensureLevel("district");
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
    state.share = hash.get("s") === "1" && canShare();
    if (hash.get("f") && (await districtsOf(hash.get("f")))) {
        await ensureLevel("district");
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
