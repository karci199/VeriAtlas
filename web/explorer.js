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

/** CSV to row objects.
 *
 *  Written out longhand because of the size: the district slice is 696.900 rows, and
 *  building each one with `Object.fromEntries(cols.map(...))` allocates two arrays and a
 *  closure per row. Assigning fields in a plain loop does the same job in a fraction of
 *  the time, which is most of the wait when the reader first opens district level.
 *
 *  Values are plain — no quoted fields with commas in them — because we write these files
 *  ourselves from the fact table.
 */
function parseCsv(text) {
    const lines = text.trim().split("\n");
    const cols = lines[0].replace(/\r$/, "").split(",");
    const width = cols.length;
    const rows = new Array(lines.length - 1);

    for (let i = 1; i < lines.length; i += 1) {
        const line = lines[i].replace(/\r$/, "");
        const row = {};
        let from = 0;
        for (let c = 0; c < width; c += 1) {
            const to = c === width - 1 ? line.length : line.indexOf(",", from);
            row[cols[c]] = line.slice(from, to < 0 ? line.length : to);
            from = to + 1;
        }
        row.year = +row.year;
        row.value = +row.value;
        rows[i - 1] = row;
    }
    return rows;
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
//: Levels already merged into `state.rows`. Not the same question as "has this file been
//: fetched": switching indicator rebuilds `state.rows` from the base file, so a level
//: visited before has to be merged in again even though its parse is still cached. Asking
//: the wrong one left the district list empty on every visit after the first.
const attached = new Set();

async function ensureLevel(level) {
    const file = state.indicator?.parts?.[level];
    if (!file || attached.has(level)) {
        return;
    }
    const note = $("rail-note");
    const said = note.textContent;
    note.textContent = (LEVEL_LABELS[level] || level) + " verisi indiriliyor…";
    try {
        state.rows = state.rows.concat(await part(file));
        attached.add(level);
        invalidate();
    } finally {
        note.textContent = said;
    }
}

// Area levels are ids in the fact table; these are their Turkish names. They belong in
// the area registry the way indicator labels belong in the dictionary — until the
// registry exports them, this is the one label map left in the page.
/** The levels the page offers, in the order the menu lists them.
 *
 *  Deliberately short of what the data holds. District and neighbourhood rows are loaded,
 *  exported and kept — nothing has been thrown away — but they are not offered while the
 *  province level is being settled, because a gap at those levels cannot be told apart
 *  from a gap in the page: districts have no single years, neighbourhoods have only the
 *  18 split, and outside the thirty metropolitan provinces they are missing their
 *  villages entirely. Testing a control against data that is itself incomplete tells you
 *  nothing about the control.
 *
 *  Putting `"district"` back in this list is the whole of the change needed to bring them
 *  back: the files are already exported, the lazy fetch already knows how to get them,
 *  and everything downstream reads the level off the rows rather than off a hard-coded
 *  list. Nothing else in the page names a level it is allowed to draw. */
const OFFERED_LEVELS = ["country", "region", "nuts1", "nuts2", "province"];

const LEVEL_LABELS = {
    // "Coğrafi bölge" rather than "Bölge": the two hierarchies are both regions, and the
    // filter boxes sit next to each other, so the names have to say which is which.
    neighbourhood: "Mahalle",
    // Only in the 51 provinces law 6360 left them in; in the other 30 every village
    // became a neighbourhood in 2014, so the level is genuinely empty there rather than
    // missing.
    village: "Köy",
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
    scatter: "⁘ Dağılım",
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
    //: Which coarse reading of each breakdown is on, by dim: {age: "age_broad"}.
    //: Empty means the raw values.
    grouping: {},
    //: Narrow the list by what an area sits inside, one entry per level above this one:
    //: {province: "Bursa", district: ""}. Empty means all of them.
    filters: {},
    //: Chosen but hidden from the chart. Kept apart from the selection so muting is
    //: reversible without losing the area's place — and its colour.
    muted: [],
    //: How the colour classes are cut: "quantile" (about as many areas in each) or
    //: "equal" (equal-width slices of the range). See the note above binEdges().
    scale: "quantile",
    //: Flip which end of the colour ramp is the strong one.
    reverse: false,
    //: Pyramid panels: one shared scale, or each panel scaled to itself.
    panelScale: "shared",
    //: Table order: which column, and which way round.
    sort: {column: "name", descending: false},
    //: Line-chart value axis. "zero" always includes zero, which keeps proportions
    //: honest; "data" fits the axis to the values, which is the only way to read a set of
    //: shares that all sit between 70 and 95.
    axis: "zero",
    //: How the value axis is spaced: "linear" or "log". See axisScale.
    scaleType: "linear",
    //: Map ramp ends: "year" recomputes them per year, "fixed" spans every year drawn.
    scaleSpan: "year",
    //: The map's viewBox — what the reader has panned and zoomed to.
    mapView: {x: 0, y: 0, w: 1000, h: 420},
    //: Active derivation id, or "" for the measurement itself.
    derivation: "",
    //: "" absolute, "country" share of the whole level, "own" share of the area's own
    //: total. Absolute and relative answer different questions and the map needs both:
    //: Şanlıurfa's child population is smaller than Ankara's in people and much larger
    //: as a proportion.
    share: "",
    //: Province the map is opened into, or null for the whole country.
    focus: null,
    //: The indicator on the scatter's x axis. The chosen indicator is always the y axis,
    //: so this is the only extra choice the view needs. Empty until the reader picks one.
    versus: "",
    //: A breakdown to draw as several series per area instead of picking one value of:
    //: "age" gives every chosen province its 0-14, 15-64 and 65+ lines. Empty means the
    //: value box decides, as before. See splitSeries.
    split: "",
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
        .filter((level) => OFFERED_LEVELS.includes(level))
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
    return districtMode() ? "district" : state.level;
}

/** Is the map drawing districts right now?
 *
 *  One answer, asked in one place. It used to be worked out twice — once to pick the
 *  level to read and once to pick the shapes to draw — and the two could disagree: with
 *  the mode left on from population, median age drew 973 district outlines and coloured
 *  them from province rows, so the whole country came out "veri yok". Guarded on the
 *  indicator having districts at all, so the mode cannot outlive the indicator it was
 *  turned on for. */
function districtMode() {
    // Off entirely while districts are not offered (OFFERED_LEVELS). The drill-down is a
    // second door into the same level, and leaving it open would put on screen exactly the
    // level the menu says is not there.
    if (!OFFERED_LEVELS.includes("district")) {
        return false;
    }
    if (state.view !== "map" || !(state.indicator.levels || []).includes("district")) {
        return false;
    }
    // The level box is the only control for this now. There used to be a second one on
    // the map — a "Tüm ilçeleri göster" chip — which meant two widgets could disagree
    // about what was on screen, and the reader had to learn which one won. Opening a
    // single province by clicking it is still a map gesture, because there is no box for
    // "Bursa's districts".
    return Boolean(state.focus || (state.level === "district" && districtFeatures.length));
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
    // Single years *replace* the banded rows where they exist, never join them.
    if (fineAt(level)) {
        return remember("fine|" + level, () => fineRows.filter((r) => r.level === level));
    }
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

/** Which level an area belongs to.
 *
 *  The selection is allowed to hold areas from more than one level at once — Türkiye and
 *  Bursa and one of Bursa's districts on the same line chart is a comparison people
 *  actually want, and the rail's level box only says which list is on offer, not what may
 *  be drawn. So every chart resolves each area against *its own* level rather than the
 *  one in the box. Read off the rows rather than parsed out of the id: an id's shape is
 *  the exporter's business, and a level whose file has not been fetched has no areas to
 *  ask about anyway. */
function levelOfArea(id) {
    const at = remember("levelOf", () => {
        const found = new Map();
        for (const row of state.rows) {
            if (!found.has(row.area_id)) {
                found.set(row.area_id, row.level);
            }
        }
        return found;
    });
    return at.get(id) || state.level;
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
        // How much population is in hand, but only where the answer depends on it. The
        // population arrives after the first draw, and a slice computed against nothing
        // is a column of NaN — cached under a key that does not mention the population,
        // it stayed NaN for the rest of the session even once the file had landed. The
        // marker changes when the rows arrive, so that slice is recomputed and every
        // other slice keeps the key it always had.
        (state.share === "population" ? (versusRows.get(AGAINST)?.length || 0) + "|" : "") +
        (state.indicator.dims || [])
            .map((d) => d + "=" + state.dims[d] + "/" + (state.grouping[d] || ""))
            .join(";")
    );
}

// endregion

// region Groupings
//
// A grouping reads a breakdown coarsely: "0-14 / 15-64 / 65+" instead of sixteen bands.
// Nothing is stored — the dictionary says which bands add up into which group and the
// page sums them (see the [grouping.*] note in indicators.toml). Every level keeps its
// own band set, so a grouping is only offered where the bands it needs are present:
// the district export has 19 bands, the neighbourhood one has two, and asking for
// "15-64" over 0-17/18+ would silently drop people.

//: Rows at the finest published resolution of a breakdown, once fetched. Kept apart from
//: `state.rows` rather than merged into them: they are the *same people* counted more
//: finely, so holding both and summing across `age` would count everyone twice — the
//: trap K14 sets out for levels, one axis over.
let fineRows = [];

/** Fetch the single-year rows, if this indicator has them and they are not in yet. */
async function ensureFine(dim) {
    const file = state.indicator?.fine?.[dim]?.file;
    if (!file || fineRows.length) {
        return;
    }
    const note = $("rail-note");
    const said = note.textContent;
    note.textContent = "Tek yaş verisi indiriliyor…";
    try {
        fineRows = await part(file);
        invalidate();
    } finally {
        note.textContent = said;
    }
}

/** Is the finest resolution worth offering here? Only where it actually covers the level
 *  on screen — single years exist for provinces and the country, not for districts, and
 *  a setting that silently does nothing is worse than no setting. */
function fineOffered(dim, level = effectiveLevel()) {
    const declared = state.indicator?.fine?.[dim];
    return declared && declared.levels.includes(level) ? declared : null;
}

/** Is the fine resolution both asked for and available at this level?
 *
 *  Asked for either directly — the reader picked "Tek yaş" — or by a grouping that cannot
 *  be built without it. "18+" is the second case at province level: the published bands
 *  are fives and eighteen falls inside 15-19, so the group is summed off the single years
 *  underneath instead of splitting a band by assumption. */
function fineAt(level) {
    // Read out of the dictionary rather than through `grouping()`, which resolves against
    // the rows on screen — and the rows on screen are chosen by this function. Asking it
    // here closed a loop: fineAt → grouping → groupingsFor → rawValuesOf → rowsAt →
    // fineAt, and the page died on load with the "veri okunamadı" fallback showing.
    const chosen = state.grouping.age;
    const wanted = chosen === FINE || Boolean(meta.groupings?.[chosen]?.needs_fine);
    return wanted && fineRows.length > 0 && fineRows.some((r) => r.level === level);
}

const FINE = "__fine__";

function groupingsFor(dim, level = effectiveLevel()) {
    return remember("groupings|" + dim + "|" + level, () => {
        const bands = rawValuesOf(dim, level);
        return Object.entries(meta.groupings || {})
            .filter(([, g]) => g.dim === dim)
            // Offered when every band *here* lands in a group. Asking the other way round
            // — is every listed value present — rejected the district level, where the
            // tail is 75-79…90+ rather than the province file's single 75+. What matters
            // is that nobody is dropped, not that the list matches exactly.
            .filter(([, g]) => {
                const covered = new Set(Object.values(g.covers).flat());
                // A grouping that needs the fine rows is offered wherever those exist,
                // rather than judged against the coarse bands now on screen — those are
                // exactly the bands it cannot be built from.
                if (g.needs_fine) {
                    return Boolean(fineOffered(dim, level)) || bands.every((b) => covered.has(b));
                }
                return bands.length > 1 && bands.every((b) => covered.has(b));
            });
    });
}

/** The active grouping for a dim, or null when the raw values are being shown. */
function grouping(dim) {
    const id = state.grouping[dim];
    const found = groupingsFor(dim).find(([key]) => key === id);
    return found ? found[1] : null;
}

/** Which group a raw value falls in, or the value itself when nothing is grouped. */
function groupValue(dim, value) {
    const active = grouping(dim);
    if (!active) {
        return value;
    }
    for (const [name, values] of Object.entries(active.covers)) {
        if (values.includes(value)) {
            return name;
        }
    }
    return "";
}

// endregion

function rawValuesOf(dim, level) {
    return remember("raw|" + dim + "|" + level, () => {
        const here = rowsAt(level);
        const found = [...new Set((here.length ? here : state.rows).map((r) => r[dim]))]
            .filter((v) => v !== undefined && v !== "");

        // The dictionary's order where it names the values, alphabetical where it does
        // not. Sorting always looked right for as long as every listed dimension was
        // alphabetical anyway — sexes, marital statuses, age bands. It stopped being
        // right at "İlinde / İl dışında", where the ids sort to elsewhere-then-own and
        // the reader is offered the remainder before the thing it is a remainder of.
        const declared = Object.keys(meta.dimensions?.[dim]?.values || {});
        if (declared.length) {
            const rank = new Map(declared.map((value, index) => [value, index]));
            return found.sort(
                (a, b) => (rank.get(a) ?? declared.length) - (rank.get(b) ?? declared.length)
            );
        }
        return found.sort((a, b) =>
            String(a).localeCompare(String(b), "tr", {numeric: true})
        );
    });
}

function valuesOf(dim, level = effectiveLevel()) {
    const active = grouping(dim);
    if (active) {
        // In the dictionary's order, which is the order a reader expects to see ages.
        return Object.keys(active.covers);
    }
    return rawValuesOf(dim, level);
}

/** Keep every breakdown choice on a value this level offers, preserving what it can.
 *  Moving province → district with age 75+ selected would otherwise draw an empty map
 *  that looks like missing data rather than a band that stops there. */
function clampDims() {
    for (const dim of state.indicator.dims || []) {
        const values = valuesOf(dim);
        // A comparison and a ratio are both legitimate choices for a dim even though
        // neither is one of its values; without this the box reset itself to "Tümü" on
        // the very next redraw and the choice never survived long enough to be computed.
        if (state.dims[dim] === TOTAL ||
            values.includes(state.dims[dim]) ||
            comparison(dim) ||
            ratioOn(dim)) {
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
// region Comparisons
//
// A comparison sets one breakdown value against another — "Erkek − Kadın", "E/K × 100".
// It is not a value of the dim, so it cannot be filtered for; the slice is taken twice
// and the two are combined. Declared in the dictionary next to the groupings, for the
// same reason: which two values, and how, is a decision rather than a branch.

function comparisonsFor(dim, level = effectiveLevel()) {
    const values = new Set(rawValuesOf(dim, level));
    return Object.entries(meta.comparisons || {}).filter(
        ([, c]) =>
            c.dim === dim &&
            values.has(c.plus) &&
            values.has(c.minus) &&
            // A *difference* between two values means something in any unit: men marry
            // three years later than women, and that three is a number of years. A
            // *ratio* of them only means something where the values are counts. The sex
            // ratio of a population is a hundred men per hundred women; the sex ratio of
            // an average age at marriage is 28,5 ÷ 26,0 = 110, a number with no name and
            // no use, offered next to one that has both. Median age carried the same
            // empty option long before marriage age was loaded.
            (c.how !== "ratio" || state.indicator.additive)
    );
}

/** The comparison a dim is currently set to, or null. */
function comparison(dim) {
    const found = comparisonsFor(dim).find(([key]) => key === state.dims[dim]);
    return found ? found[1] : null;
}

function activeComparison() {
    for (const dim of state.indicator.dims || []) {
        const found = comparison(dim);
        if (found) {
            return [dim, found];
        }
    }
    return null;
}

// region Ratios
//
// A comparison reads two values of a breakdown against each other; a ratio reads two
// *sets* of them. The dependency ratios need that — (0-14 + 65+) over 15-64 is three
// groups — and they are computed here rather than downloaded because they are an exact
// function of the bands already in hand (K12). TÜİK's own published versions are fetched
// separately, once, to check these against.

/** The ratio the reader picked on a dim, or null. Stored in `state.dims` like a
 *  comparison, because it answers the same question the value box asks. */
function ratioOn(dim) {
    const body = meta.ratios?.[state.dims[dim]];
    return body && body.dim === dim ? [state.dims[dim], body] : null;
}

function activeRatio() {
    for (const dim of state.indicator.dims || []) {
        const found = ratioOn(dim);
        if (found) {
            return found;
        }
    }
    return null;
}

/** Which ratios can be offered on this dim here: the ones whose grouping covers every
 *  band at this level. Reusing the grouping's own rule means a ratio can never be built
 *  on a level where it would silently drop people. */
function ratiosFor(dim, level = effectiveLevel()) {
    const usable = new Set(groupingsFor(dim, level).map(([id]) => id));
    return Object.entries(meta.ratios || {}).filter(
        ([, body]) => body.dim === dim && usable.has(body.grouping)
    );
}

/** The raw band values a ratio's side covers, at this level. */
function bandsOf(body, side, level) {
    const covers = meta.groupings?.[body.grouping]?.covers || {};
    const here = new Set(rawValuesOf(body.dim, level));
    return body[side]
        .flatMap((group) => covers[group] || [])
        .filter((band) => here.has(band));
}

function combine(how, plus, minus) {
    if (how === "ratio") {
        return minus ? (plus / minus) * 100 : NaN;
    }
    return plus - minus;
}

// endregion

function slice(level = state.level) {
    const compare = activeComparison();
    if (compare) {
        const [dim, spec] = compare;
        return remember("compare|" + level + "|" + choices(), () => {
            const at = (value) => {
                const kept = state.dims[dim];
                state.dims = {...state.dims, [dim]: value};
                const rows = sliceRaw(level);
                state.dims = {...state.dims, [dim]: kept};
                return new Map(rows.map((r) => [r.area_id + "|" + r.year, r]));
            };
            const plus = at(spec.plus);
            const minus = at(spec.minus);
            return [...plus.entries()].map(([key, row]) => ({
                ...row,
                value: combine(spec.how, row.value, minus.get(key)?.value),
            }));
        });
    }

    const ratio = activeRatio();
    if (ratio) {
        const [, body] = ratio;
        return remember("ratio|" + level + "|" + choices(), () => {
            // Both sides summed straight off the rows rather than through two slices:
            // a side is several bands, and `sliceRaw` answers for one value at a time.
            const over = new Set(bandsOf(body, "over", level));
            const under = new Set(bandsOf(body, "under", level));
            const sums = new Map();
            for (const row of rowsAt(level)) {
                const side = over.has(row[body.dim])
                    ? "over"
                    : under.has(row[body.dim])
                      ? "under"
                      : null;
                if (!side) {
                    continue;
                }
                // The other breakdowns still apply: the reader can ask for the male
                // dependency ratio, and the age dim is the only one this consumes.
                const others = (state.indicator.dims || []).filter((d) => d !== body.dim);
                if (!others.every((d) => state.dims[d] === TOTAL ||
                                         String(groupValue(d, row[d])) === String(state.dims[d]))) {
                    continue;
                }
                const key = row.area_id + "|" + row.year;
                const bucket = sums.get(key) || {row, over: 0, under: 0};
                bucket[side] += row.value;
                sums.set(key, bucket);
            }
            return [...sums.values()].map(({row, over: top, under: bottom}) => ({
                ...row,
                value: bottom ? (top / bottom) * 100 : NaN,
            }));
        });
    }

    return sliceRaw(level);
}

function sliceRaw(level = state.level) {
    return remember("slice|" + level + "|" + choices(), () => {
        const dims = state.indicator.dims || [];
        const totals = new Map();

        for (const row of rowsAt(level)) {
            // Matched through the grouping: with "Geniş yaş grupları" on, a row banded
            // 20-24 answers to 15-64, and the rows in a group add up on the way past.
            if (!dims.every((d) => state.dims[d] === TOTAL ||
                                   String(groupValue(d, row[d])) === String(state.dims[d]))) {
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

        // "Per cent of what" has two honest answers and the reader picks which:
        //   own     — composition: what share of *this place* is aged 0-4.
        //   country — distribution: what share of *the country* is here.
        // Note that "own" with no breakdown chosen really is 100% everywhere; that is
        // arithmetic, not a bug, and the reader who asked for it can see why.
        // Against another indicator entirely: the area's population.
        if (state.share === "population") {
            const people = populationTotals(level);
            return [...totals.values()].map((row) => {
                const base = people.get(row.area_id + "|" + row.year);
                return {...row, value: base ? (row.value / base) * 100 : NaN};
            });
        }

        // "own:<dim>" — the share within one breakdown, every other choice held. See
        // shareControl for why this is a separate mode rather than what "own" means.
        const within = shareWithin();
        if (within) {
            const base = withinTotals(level, within);
            return [...totals.values()].map((row) => {
                const found = base.get(row.area_id + "|" + row.year);
                return {...row, value: found ? (row.value / found) * 100 : NaN};
            });
        }

        if (state.share === "own") {
            const whole = wholeOf(level);
            return [...totals.values()].map((row) => {
                const base = whole.get(row.area_id + "|" + row.year);
                return {...row, value: base ? (row.value / base) * 100 : NaN};
            });
        }

        // A value that is true by construction is not an observation.
        //
        // At country level this mode divides Türkiye by Türkiye and gets 100, every year,
        // for every indicator. It is arithmetic, not a finding, and drawn beside the
        // provinces it flattens the colour ramp and the axis onto a number that means
        // nothing. The same rule covers the other cases of the same shape — an area's
        // share of itself, a share with no breakdown to be a share of — so they are
        // excluded here rather than each being noticed separately later.
        const areas = new Set([...totals.values()].map((row) => row.area_id));
        if (areas.size < 2) {
            return [...totals.values()].map((row) => ({...row, value: NaN}));
        }

        const nationwide = new Map();
        for (const row of totals.values()) {
            nationwide.set(row.year, (nationwide.get(row.year) || 0) + row.value);
        }
        return [...totals.values()].map((row) => {
            const base = nationwide.get(row.year);
            return {...row, value: base ? (row.value / base) * 100 : NaN};
        });
    });
}

/** The slice with the derivation applied, area by area.
 *
 *  A derivation turns a series into a series — an index needs its first year, an annual
 *  change needs the year before — so it cannot be computed from one year's rows. The line
 *  chart and the table go through `seriesFor`, which derives per area and so has always
 *  had it; the map read the raw slice directly and quietly showed the measurement while
 *  the strip said "Yıllık değişim (%)". The two now read the same numbers.
 *
 *  The derivation is in the memo key because `choices()` does not name it: sliced answers
 *  are shared with the views that do not derive. */
function derivedSlice(level = state.level) {
    if (!state.derivation) {
        return slice(level);
    }
    return remember("derived|" + level + "|" + choices() + "|" + state.derivation, () => {
        const byId = new Map();
        for (const row of slice(level)) {
            const bucket = byId.get(row.area_id);
            if (bucket) {
                bucket.push(row);
            } else {
                byId.set(row.area_id, [row]);
            }
        }
        return [...byId.values()].flatMap((points) => derive(points));
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

// region Against the population
//
// Every share mode so far divides an indicator by part of itself. "Kaç yabancı yaşıyor"
// against "ilin nüfusunun yüzde kaçı yabancı" is a different move: the denominator is
// another indicator entirely, and without it Şanlıurfa's 130 thousand foreign residents
// and Muğla's 90 thousand cannot be compared — the provinces are different sizes.
//
// Read through the same lazily-fetched second dataset the scatter uses, so a page that
// never asks for it never downloads it.

//: The indicator every count is offered against. Population is the one denominator that
//: means something for all of them; anything else belongs on the scatter, where the
//: reader names both axes.
const AGAINST = "population";

async function ensurePopulation() {
    const indicator = catalogue.find((i) => i.id === AGAINST);
    if (!indicator || versusRows.has(AGAINST)) {
        return;
    }
    const files = [indicator.dataset, indicator.parts?.[state.level]].filter(Boolean);
    const note = $("rail-note");
    const said = note.textContent;
    note.textContent = "Nüfus indiriliyor…";
    try {
        versusRows.set(AGAINST, (await Promise.all(files.map(part))).flat());
    } finally {
        note.textContent = said;
    }
}

/** Total population per area-year at a level: `Map("TR-16|2025" -> 3263011)`.
 *
 *  The row count is in the memo key, which looks redundant and is not: the population is
 *  fetched lazily, and anything computed from it before it lands would otherwise be
 *  remembered as an empty map for the rest of the session. That is what "İl nüfusunun
 *  %'si" did on kütük nüfusu — a full column of dashes, on an indicator whose data was
 *  sitting right there. It worked wherever the population happened to have been fetched
 *  first, which is the worst kind of bug: the one that comes and goes with what you
 *  clicked before. */
function populationTotals(level) {
    return remember("pop|" + level + "|" + (versusRows.get(AGAINST)?.length || 0), () => {
        const totals = new Map();
        for (const row of versusRows.get(AGAINST) || []) {
            if (row.level !== level) {
                continue;
            }
            const key = row.area_id + "|" + row.year;
            totals.set(key, (totals.get(key) || 0) + row.value);
        }
        return totals;
    });
}

/** Can this indicator be read against the population? A count can; the population itself
 *  cannot (it would be 100 everywhere) and neither can a rate.
 *
 *  "A count" used to be spelled `unit === "kişi"` — a match on the Turkish label. It held
 *  for exactly as long as everything counted was people. Births are counted in doğum,
 *  deaths in ölüm, marriages in evlenme, and every one of them lost the mode without a
 *  word: "ilin nüfusuna göre kaç evlenme" is the kaba evlenme hızı, the single most
 *  standard reading of that number, and the control for it simply was not drawn.
 *
 *  Additivity is the property that was meant all along, and it is a fact the dictionary
 *  states about the unit rather than a word in one language (K1). What adds up is a
 *  count; what does not is a rate, an age or an index, and none of those go over a
 *  population. */
function canShareAgainstPopulation() {
    return (
        state.indicator.id !== AGAINST &&
        state.indicator.additive &&
        catalogue.some((i) => i.id === AGAINST && i.available)
    );
}

// endregion

/** Is there more than one area at this level to be a share *of*?
 *
 *  At Türkiye level there is not: the mode divides the country by the country and gets
 *  100 every year, which `slice` refuses to state as a finding and returns as blank. The
 *  refusal is right and the control offering it anyway was not — the reader picked
 *  "Toplamın %'si" on doğal nüfus artışı and got a table of seventeen dashes with nothing
 *  saying why. So the offer is withdrawn where the answer would be empty. */
function shareOfWholeMeans() {
    return new Set(slice().map((row) => row.area_id)).size > 1;
}

/** The share mode this indicator can still answer, or "" — one rule, so switching
 *  indicator and following a shared link cannot disagree about what survives. */
function shareStillMeans(share) {
    if (share === "population") {
        return canShareAgainstPopulation() ? share : "";
    }
    if (share === "country") {
        return shareOfWholeMeans() ? share : "";
    }
    if (!canShare()) {
        return "";
    }
    if (share.startsWith("own:")) {
        return (state.indicator.dims || []).includes(share.slice(4)) ? share : "";
    }
    return share;
}

/** The breakdown the reader is taking a share within, or null. */
function shareWithin() {
    const dim = state.share.startsWith("own:") ? state.share.slice(4) : null;
    return dim && (state.indicator.dims || []).includes(dim) ? dim : null;
}

/** Per area-year, the total across one breakdown with every other choice held fixed.
 *
 *  The denominator of "Medeni durum içinde %": for 65+ women it sums the widowed, the
 *  married, the never-married and the divorced 65+ women, and nobody else. */
function withinTotals(level, dim) {
    return remember("within|" + level + "|" + dim + "|" + choices(), () => {
        const others = (state.indicator.dims || []).filter((d) => d !== dim);
        const base = new Map();
        for (const row of rowsAt(level)) {
            if (!others.every((d) => state.dims[d] === TOTAL ||
                                     String(groupValue(d, row[d])) === String(state.dims[d]))) {
                continue;
            }
            const key = row.area_id + "|" + row.year;
            base.set(key, (base.get(key) || 0) + row.value);
        }
        return base;
    });
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
    //
    // The rule only fires where the data shows a complete cross-product is possible.
    //
    // Multiplying the dimensions out and demanding that many rows was wrong twice over.
    // Marital status has 5 × 2 × 17 = 170 combinations on paper and TÜİK publishes 151 —
    // so every province failed and the share mode drew an empty country. But taking the
    // fullest province as the standard instead was wrong the other way: a small province
    // has no divorced ninety-year-old men and the cell is simply absent, which is a zero,
    // not a suppression, and nearly every province lost its share.
    //
    // What separates the two cases is whether the full product is ever actually seen. In
    // Bursa's neighbourhoods it is — the 18 split has two bands and most areas have both,
    // so the 282 carrying one are genuinely missing a published number. Where no area
    // reaches the product, the product is not what the source publishes, and the absent
    // cells are absent for everybody.
    const product = (state.indicator.dims || [])
        .map((dim) => valuesOf(dim, level).length || 1)
        .reduce((a, b) => a * b, 1);
    if (counted.size && Math.max(...counted.values()) === product) {
        for (const [key, rows] of counted) {
            if (rows < product) {
                whole.delete(key);
            }
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

/** Percentage change needs a base that is above zero, and every series here used to have
 *  one. Natural increase does not: a province can be at −2.535 and the country's figure
 *  is on its way to crossing over.
 *
 *  Divided by a negative base the sign flips and the sentence inverts. A province going
 *  from −1.000 to −500 has halved its deficit; ((−500 − −1.000) / −1.000) × 100 prints
 *  **−50%**, which reads as "fell by half" — the opposite of what happened, stated
 *  confidently, in a form nobody double-checks. Crossing zero is worse: the number is
 *  arbitrarily large and its sign says nothing at all.
 *
 *  So a non-positive base yields no point. Undefined is the honest answer, and the strip
 *  greys these derivations out where they would apply (see derivationControl), so the
 *  reader is told rather than left with an empty chart. */
function positiveBase(value) {
    return Number.isFinite(value) && value > 0;
}

//: The derivations that divide by the series' own values, and so need it above zero.
//: `diff`, `total_diff` and `ma3` subtract and average instead, which a negative number
//: survives, so they stay offered everywhere.
const NEEDS_POSITIVE = ["index", "yoy", "total_change", "cagr"];

/** Does the reading now on screen ever go below zero?
 *
 *  Negative, not "zero or below", and the difference decides how blunt this is. A zero
 *  base makes one point undefined and `positiveBase` drops that point — ordinary, local,
 *  and the rest of the series is untouched. A *negative* base flips the sign of the
 *  answer, so every percentage in that series says the opposite of what happened, and
 *  there is no reading of it that is safe to leave on offer.
 *
 *  Written as "zero or below" first, it turned the percentage derivations off for foreign
 *  nationals over five zero rows in 2.952 — an indicator that is fine to index, blocked
 *  because a province once had no foreign women.
 *
 *  Asked of the whole slice rather than of the drawn series: the offer in the strip has
 *  to hold for whatever the reader selects next, and a control that appears and vanishes
 *  as areas are ticked is worse than one that is honestly greyed out. */
function everNegative() {
    return remember("negative|" + state.level + "|" + choices(), () =>
        slice().some((r) => Number.isFinite(r.value) && r.value < 0)
    );
}

const DERIVATIONS = {
    /** Each series against its own first year. Shows movement, not size. */
    index(points) {
        const base = points.find((p) => Number.isFinite(p.value))?.value;
        if (!positiveBase(base)) {
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
                if (!previous || !positiveBase(previous.value)) {
                    return null;
                }
                return {...p, value: ((p.value - previous.value) / previous.value) * 100};
            })
            .filter(Boolean);
    },

    /** The same step in the measurement's own unit. A percentage on a small base is a
     *  big number about a small thing; this says how many. */
    diff(points) {
        return points
            .map((p, i) => (i ? {...p, value: p.value - points[i - 1].value} : null))
            .filter(Boolean);
    },

    /** Total movement since the series began, read directly rather than as an index:
     *  −51,4 rather than 48,6. This is the column to sort by for "where did it fall
     *  most". */
    total_change(points) {
        const base = points.find((p) => Number.isFinite(p.value))?.value;
        if (!positiveBase(base)) {
            return [];
        }
        return points.map((p) => ({...p, value: ((p.value - base) / base) * 100}));
    },

    /** Total movement since the series began, in the measurement's own unit. A median age
     *  going 34 → 36 is "+2 yaş"; calling it "+5,9%" is arithmetic nobody asked for. */
    total_diff(points) {
        const base = points.find((p) => Number.isFinite(p.value))?.value;
        if (base === undefined) {
            return [];
        }
        return points.map((p) => ({...p, value: p.value - base}));
    },

    /** Compound growth from the first year to each year, per year.
     *
     *  The one people reach for when they say "how fast is it growing". "Yıllık değişim"
     *  answers it for a single year, so a good year or a bad one changes the whole
     *  picture; this spreads the whole run into one rate. Compounding matters at these
     *  spans: 20% over 18 years is 1,0% a year, not 20/18 = 1,1%.
     *
     *  The first year is its own base, so it has no rate and is dropped rather than
     *  printed as a zero that would read as "no growth". */
    cagr(points) {
        const first = points.find((p) => Number.isFinite(p.value));
        if (!first || first.value <= 0) {
            // A compound rate off a base of zero or less has no meaning — the ratio is
            // undefined or the root is of a negative number.
            return [];
        }
        return points
            .map((p) => {
                const years = p.year - first.year;
                if (years <= 0 || !Number.isFinite(p.value) || p.value <= 0) {
                    return null;
                }
                return {...p, value: (Math.pow(p.value / first.value, 1 / years) - 1) * 100};
            })
            .filter(Boolean);
    },

    /** Three-year centred mean. Small areas jump about year to year and the jumping is
     *  mostly noise; the ends have no neighbour on one side and are dropped rather than
     *  averaged over a shorter window, which would make them a different statistic. */
    ma3(points) {
        return points
            .map((p, i) => {
                const window = [points[i - 1], p, points[i + 1]];
                if (window.some((w) => !w || !Number.isFinite(w.value))) {
                    return null;
                }
                return {...p, value: (window[0].value + p.value + window[2].value) / 3};
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
    return derive(byArea(levelOfArea(area)).get(area) || []);
}

// region Splitting a breakdown into series
//
// Every other control answers "which value of this breakdown", and the answer is one
// value across all the areas: 0-14 everywhere, or 65+ everywhere. The question that could
// not be asked was the other one — *this* province's 0-14 against its own 15-64 and 65+.
//
// The alternative was to let the value box take several values at once, so any area could
// be paired with any band. It is more flexible and it is worse: it lets you draw
// İstanbul's 0-14 beside Ankara's 65+, a chart whose shape means nothing and which the
// reader has no way to tell apart from a real comparison. Splitting a whole dimension
// keeps the picture symmetric by construction — every chosen area gets every band, and an
// asymmetric one cannot be built by accident.
//
// Colour carries the area and the dash carries the value, so the eye groups by place
// first and separates the bands inside each group.

/** Which dimensions can be split here: the ones this indicator breaks down by, that have
 *  more than one value at this level. */
function splittable() {
    return (state.indicator.dims || []).filter((dim) => valuesOf(dim).length > 1);
}

/** The values the split draws, in the dictionary's order. */
function splitValues() {
    return state.split ? valuesOf(state.split) : [];
}

/** The series for one area: one when nothing is split, one per value when something is.
 *
 *  Each is a whole series with its own points, so everything downstream — the derivation,
 *  the axis, the cursor readout — works on it exactly as it works on an unsplit area. */
function splitSeries(area) {
    const level = levelOfArea(area);
    if (!state.split) {
        return [{key: area, area, label: nameOf(area), value: null, points: seriesFor(area)}];
    }

    const dim = state.split;
    const kept = state.dims[dim];
    const out = splitValues().map((value) => {
        // The slice is keyed on the whole choice set, so swapping one dim in and out
        // reads a cached answer rather than rebuilding — the same move the comparison
        // does. Restored immediately, because everything else reads `state.dims` too.
        state.dims = {...state.dims, [dim]: value};
        const points = derive(byArea(level).get(area) || []);
        return {
            key: area + "|" + value,
            area,
            value,
            label: nameOf(area) + " · " + dimValue(dim, value),
            points,
        };
    });
    state.dims = {...state.dims, [dim]: kept};
    return out.filter((s) => s.points.length);
}

/** Every drawn series, across every drawn area. */
function allSeries() {
    return drawn().flatMap(splitSeries);
}

//: Dash patterns for the split values, in the order the values come. The first is solid,
//: so an unsplit chart and the first band of a split one look the same.
const DASHES = ["", "6 4", "2 3", "10 3 2 3", "1 4"];

function dashFor(series) {
    if (!state.split || series.value === null) {
        return "";
    }
    return DASHES[splitValues().indexOf(series.value) % DASHES.length];
}

// endregion

// region The second indicator
//
// Every other view answers a question about one indicator. The scatter asks how two of
// them move together — is a province's fertility lower where its population is older —
// and that is a different shape of question: it needs a second dataset in hand at the
// same time, joined to the first on area and year.
//
// The chosen indicator stays the y axis, with every breakdown, share and derivation
// control still applying to it. The second one is read as a **whole**: summed across its
// breakdowns where they add up, and otherwise taken at whichever value stands for
// everybody. Giving the x axis its own copy of the breakdown strip would double a
// control panel that is already the busiest thing on the page, and the question people
// actually bring here is about the two measures, not about a cross-tabulation.

//: Rows of the x-axis indicator, by its id. Kept apart from `state.rows` — they are a
//: different indicator entirely, and merging them would put two units in one bucket.
const versusRows = new Map();

function versusIndicator() {
    return state.versus ? catalogue.find((i) => i.id === state.versus) : null;
}

/** Indicators that can sit opposite this one: published at the level on screen, and not
 *  the one already being drawn.
 *
 *  Ordered so that the ones with a whole-population value come first, because the first
 *  is what the view opens on. An indicator published only by sex has no total to put on
 *  an axis, and opening the scatter onto one of those makes a working view look broken. */
function versusOffered() {
    const whole = (i) => !(i.dims || []).length || i.additive;
    return catalogue
        .filter((i) => i.available && i.id !== state.indicator.id &&
                       (i.levels || []).includes(state.level))
        .sort((a, b) => Number(whole(b)) - Number(whole(a)));
}

/** Fetch the x-axis indicator, and the part that carries the level on screen. */
async function ensureVersus() {
    const indicator = versusIndicator();
    if (!indicator) {
        return;
    }
    const files = [indicator.dataset, indicator.parts?.[state.level]].filter(Boolean);
    const missing = files.filter((file) => !datasets.has(file));
    if (!missing.length && versusRows.has(indicator.id)) {
        return;
    }

    const note = $("rail-note");
    const said = note.textContent;
    note.textContent = indicator.label + " indiriliyor…";
    try {
        const parts = await Promise.all(files.map(part));
        versusRows.set(indicator.id, parts.flat());
    } finally {
        note.textContent = said;
    }
}

/** The x-axis indicator's value per area at one year: `Map(area_id -> value)`.
 *
 *  Summed across breakdowns where the unit adds up. Where it does not — a median, a rate
 *  — summing would be nonsense, so the value that stands for the whole population is
 *  taken instead: `sex=total` where it exists, and otherwise nothing at all rather than
 *  an arbitrary one of the parts quietly standing in for everybody. */
function versusAt(level, year) {
    const indicator = versusIndicator();
    const rows = versusRows.get(state.versus) || [];
    const here = rows.filter((r) => r.level === level && r.year === year);
    const dims = indicator?.dims || [];
    const values = new Map();

    if (!dims.length || indicator?.additive) {
        for (const row of here) {
            values.set(row.area_id, (values.get(row.area_id) || 0) + row.value);
        }
        return values;
    }

    const whole = here.filter((row) => dims.every((dim) => String(row[dim]) === "total"));
    for (const row of whole) {
        values.set(row.area_id, row.value);
    }
    return values;
}

// endregion

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
    // Eighty-one provinces in one alphabetical run is a list you scroll rather than read.
    // A province belongs to two hierarchies at once — the seven geographic regions and
    // the İBBS statistical ones — and they answer different questions, so both are
    // offered rather than one being picked on the reader's behalf.
    province: ["region", "nuts1"],
    district: ["province"],
    neighbourhood: ["province", "district"],
    village: ["province", "district"],
};

function filterLabel(key) {
    return LEVEL_LABELS[key] || key;
}

/** Which parent of an area, at a given level, the list is narrowed by.
 *
 *  For the levels below a province it comes out of what the rows already carry — the
 *  province is the first two segments of the id, and a neighbourhood's district is the
 *  prefix the exporter put in its name. Above a province there is nothing in the row to
 *  read, so it comes from `belongs` in the dictionary: the province's ancestors in both
 *  hierarchies, matched by the shape of the id (`TR1`/`TR62` are İBBS, `TR-R-*` are the
 *  geographic regions). */
function filterValue(row, key) {
    if (key === "region" || key === "nuts1" || key === "nuts2") {
        const chain = meta.belongs?.[row.area_id] || [];
        const wanted = chain.find((id) =>
            key === "region"
                ? id.startsWith("TR-R-")
                : !id.startsWith("TR-R-") && id.length === (key === "nuts1" ? 3 : 4)
        );
        return wanted ? meta.area_labels?.[wanted] || wanted : "";
    }
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

/** The Turkish name of an area id, for anything the reader reads.
 *
 *  Across every level in hand, not just the one in the rail's box: a chosen area keeps its
 *  place when the reader moves the box, and a chart that draws it has to be able to name
 *  it. Level-scoped, this printed a bare `TR` next to Türkiye's line. */
function nameOf(id) {
    return remember("names", () => {
        const names = new Map();
        for (const row of state.rows) {
            names.set(row.area_id, row.area);
        }
        return names;
    }).get(id) || id;
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
    // A derivation with no unit of its own — a difference, a moving average — keeps the
    // precision of whatever it was computed from, share included.
    const from = derivation() || activeComparison()?.[1] || activeRatio()?.[1];
    if (from && from.decimals !== null && from.decimals !== undefined) {
        return from.decimals;
    }
    return state.share ? 2 : state.indicator.decimals;
}

function unitLabel() {
    const from = derivation() || activeComparison()?.[1] || activeRatio()?.[1];
    if (from && from.unit) {
        return from.unit;
    }
    if (!state.share) {
        return state.indicator.unit;
    }
    // Name the denominator, because these percentages are different numbers about
    // different things and only the label tells them apart on the page. "65+ kadınlarda
    // dul" and "nüfusta 65+ dul kadın" are both percentages and they are not close.
    const within = shareWithin();
    if (within) {
        return dimLabel(within).toLocaleLowerCase("tr") + " içinde %";
    }
    if (state.share === "own") {
        return "alanın kendi toplamının %'si";
    }
    // Named rather than left to the fallthrough: reading against the population is the
    // one share whose denominator is a different indicator, and it was printing as
    // "Türkiye toplamının %'si" — the chart said one thing, the control said another,
    // and the number was neither.
    if (state.share === "population") {
        return (LEVEL_LABELS[state.level] || "alan").toLocaleLowerCase("tr") +
               " nüfusunun %'si";
    }
    return (LEVEL_LABELS[state.level] === "Türkiye" ? "toplamın" : "Türkiye toplamının") +
           " %'si";
}

/** Sharing divides by a total, so it needs a unit that adds up and a breakdown to be a
 *  share *of*. Without both, the control would only ever draw 100%. */
function canShare() {
    return Boolean(state.indicator.additive && (state.indicator.dims || []).length);
}

//: Number formatters, kept by precision. `toLocaleString` builds a new Intl.NumberFormat
//: on every call, and a district table is twenty thousand cells: that one line was most
//: of the second it took to sort a thousand rows.
const formatters = new Map();

/** A number formatter for at most `places` decimals.
 *
 *  At most, not exactly: a trailing zero is a digit the value does not have, and printing
 *  44,50 where the answer is 44,5 claims a precision the rounding just took away. The
 *  unit's `decimals` is a ceiling on what may be shown, not a width to pad to.
 *
 *  The cost is that a table column comes out ragged — 44,5 over 28,07 — where fixed
 *  decimals would line the commas up. Legibility of the number won over alignment of the
 *  column, since the column is read one cell at a time. */
function formatter(places) {
    if (!formatters.has(places)) {
        formatters.set(
            places,
            new Intl.NumberFormat("tr-TR", {
                minimumFractionDigits: 0,
                maximumFractionDigits: places,
            })
        );
    }
    return formatters.get(places);
}

function fmt(value) {
    if (value === undefined || !Number.isFinite(value)) {
        return "—";
    }
    return formatter(decimals()).format(value);
}

// endregion

// region Left rail

function drawRail() {
    // The count is on the label because the names alone invite a guess that is wrong:
    // coğrafi bölge and İBBS-1 are two different maps of the country (7 against 12), and
    // İBBS-2 is 26 sub-regions, not the 81 provinces. Seeing "İBBS-2 (26)" next to
    // "İl (81)" settles it without anyone having to look it up.
    $("level").innerHTML = levelsInData()
        .map((l) => {
            const count = new Set(rowsAt(l).map((r) => r.area_id)).size;
            return '<option value="' + l + '"' + (l === state.level ? " selected" : "") +
                   ">" + (LEVEL_LABELS[l] || l) + (count ? " (" + count + ")" : "") +
                   "</option>";
        })
        .join("");

    // Chosen areas get their own block above the list. Searching filters the list, and
    // a selection that scrolls out of sight — or filters away — is a selection the
    // reader cannot undo.
    // Capped. "Tümünü seç" over the districts put a thousand rows here, each with two
    // buttons, and rebuilding three thousand elements was half the cost of every redraw
    // — for a list nobody scrolls to the bottom of. The ones past the cap are still
    // selected and still drawn; they just do not each get a row of their own.
    const listed = state.selection.slice(0, CHOSEN_LIMIT);
    const hidden = state.selection.length - listed.length;

    $("chosen").innerHTML = listed
        .map((id, i) => {
            const muted = state.muted.includes(id);
            // An area chosen at another level stays chosen, so this block can hold a mix.
            // Which one is which matters — "Merkez" alone does not say whether it is a
            // district or a neighbourhood — so anything not from the level on offer says
            // where it came from.
            const from = levelOfArea(id);
            const name = nameOf(id);
            // The country's tag is its own name — "Türkiye Türkiye" — so a tag that only
            // repeats the name is left off.
            const tag = from === state.level || (LEVEL_LABELS[from] || from) === name
                ? ""
                : " <span class='lvl'>" + (LEVEL_LABELS[from] || from) + "</span>";
            return "<li class='" + (muted ? "muted" : "") + "' data-area='" + id + "'>" +
                   "<span class='dot' style='background:" + colour(i) + "'></span>" +
                   "<span class='name'>" + name + tag + "</span>" +
                   "<button class='chip' data-act='mute' title='" +
                   (muted ? "Grafiğe geri koy" : "Grafikten gizle") + "'>" +
                   (muted ? "◎" : "◉") + "</button>" +
                   "<button class='chip' data-act='drop' title='Seçimden çıkar'>✕</button></li>";
        })
        .join("") +
        (hidden ? "<li class='muted'><span class='name'>… ve " + hidden +
                  " alan daha seçili</span></li>" : "");
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

//: How many options a control may have before its buttons fold into a dropdown.
//:
//: Taken from OWID's own explorer rather than invented: there, sex (3 options) and
//: projection scenario (4) are laid out as buttons you can see all of, while indicator
//: (10) and age (25) are dropdowns. The line falls between four and ten; five is where
//: our own controls divide cleanly — sex, the level, a grouping and the value modes fit
//: under it, the indicator tree and the derivations do not.
const PILL_MAX = 5;

/** A one-of-many control: buttons while there are few, a dropdown once there are many.
 *
 *  A dropdown hides every option but the chosen one, which costs a click to answer "what
 *  else is there" — fine for twenty-four indicators, wasteful for "Kadın / Erkek /
 *  Toplam", where the whole question fits on one line.
 *
 *  The buttons are real radios with a label around them, not `<button>`s: a radio group
 *  arrows left and right from the keyboard, reads as one control to a screen reader, and
 *  — the reason it matters here — fires the same bubbling `change` event a `<select>`
 *  does, so the strip's one handler serves both shapes and neither form knows which it
 *  got. What identifies the control moves onto each input as `data-role`, because an
 *  `id` cannot be repeated across the options of a group.
 *
 *  `options` are `{value, label, selected, disabled}`. `html` is emitted as-is after
 *  them, and forces the dropdown — it is how the callers that need `<optgroup>` (the
 *  comparisons and ratios) opt out of buttons entirely. */
function chooser(what, options, {html = "", force = false, title = ""} = {}) {
    const key = what.dim
        ? "data-dim='" + what.dim + "'"
        : what.grouping
          ? "data-grouping='" + what.grouping + "'"
          : "";
    const name = what.dim || what.grouping || what.role;
    const tip = title ? " title=\"" + title + '"' : "";

    if (force || html || options.length > PILL_MAX) {
        return (
            "<select " + (what.role ? "id='" + what.role + "' " : "") + key + tip +
            (what.disabled ? " disabled" : "") + ">" +
            options
                .map((o) => "<option value=\"" + o.value + '"' +
                            (o.selected ? " selected" : "") +
                            (o.disabled ? " disabled" : "") + ">" + o.label + "</option>")
                .join("") +
            html + "</select>"
        );
    }

    return (
        "<div class='pills'" + tip + ">" +
        options
            .map((o) =>
                "<label class='pill" + (o.selected ? " on" : "") +
                (o.disabled ? " off" : "") + "'>" +
                "<input type='radio' name='p-" + name + "' " + key +
                (what.role ? " data-role='" + what.role + "'" : "") +
                " value=\"" + o.value + '"' +
                (o.selected ? " checked" : "") +
                (o.disabled || what.disabled ? " disabled" : "") + ">" +
                "<span>" + o.label + "</span></label>")
            .join("") +
        "</div>"
    );
}

/** The derivation picker.
 *
 *  These used to be hidden everywhere but the line chart and the table, on the reasoning
 *  that a year-on-year change has nothing to say about one year. That was the wrong way
 *  round: the *view* stands on one year, the data does not. "How much did each province
 *  grow last year" is a question about 2025 and 2024 together, and a map is the natural
 *  place to ask it — which is what the reader was reaching for when they found the
 *  derivation offered in the table and missing on the map.
 *
 *  The pyramid is still out: its axis is the age bands, so a derivation would run along
 *  years the chart does not draw. */
function derivationControl() {
    const span = state.view !== "pyramid";
    // A percentage of a number that reaches zero is either undefined or sign-flipped
    // (see positiveBase), so those are offered but not selectable here. Greyed rather
    // than removed: "doğal artışta yıllık değişim neden yok" is a question the control
    // should answer where it is asked.
    const blocked = everNegative();
    const options = Object.entries(meta.derivations || {})
        .filter(([, body]) => span || !body.needs_span)
        .map(([id, body]) => ({
            value: id,
            label: body.label,
            selected: state.derivation === id,
            disabled: blocked && NEEDS_POSITIVE.includes(id),
        }));

    if (!options.length) {
        return "";
    }
    return (
        "<div><div class='dim-label'>Türetme</div>" +
        chooser({role: "derivation"}, [
            {value: "", label: "Ölçüm (ham)", selected: !state.derivation},
            ...options,
        ]) +
        "</div>"
    );
}

/** Absolute or relative. Its own control rather than an entry in the derivation list:
 *  a share is a different *reading* of the same year, while the derivations there are
 *  all about movement over time, and the two combine — you can index a share. */
function shareControl() {
    // Sharing within the indicator needs a breakdown; sharing against the population does
    // not. Net migration has no breakdown at all and "ilin nüfusunun yüzde kaçı" is
    // exactly the question worth asking of it, so the box appears for either reason.
    const inside = canShare();
    const against = canShareAgainstPopulation();
    if (!inside && !against && !shareOfWholeMeans()) {
        return "";
    }
    // Two different percentages, named rather than inferred. They used to be one option
    // whose meaning flipped depending on whether a breakdown happened to be chosen, and
    // a control that quietly changes what it computes is a control nobody can trust —
    // "0-4 seçince neden İznik'e oranı oldu" is the question that always follows.
    const option = (value, label) => ({
        value,
        label,
        selected: state.share === value,
    });

    // A third kind of percentage, one per breakdown: the share *within* that breakdown,
    // holding every other choice where the reader put it.
    //
    // With one breakdown "alanın kendi toplamı" was unambiguous. With three it is not,
    // and it was quietly answering the wrong question: asking for 65+ women who are
    // widowed gave 7,59 — their share of the whole population aged 15 and over, which is
    // true and is not what anybody means by it. The question is "of women aged 65 and
    // over, how many are widowed", and that needs a denominator that keeps sex and age
    // fixed while summing across marital status. Which dimension to sum across is a real
    // choice with more than one right answer, so it is offered rather than guessed.
    // One per breakdown — but only where there is more than one breakdown to tell apart.
    // With a single dim, "kırılım içinde %" and "alanın kendi toplamının %'si" divide by
    // the very same total: kütük nüfusu offered both, side by side, drawing identical
    // maps. Two names for one number is worse than either name alone, because a reader
    // who sees two controls assumes they answer two questions.
    const dims = (state.indicator.dims || []).filter((dim) => valuesOf(dim).length > 1);
    const within =
        dims.length > 1
            ? dims.map((dim) => option("own:" + dim, dimLabel(dim) + " içinde %"))
            : [];

    // "Alanın kendi toplamı" is only a question where there is a breakdown to be a share
    // of; without one it is 100 everywhere, which is arithmetic rather than an answer.
    const options = [
        option("", "Mutlak sayı"),
        ...(shareOfWholeMeans()
            ? [option("country", "Türkiye toplamının %'si")]
            : []),
        ...(inside ? [option("own", "Alanın kendi toplamının %'si"), ...within] : []),
        ...(against
            ? [option("population", (LEVEL_LABELS[state.level] || "Alan") + " nüfusunun %'si")]
            : []),
    ];

    return (
        "<div><div class='dim-label'>Değer</div>" +
        chooser({role: "share"}, options) +
        "</div>"
    );
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
            ? [
                  {
                      value: TOTAL,
                      label: dimValue(dim, TOTAL),
                      selected: state.dims[dim] === TOTAL,
                  },
              ]
            : [];

        // The grouping box sits next to the values it regroups rather than off in its own
        // corner: "hangi yaş" and "hangi yaş bölmesi" are one question asked twice.
        const ways = groupingsFor(dim);
        const finest = fineOffered(dim);
        // A ratio names its own grouping — that is how "65+" resolves to bands — so the
        // box would be a control the reader can move while nothing changes. Disabled and
        // labelled with the grouping the ratio is using, rather than left looking live.
        const byRatio = ratioOn(dim);
        if (ways.length || finest) {
            const options = byRatio
                ? [
                      {
                          value: "",
                          label:
                              meta.groupings?.[byRatio[1].grouping]?.label ||
                              byRatio[1].grouping,
                          selected: true,
                      },
                  ]
                : [
                      ...(finest
                          ? [
                                {
                                    value: FINE,
                                    label: "Tek yaş",
                                    selected: state.grouping[dim] === FINE,
                                },
                            ]
                          : []),
                      {
                          value: "",
                          label: "Yayımlandığı gibi",
                          selected: !state.grouping[dim],
                      },
                      ...ways.map(([id, g]) => ({
                          value: id,
                          label: g.label,
                          selected: state.grouping[dim] === id,
                      })),
                  ];

            groups.push(
                "<div><div class='dim-label'>" + dimLabel(dim) + " bölmesi" +
                (byRatio ? " <span class='muted'>· oran belirliyor</span>" : "") +
                "</div>" +
                chooser({grouping: dim, disabled: byRatio}, options) +
                "</div>"
            );
        }

        // Comparisons sit at the bottom of the same box, under a rule: they are answers
        // to "which value" too, just ones that need two.
        const against = comparisonsFor(dim)
            .map(([id, c]) => "<option value='" + id + "'" +
                              (state.dims[dim] === id ? " selected" : "") + ">" +
                              c.label + "</option>")
            .join("");

        // Ratios sit in the same box for the same reason comparisons do: "which value",
        // "which two values" and "which two sets of values" are one question asked three
        // ways, and picking a ratio *is* the answer to it. Nothing has to be disabled —
        // the ratio replaces the value rather than sitting beside it.
        const over = ratiosFor(dim)
            .map(([id, r]) => "<option value='" + id + "'" +
                              (state.dims[dim] === id ? " selected" : "") + ">" +
                              r.label + "</option>")
            .join("");

        // The comparisons and ratios are `<optgroup>`s, which buttons have no equivalent
        // of — a group of pills with two unlabelled kinds in it would read as one flat
        // list where the last two entries do something else entirely. So their presence
        // is what decides the shape here, not only the count.
        groups.push(
            "<div><div class='dim-label'>" + dimLabel(dim) + "</div>" +
            chooser(
                {dim},
                [
                    ...all,
                    ...options.map((v) => ({
                        value: v,
                        label: dimValue(dim, v),
                        selected: String(state.dims[dim]) === String(v),
                    })),
                ],
                {
                    html:
                        (against ? "<optgroup label='Karşılaştırma'>" + against + "</optgroup>" : "") +
                        (over ? "<optgroup label='Oran'>" + over + "</optgroup>" : ""),
                }
            ) +
            "</div>"
        );
    }

    groups.push(splitControl());
    $("dims").innerHTML = groups.filter(Boolean).join("");
}

/** The "draw this breakdown as several series" picker.
 *
 *  Only where it can be drawn. On a map an area has one colour, on a pyramid the age
 *  bands are already the vertical axis, and on a scatter both axes are spoken for — in
 *  all three the control would be a switch that does nothing, which is worse than a
 *  control that is not there. */
function splitControl() {
    const dims = SPLIT_VIEWS.includes(state.view) ? splittable() : [];
    if (!dims.length) {
        return "";
    }
    return (
        "<div><div class='dim-label'>Serilere ayır</div>" +
        chooser(
            {role: "split"},
            [
                {value: "", label: "Ayırma", selected: !state.split},
                ...dims.map((dim) => ({
                    value: dim,
                    label: dimLabel(dim),
                    selected: state.split === dim,
                })),
            ],
            {
                title:
                    "Seçili her alan için bu kırılımın bütün değerleri ayrı çizgi olur: " +
                    "Bursa 0-14, Bursa 15-64, Bursa 65+",
            }
        ) +
        "</div>"
    );
}

//: Where a split can be drawn at all. See splitControl.
const SPLIT_VIEWS = ["line", "bar", "table"];

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
    // The scatter is the one view that is not a property of an indicator: it is a
    // property of there being *two*. So it is not declared per indicator in the
    // dictionary — every indicator would have to list it, and the list would still be
    // wrong at a level where nothing else is published.
    if (view === "scatter") {
        return versusOffered().length
            ? {enabled: true, reason: ""}
            : {
                  enabled: false,
                  reason: (LEVEL_LABELS[state.level] || state.level) +
                          " düzeyinde karşılaştırılacak ikinci gösterge yok",
              };
    }
    if (!(state.indicator.views || []).includes(view)) {
        return {enabled: false, reason: "Bu gösterge için tanımlı değil"};
    }
    if (view === "map" && !geometry) {
        return {enabled: false, reason: "Sınır geometrisi henüz çekilmedi"};
    }
    if (view === "map" && !mappableAs(state.level)) {
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

//: Past this many series the right-hand names stop fitting and the cursor box stops
//: being a box. Both fall back to something that still works at any count.
const LABEL_LIMIT = 12;

//: How many chosen areas get a row of their own in the rail. Past this the rest are
//: counted rather than listed — they are still selected and still drawn.
const CHOSEN_LIMIT = 150;

//: How many table rows are built. The frame shows about fifteen at a time; sorting runs
//: over every row regardless, so the ones that matter are always at the top.
const TABLE_LIMIT = 200;

/** A series keeps its colour by its place in the selection, muted or not. */
function colour(index) {
    return token("--series-" + ((index % 10) + 1));
}

function colourOf(area) {
    return colour(state.selection.indexOf(area));
}

/** Round gridline step and the ends of the axis, for a range that may go below zero.
 *
 *  The old version took a maximum and assumed the floor was zero. Year-on-year change is
 *  the derivation that breaks that: a district that shrank draws at −1%, which landed
 *  below the bottom of the frame and simply left the picture. Anything that can be
 *  negative needs an axis that admits it, and a zero line to read it against. */
function niceTicks(min, max, fromZero = true) {
    // Fitting the axis to the data exaggerates every wiggle, which is why zero is the
    // default. But a chart of shares that all sit between 70 and 95 spends three quarters
    // of its height on empty space and every series lands in the same flat band — there
    // the honest reading is the one you can actually see, so it is one click away.
    // Fitted does not mean "below zero": with values from 29 to 7620 the padding rounded
    // the axis down to −2.000, inventing a region the data never visits. It only crosses
    // zero when the data does.
    const padded = min - (max - min) * 0.08;
    const bottom = fromZero ? Math.min(0, min) : min < 0 ? padded : Math.max(0, padded);
    const raw = Math.max(1e-9, (max - bottom) / 5);
    const magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) || magnitude * 10;
    return {
        step,
        top: Math.ceil(max / step) * step || step,
        bottom: Math.floor(bottom / step) * step,
    };
}

/** An axis: where its ticks go, and where a value sits along it as a fraction from 0 to 1.
 *
 *  Two rules for the same job, so the charts do not each grow their own copy. The
 *  logarithmic one exists because populations run from Bayburt's 85 thousand to
 *  İstanbul's 15,7 million: on a linear axis eighty of the eighty-one provinces are
 *  pressed into the bottom eighth of the chart and only İstanbul is legible. A log axis
 *  gives equal room to each factor of ten, so "doubled" is the same distance everywhere.
 *
 *  Zero and negatives have no place on it — there is no power of ten that reaches them —
 *  so they are dropped and counted rather than clamped to the floor, where they would
 *  look like very small values instead of missing ones. */
function axisScale(values, {log, fromZero}) {
    const usable = values.filter(Number.isFinite);
    if (!usable.length) {
        return null;
    }

    if (log) {
        const positive = usable.filter((v) => v > 0);
        if (!positive.length) {
            return null;
        }
        const low = Math.min(...positive);
        const high = Math.max(...positive);

        // Every 1-2-5 step across the range, then the axis is cut to the two that just
        // enclose the data. Rounding out to whole powers of ten instead put provinces
        // running to 15,7 million on an axis that ran to a hundred million, and half the
        // chart was empty.
        const candidates = [];
        for (let e = Math.floor(Math.log10(low)) - 1; e <= Math.ceil(Math.log10(high)) + 1; e += 1) {
            for (const m of [1, 2, 5]) {
                candidates.push(m * Math.pow(10, e));
            }
        }
        const bottom = [...candidates].reverse().find((v) => v <= low) ?? low;
        const top = candidates.find((v) => v >= high) ?? high;

        // Over a wide span the 2 and 5 steps become a thicket, so only the powers of ten
        // are drawn there.
        const decades = Math.log10(top) - Math.log10(bottom);
        const ticks = candidates.filter(
            (v) => v >= bottom && v <= top &&
                   (decades <= 3 || Math.abs(Math.log10(v) - Math.round(Math.log10(v))) < 1e-9)
        );
        const span = Math.log10(top) - Math.log10(bottom) || 1;
        return {
            ticks,
            bottom,
            top,
            log: true,
            at: (v) => (Math.log10(v) - Math.log10(bottom)) / span,
            plots: (v) => Number.isFinite(v) && v > 0,
            dropped: usable.length - positive.length,
        };
    }

    const {step, top, bottom} = niceTicks(Math.min(...usable), Math.max(...usable), fromZero);
    const ticks = [];
    for (let v = bottom; v <= top + step / 2; v += step) {
        ticks.push(v);
    }
    return {
        ticks,
        bottom,
        top,
        log: false,
        at: (v) => (v - bottom) / Math.max(1e-9, top - bottom),
        plots: Number.isFinite,
        dropped: 0,
    };
}

/** An axis tick, printed with enough precision to tell it from its neighbours.
 *
 *  The indicator's own precision is right for values but wrong for a logarithmic axis,
 *  where the ticks get closer together the further down they go. Yıllık değişim prints to
 *  one decimal, so the ticks 0,1 · 0,05 · 0,02 · 0,01 all came out as "0,1", "0,1", "0,0",
 *  "0,0" — a scale reading zero at a place a log axis can never reach. Small ticks get the
 *  digits they need; everything else keeps the indicator's own rounding. */
function tickText(value, places) {
    if (value === 0 || Math.abs(value) >= 1) {
        return formatter(places).format(value);
    }
    const needed = Math.min(6, Math.ceil(-Math.log10(Math.abs(value))) + 1);
    return formatter(Math.max(places, needed)).format(value);
}

/** The axis rule the reader picked. Kept out of the chart bodies so the chip, the state
 *  and the two charts cannot drift apart. */
function logScale() {
    return state.scaleType === "log";
}

/** The linear/log chips, drawn the same way wherever the axis is offered.
 *
 *  Named for what they do to the picture rather than for the mathematics: "her katta eşit
 *  aralık" is the property the reader is choosing, and it is the reason to click it. */
/** A one-line summary of what a cross-section view is showing.
 *
 *  The charts show shape and the cursor shows one value; between the two there was nothing
 *  that answered "what is normal here" — the reader had to eyeball a middle off a colour
 *  ramp. Mean and median are both given because they part company exactly where it
 *  matters: İstanbul pulls the mean population to 1,1 million while the median province
 *  sits near 560 thousand, and the gap between the two numbers *is* the skew.
 *
 *  Given the values the caller already has, so it costs one pass and no second slice. */
function summaryLine(pairs) {
    const usable = pairs.filter((p) => Number.isFinite(p.value));
    if (usable.length < 2) {
        return "";
    }
    const sorted = [...usable].sort((a, b) => a.value - b.value);
    const middle = sorted.length % 2
        ? sorted[(sorted.length - 1) / 2].value
        : (sorted[sorted.length / 2 - 1].value + sorted[sorted.length / 2].value) / 2;
    const mean = usable.reduce((sum, p) => sum + p.value, 0) / usable.length;
    const low = sorted[0];
    const high = sorted[sorted.length - 1];

    const cell = (label, body) =>
        "<span><span class='muted'>" + label + "</span> " + body + "</span>";
    return "<div class='summary'>" +
        cell("ortalama", fmt(mean)) +
        cell("ortanca", fmt(middle)) +
        cell("en düşük", fmt(low.value) + " · " + low.name) +
        cell("en yüksek", fmt(high.value) + " · " + high.name) +
        cell("alan", usable.length) +
        "</div>";
}

function scaleTypeToggle() {
    return "<span>Ölçek</span>" +
        "<button class='chip" + (logScale() ? "" : " on") +
        "' data-scaletype='linear' title='Eşit farklar eşit aralık: 100 bin ile 200 bin arası, 1 milyon ile 1,1 milyon arası kadar'>Doğrusal</button>" +
        "<button class='chip" + (logScale() ? " on" : "") +
        "' data-scaletype='log' title='Eşit katlar eşit aralık: iki katına çıkmak her yerde aynı mesafe. Bayburt ile İstanbul aynı grafikte okunabilir olur'>Logaritmik</button>";
}

function lineChart() {
    // One row per series, not per area: with a breakdown split, an area contributes one
    // line per value (splitSeries). Colour still comes from the area, so the bands of a
    // province stay visibly one family.
    const rows = allSeries()
        .map((s) => ({
            id: s.key,
            area: s.label,
            pts: s.points,
            colour: colourOf(s.area),
            dash: dashFor(s),
        }))
        .filter((r) => r.pts.some((p) => Number.isFinite(p.value)));
    if (!rows.length) {
        return empty("Soldan en az bir alan seçin.");
    }

    const span = years();
    const [minYear, maxYear] = [span[0], span[span.length - 1]];
    const all = rows.flatMap((r) => r.pts.map((p) => p.value)).filter(Number.isFinite);
    const scale = axisScale(all, {log: logScale(), fromZero: state.axis === "zero"});
    if (!scale) {
        return empty("Logaritmik eksende çizilecek pozitif değer yok.");
    }

    // Room on the right for the labels, unless there are too many to label at all.
    const labelled = rows.length <= LABEL_LIMIT;
    const L = 96, R = labelled ? 190 : 24, T = 16, B = 38;
    const x = (y) => L + ((y - minYear) / Math.max(1, maxYear - minYear)) * (PLOT_W - L - R);
    const yv = (v) => T + (1 - scale.at(v)) * (PLOT_H - T - B);

    let svg = '<svg class="plot" viewBox="0 0 ' + PLOT_W + " " + PLOT_H + '" role="img">';

    for (const v of scale.ticks) {
        // Zero is a real boundary once the data crosses it — above the line is growth,
        // below it is loss — so it is drawn solid while the rest stay dashed.
        const isZero = !scale.log && v === 0 && scale.bottom < 0;
        svg += '<line x1="' + L + '" x2="' + (PLOT_W - R) + '" y1="' + yv(v) + '" y2="' + yv(v) +
               '" stroke="' + token(isZero ? "--text-tertiary" : "--stroke-divider") + '"' +
               (isZero ? "" : ' stroke-dasharray="4 5"') + "/>" +
               axisText(L - 12, yv(v) + 4,
                        scale.log ? tickText(v, decimals()) : fmt(v), "end");
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
    // Past a couple of dozen series there is no arrangement that works — the names run
    // off the frame and cover the chart — so they are dropped and the cursor does the
    // naming instead.
    const lastOf = (r) => [...r.pts].reverse().find((p) => scale.plots(p.value));
    const labels = labelled
        ? rows
              .filter(lastOf)
              .map((r) => ({r, y: yv(lastOf(r).value)}))
              .sort((a, b) => b.y - a.y)
        : [];
    labels.forEach((l, i) => {
        if (i && labels[i - 1].y - l.y < 16) {
            l.y = labels[i - 1].y - 16;
        }
    });

    for (const row of rows) {
        // A missing year breaks the line rather than being drawn through. The share of a
        // neighbourhood whose under-18 count TÜİK withheld has no value at all, and
        // joining across it would draw a straight line the data does not support — it
        // also put a literal NaN in the path and the browser refused the whole shape.
        let broken = true;
        const d = row.pts
            .map((p) => {
                // On a log axis a zero or a negative is not a low point, it is a point the
                // axis cannot reach — so it breaks the line exactly like a missing year.
                if (!scale.plots(p.value)) {
                    broken = true;
                    return "";
                }
                const move = broken ? "M" : "L";
                broken = false;
                return move + x(p.year).toFixed(1) + " " + yv(p.value).toFixed(1);
            })
            .filter(Boolean)
            .join(" ");

        const last = [...row.pts].reverse().find((p) => scale.plots(p.value));
        if (!last) {
            continue;
        }
        const label = labels.find((l) => l.r === row);

        svg += '<path d="' + d + '" fill="none" stroke="' + row.colour +
               '" stroke-width="' + (labelled ? 2.5 : 1.4) + '" stroke-linejoin="round"' +
               (row.dash ? ' stroke-dasharray="' + row.dash + '"' : "") + "/>";
        if (label) {
            svg += '<circle cx="' + x(last.year) + '" cy="' + yv(last.value) + '" r="3" fill="' + row.colour + '"/>' +
                   '<path d="M' + (x(last.year) + 4) + " " + yv(last.value) + "L" + (PLOT_W - R + 8) + " " + label.y +
                   '" fill="none" stroke="' + row.colour + '" stroke-width="1" opacity=".55"/>' +
                   '<text class="legend-label" x="' + (PLOT_W - R + 14) + '" y="' + (label.y + 4) +
                   '" fill="' + row.colour + '">' + row.area + "</text>";
        }
    }

    const note = "<div class='map-head'>" +
        (labelled
            ? "<span></span>"
            : "<span>" + rows.length + " seri · adlar için imleci grafiğin üstünde gezdirin</span>") +
        (scale.dropped
            ? "<span>· " + scale.dropped +
              " değer sıfır ya da eksi, logaritmik eksende çizilemiyor</span>"
            : "") +
        "<span class='spacer'></span>" + scaleTypeToggle() +
        // Zero is not a place a logarithmic axis can go, so the choice between "from zero"
        // and "fitted" simply does not arise there — the chips are dropped rather than
        // shown doing nothing.
        (logScale()
            ? ""
            : "<span>Eksen</span>" +
              "<button class='chip" + (state.axis === "zero" ? " on" : "") +
              "' data-axis='zero' title='Eksen sıfırı içerir: oranlar dürüst okunur'>Sıfırdan</button>" +
              "<button class='chip" + (state.axis === "data" ? " on" : "") +
              "' data-axis='data' title='Eksen verinin aralığına oturur: hepsi 70-95 arasındayken farkı ancak böyle görürsünüz'>Veriye göre</button>") +
        "</div>";

    hover = {kind: "line", rows, years: span, left: L, right: PLOT_W - R, x, yv};
    return note + wrapPlot(svg + "</svg>");
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

            // Listing every series at once is the point of the crosshair — until there
            // are fifty-seven of them and the box is taller than the screen. Past that,
            // it lists the ones nearest the pointer, which is what the pointer is asking
            // about, and says how many it left out.
            const here = hover.rows
                .map((r) => ({r, point: r.pts.find((p) => p.year === year)}))
                .filter((row) => row.point);

            const atCursor = event.offsetY / scale;
            const shown = here.length <= LABEL_LIMIT
                ? here
                : [...here]
                      .sort((a, b) => Math.abs(hover.yv(a.point.value) - atCursor) -
                                      Math.abs(hover.yv(b.point.value) - atCursor))
                      .slice(0, LABEL_LIMIT)
                      .sort((a, b) => b.point.value - a.point.value);

            const body = shown
                .map((row) => tipRow(row.r.colour, row.r.area, fmt(row.point.value)))
                .join("");
            const rest = here.length - shown.length;

            place(event,
                  "<div class='tip-head'>" + year + " · " + unitLabel() + "</div>" + body +
                  (rest ? "<div class='tip-more'>imlece en yakın " + shown.length +
                          " seri · " + rest + " tane daha</div>" : ""),
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

//: A bar and its label need about this much height to stay legible.
const BAND = 22;

function barChart() {
    const rows = allSeries()
        .map((s) => {
            const point = s.points.find((p) => p.year === state.year);
            return point && Number.isFinite(point.value)
                ? {area: s.label, value: point.value, colour: colourOf(s.area)}
                : null;
        })
        .filter(Boolean)
        .sort((a, b) => b.value - a.value);
    if (!rows.length) {
        return empty("Seçili alanların bu yıl için değeri yok.");
    }

    // The chart used to divide a fixed height by however many bars there were, so
    // forty-six of them got eight pixels each and their thirteen-pixel names printed on
    // top of one another — a wall of text with no bars visible at all. Instead the chart
    // grows with the data and scrolls inside its own frame.
    const T = 16;
    const height = Math.max(PLOT_H, T + 16 + rows.length * BAND);
    const band = (height - T - 16) / rows.length;
    const L = 150, R = 130;

    // Bars are read against zero: a bar chart that starts anywhere else is a lie about
    // proportion, so this axis does not follow the "veriye göre" setting.
    const max = Math.max(...rows.map((r) => r.value), 0);
    const min = Math.min(...rows.map((r) => r.value), 0);
    const zero = L + (min < 0 ? (-min / (max - min)) * (PLOT_W - L - R) : 0);
    const unit = (PLOT_W - L - R) / Math.max(1e-9, max - min);

    let svg = '<svg class="plot" viewBox="0 0 ' + PLOT_W + " " + height + '" role="img"' +
              ' style="min-height:' + height + 'px">';
    rows.forEach((row, i) => {
        const y = T + i * band + band * 0.18;
        const h = band * 0.64;
        const w = Math.abs(row.value) * unit;
        const x = row.value < 0 ? zero - w : zero;
        svg += '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h +
               '" rx="2" fill="' + row.colour + '" data-value="' + fmt(row.value) +
               '" data-name="' + row.area + '" data-colour="' + row.colour + '"/>' +
               axisText(L - 12, y + h / 2 + 5, row.area, "end") +
               axisText(x + (row.value < 0 ? -12 : w + 12), y + h / 2 + 5, fmt(row.value),
                        row.value < 0 ? "end" : "start");
    });
    if (min < 0) {
        svg += '<line x1="' + zero + '" x2="' + zero + '" y1="' + T + '" y2="' + (height - 16) +
               '" stroke="' + token("--text-tertiary") + '"/>';
    }

    hover = {kind: "shape"};
    return "<div class='plot-scroll'>" + wrapPlot(svg + "</svg>") + "</div>" +
           summaryLine(rows.map((r) => ({name: r.area, value: r.value})));
}

/** Rows for the table, in whatever order the reader clicked a header into.
 *
 *  Sorting by a year is the question "who was biggest in 2013", which the table could not
 *  answer before: it came out in whatever order the rail happened to be in, and with a
 *  hundred neighbourhoods that is no order at all. */
function tableRows(years) {
    // Below province the name alone does not identify a row — forty-odd districts are
    // called Merkez — so what it sits inside comes with it. Appended to the name rather
    // than given a column of its own: a column would repeat the same word down hundreds
    // of rows and sort into a useless order, while the reader needs it exactly where the
    // name is.
    // Only where the name really is ambiguous. Province names are unique, so once the
    // rail gained region boxes every row started printing "Antalya · Akdeniz" — the same
    // word repeated down a column to disambiguate something that was never ambiguous.
    const keys = filtersFor();
    const here = areasAtLevel();
    const repeats = new Set();
    const seenNames = new Set();
    for (const area of here) {
        if (seenNames.has(area.name)) {
            repeats.add(area.name);
        }
        seenNames.add(area.name);
    }
    const inside = keys.length && repeats.size
        ? new Map(here.map((a) => [a.id, a.in[keys[0]] || ""]))
        : null;

    // One row per series: with a breakdown split, an area becomes one row per value.
    const rows = allSeries().map((s) => {
        const where = inside?.get(s.area);
        return {
            id: s.key,
            name: s.label + (where ? " · " + where : ""),
            by: new Map(s.points.map((p) => [p.year, p.value])),
        };
    });

    const {descending} = state.sort;
    // The header carries the column as text; the year keys are numbers.
    const column = state.sort.column === "name" ? "name" : Number(state.sort.column);
    rows.sort((a, b) => {
        if (column === "name" || !years.includes(column)) {
            return a.name.localeCompare(b.name, "tr") * (descending ? -1 : 1);
        }
        // A missing year sorts last whichever way round the column is: it is not a small
        // value, it is an absent one.
        const [x, y] = [a.by.get(column), b.by.get(column)];
        if (!Number.isFinite(x) || !Number.isFinite(y)) {
            return Number.isFinite(x) ? -1 : Number.isFinite(y) ? 1 : 0;
        }
        return (descending ? y - x : x - y) || a.name.localeCompare(b.name, "tr");
    });
    return rows;
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
    const rows = tableRows(shown);

    // Every header carries the sort mark, faint until it is the one in use. Only marking
    // the active column left no sign that the others could be clicked at all.
    const mark = (column) =>
        state.sort.column !== column
            ? "<span class='sort-mark'>↕</span>"
            : "<span class='sort-mark on'>" + (state.sort.descending ? "↓" : "↑") + "</span>";
    const head = (column, label) =>
        "<th class='sortable" + (column === "name" ? " sticky-col" : "") +
        (state.sort.column === column ? " sorted" : "") +
        "' data-sort='" + column + "' title='" + label + " sütununa göre sırala'>" +
        label + mark(column) + "</th>";

    // Capped. Nine hundred rows across twenty years is twenty thousand cells, and
    // building them was four hundred milliseconds of every redraw — measured against the
    // same selection drawn as a line chart, which cost a hundred and sixty. The box shows
    // fifteen rows at a time, so the rest were paid for and never looked at. Sorting
    // still runs over everything, which is what makes the top of the list the answer.
    const shownRows = rows.slice(0, TABLE_LIMIT);
    const over = rows.length - shownRows.length;

    let html = "<div class='grid-head'>" + rows.length + " satır" +
               (over ? " · ilk " + TABLE_LIMIT + "'ü gösteriliyor, sıralama hepsine " +
                       "uygulanır (tamamı için ↓ İndir)" : "") +
               " · <b>bir yıl başlığına tıklayın</b>, o yıla göre sıralanır — " +
               "ikinci tıklama tersine çevirir</div>" +
               "<div class='grid-wrap' style='max-height:" + PLOT_H +
               "px'><table class='grid'><thead><tr>" +
               head("name", LEVEL_LABELS[state.level] || state.level) +
               shown.map((y) => head(String(y), y)).join("") + "</tr></thead><tbody>";

    for (const row of shownRows) {
        html += "<tr><td class='sticky-col'>" + row.name + "</td>" +
                shown.map((y) => "<td>" + fmt(row.by.get(y)) + "</td>").join("") +
                "</tr>";
    }
    // Of the year on the slider, not of the whole table: the columns are nineteen
    // different cross-sections and there is no one average across all of them. Says which
    // year, so the number cannot be read as a summary of everything on screen.
    return html + "</tbody></table></div>" +
           summaryLine(rows.map((r) => ({name: r.name, value: r.by.get(state.year)})))
               .replace("<div class='summary'>",
                        "<div class='summary'><span><span class='muted'>yıl</span> " +
                        state.year + "</span>");
}

/** One pyramid per selected area, side by side, drawn on a shared scale.
 *
 *  A shared scale is the point: two pyramids each normalised to their own maximum
 *  compare shapes but hide that one province is ten times the other. Every pyramid is
 *  a fixed share of the width, so adding a third narrows all three rather than
 *  squeezing the last one. */
/** Where an open-ended top band is taken to end.
 *
 *  A closing band has no published upper edge, and a density needs one. Running it to a
 *  hundred is the ordinary demographic convention and it is close enough to true that the
 *  bar stops lying: `75+` becomes twenty-five years wide instead of the one year the
 *  bands around it cover, which is the difference between a plausible tail and a bar
 *  running the width of the panel. Stated on the chart, not hidden in here. */
const OPEN_BAND_END = 100;

/** How many years of life an age band covers: `30` is one, `0-4` is five, `75+` is open
 *  and gets the assumption above. Returns the width and whether it was assumed. */
function bandWidth(label) {
    const text = String(label);
    if (/^\d+$/.test(text)) {
        return {years: 1, open: false};
    }
    const span = text.match(/^(\d+)\s*-\s*(\d+)$/);
    if (span) {
        return {years: Number(span[2]) - Number(span[1]) + 1, open: false};
    }
    const open = text.match(/^(\d+)\s*\+$/);
    if (open) {
        return {years: Math.max(1, OPEN_BAND_END - Number(open[1])), open: true};
    }
    return {years: 1, open: false};
}

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
    const wholeFor = (area) => (state.share === "own" ? wholeOf(levelOfArea(area)) : null);

    // Every breakdown control applies here too — pick Kadın and you get the female side
    // alone, on a scale that fits it. Age is the exception: it is this chart's own
    // vertical axis, so narrowing it would leave a pyramid of one band. The head says so
    // rather than letting the control look broken.
    const others = (state.indicator.dims || []).filter((d) => d !== "age");
    const ignoringAge = state.dims.age && state.dims.age !== TOTAL;

    const rowsOf = (area) => {
        const rows = rowsAt(levelOfArea(area)).filter(
            (r) => r.year === state.year && r.area_id === area &&
                   others.every((d) => state.dims[d] === TOTAL ||
                                       String(r[d]) === String(state.dims[d]))
        );
        const whole = wholeFor(area);
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

    // A bar's length is people *per year of age*, not people.
    //
    // Bands do not all cover the same stretch of life. In single-year mode the page holds
    // seventy-five one-year bands and then `75+`, which is a quarter of a century in one
    // lump: drawn at the same length rule it came out as a bar running the full width of
    // the panel, and it reads as a spike in the population when it is only a spike in how
    // the source chose to group. Dividing by the width makes the eye compare areas, which
    // is what a histogram is for, and leaves the five-year pyramid looking exactly as it
    // did — every band there is five wide, so the whole picture is scaled by one number.
    //
    // The closing band has no published upper edge, so its width is assumed rather than
    // read (OPEN_BAND_END). It is drawn faded and the head says so.
    const widths = new Map(bands.map((label) => [label, bandWidth(label)]));
    const perYear = (row) => row.value / widths.get(row.age).years;
    const openBand = bands.find((label) => widths.get(label).open);
    // Every band's span, the assumed one included: what decides whether dividing by the
    // width changes the picture at all. Counting only the closed bands missed the
    // five-year pyramid, where they are all five wide and the closing band is not.
    const spans = bands.map((label) => widths.get(label).years);

    // Two questions, two scales. "How many people" wants one shared scale — İstanbul
    // towering over Afyonkarahisar is the answer. "What shape is this population" wants
    // each panel scaled to itself, or the smaller one is a sliver you cannot read.
    const shared = Math.max(...all.map(perYear));
    const maxOf = (rows) => (state.panelScale === "own" ? Math.max(...rows.map(perYear)) : shared);

    // The age labels are printed down the left of the whole drawing, so the first panel
    // has to start clear of them or its bars run under the text.
    const T = 34;
    const GUTTER = 56;
    const cell = (PLOT_W - GUTTER) / areas.length;
    const band = (PLOT_H - T - 16) / bands.length;

    // With one sex selected there is no second side to balance against, so the single
    // arm gets the whole panel instead of half of it — otherwise the chart reads as a
    // pyramid with its right half cut off rather than as one sex on its own.
    const oneSided = sexes.length === 1;

    let svg = '<svg class="plot" viewBox="0 0 ' + PLOT_W + " " + PLOT_H + '" role="img">';

    areas.forEach((area, ai) => {
        const rows = rowsOf(area);
        const max = maxOf(rows);
        const left = GUTTER + cell * ai;
        const mid = oneSided ? left + 8 : left + cell / 2;
        const arm = oneSided ? cell - 24 : cell / 2 - 20;

        svg += '<text x="' + (left + cell / 2) + '" y="14" text-anchor="middle" fill="' +
               colourOf(area) + '" font-size="13">' + nameOf(area) +
               (state.panelScale === "own"
                   ? " · " + fmt(max) + " ölçek" +
                     (Math.min(...spans) !== Math.max(...spans) ? "/yaş" : "")
                   : "") + "</text>";

        bands.forEach((label, i) => {
            const y = PLOT_H - 16 - (i + 1) * band + band * 0.15;
            const h = band * 0.7;
            sexes.forEach((s, si) => {
                const row = rows.find((r) => r.age === label && r.sex === s);
                if (!row) {
                    return;
                }
                const w = Math.max(0, (perYear(row) / max) * arm);
                const open = label === openBand;
                svg += '<rect x="' + (oneSided ? mid : si === 0 ? mid - 8 - w : mid + 8) +
                       '" y="' + y +
                       '" width="' + w + '" height="' + h + '" fill="' + colour(si) +
                       (open ? '" opacity=".45' : "") +
                       '" rx="1" data-colour="' + colour(si) + '" data-name="' + nameOf(area) + " · " +
                       dimValue("sex", s) + " " + label + (open ? " (açık uçlu)" : "") +
                       '" data-value="' + fmt(row.value) + '"/>';
            });
            // Seventy-six labels down a 400-pixel axis is a grey smear. Every fifth band
            // is enough to read the scale by, and the open band always gets its name
            // because it is the one the reader most needs to identify.
            const dense = bands.length > 20;
            if (ai === 0 && (!dense || i % 5 === 0 || label === openBand)) {
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
        // Said only where it changes the reading: with every band the same width the
        // division cancels out and the picture is the plain one.
        (Math.min(...spans) !== Math.max(...spans)
            ? "<span>· çubuk uzunluğu <b>yaş yılı başına</b>, bantlar eşit genişlikte değil</span>"
            : "") +
        (openBand
            ? "<span>· <b>" + openBand + "</b> açık uçlu, " + OPEN_BAND_END +
              " yaşa kadar sayıldı</span>"
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

/** Can the map draw this level, and how?
 *
 *  Only provinces have their own shapes in the boundary file. But a geographic region and
 *  an İBBS region are *exactly* sets of provinces — nothing else — so they can be drawn by
 *  painting their provinces one colour, with the internal borders taken out. That is not
 *  an approximation of the region: it is the region, at the resolution we have. Without
 *  this the map tab was dead at four of the five levels the fertility rate is published
 *  at, which is most of what that indicator has to say. */
function mappableAs(level) {
    if (levelsWithGeometry().includes(level)) {
        return "own";
    }
    // District shapes live in eighty-one per-province files rather than the main one.
    if (level === "district") {
        return "own";
    }
    // A province belongs to one area at each level above it, and meta says which.
    const parents = Object.values(meta.belongs || {});
    const known = new Set(parents.flat());
    const here = new Set(rowsAt(level).map((r) => r.area_id));
    return [...here].some((id) => known.has(id)) ? "provinces" : "";
}

/** For a level drawn out of province shapes: which area each province rolls up into. */
function rollUp(level) {
    return remember("rollup|" + level, () => {
        const wanted = new Set(rowsAt(level).map((r) => r.area_id));
        const map = new Map();
        for (const [province, chain] of Object.entries(meta.belongs || {})) {
            const found = chain.find((a) => wanted.has(a));
            if (found) {
                map.set(province, found);
            }
        }
        return map;
    });
}

function map() {
    if (!geometry) {
        return empty(
            "Harita için sınır geometrisi gerekiyor; henüz çekilmedi.",
            "uv run python scripts/fetch_geometry.py"
        );
    }

    const opened = districtMode() && state.focus ? districts.get(state.focus) : null;
    const wide = districtMode() && !state.focus;

    // Levels with no shapes of their own borrow the provinces they are made of.
    const borrowed = !opened && !wide && mappableAs(state.level) === "provinces";
    const rolls = borrowed ? rollUp(state.level) : null;
    const features = opened
        ? opened.features
        : wide
          ? districtFeatures
          : geometry.features.filter(
                (f) => f.properties.area_level === (borrowed ? "province" : state.level)
            );
    if (!features.length) {
        return empty((LEVEL_LABELS[state.level] || state.level) + " düzeyinde sınır geometrisi yok.");
    }

    // Drawing districts means reading district rows: the scale then belongs to the
    // largest district on screen, not to İstanbul.
    const level = effectiveLevel();
    const here = derivedSlice(level);
    const rows = here.filter((r) => r.year === state.year);
    const byId = new Map(rows.map((r) => [r.area_id, r.value]));

    // Which area a drawn shape stands for: itself, or the region it rolls up into.
    const standsFor = (feature) =>
        rolls ? rolls.get(feature.properties.area_id) : feature.properties.area_id;

    // Non-finite values are excluded from the ramp, not just from the drawing. A share
    // whose denominator was withheld is NaN, and NaN poisons everything downstream:
    // Math.min returns NaN, the sort comparator goes incoherent, and the legend came out
    // with edges running backwards under a bound printed as "—".
    const usable = (v) => Number.isFinite(v);
    const drawnIds = new Set(features.map(standsFor).filter(Boolean));
    const thisYear = [...drawnIds].map((id) => byId.get(id)).filter(usable);

    // Two ways to set the ends of the ramp, and they answer different questions.
    // Per-year rescaling shows who is biggest *this* year — which barely moves, so the
    // map looks frozen as the years play. A scale fixed over the whole span keeps the
    // ends still and lets the colours actually travel: that is growth.
    const span = state.scaleSpan === "fixed"
        ? here.filter((r) => drawnIds.has(r.area_id)).map((r) => r.value).filter(usable)
        : thisYear;

    const values = thisYear;
    const [low, high] = span.length ? [Math.min(...span), Math.max(...span)] : [0, 0];

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
    // Which end is dark is a reading decision, not a fact: for population the big places
    // deserve the strong colour, for a falling fertility rate the *low* end is the news.
    const colours = rampColours(edges.length + 1);
    if (state.reverse) {
        colours.reverse();
    }
    const colourFor = (v) => (usable(v) ? colours[binOf(v, edges)] : base);

    // Pan and zoom are a viewBox, not a transform: the strokes then keep their width and
    // the shapes stay crisp however far in the reader goes.
    const view = state.mapView;
    const drillable = !state.focus && OFFERED_LEVELS.includes("district");
    let svg = '<svg id="map-svg" class="plot ' + (drillable ? "drillable" : "") +
              '" viewBox="' + view.x + " " + view.y + " " + view.w + " " + view.h + '" role="img">';
    const nameFor = new Map(rows.map((r) => [r.area_id, r.area]));

    // The projected outline of a shape does not change as the reader moves the year on or
    // recolours the map — only the fill does. Rebuilding 973 path strings (a megabyte of
    // text) on every redraw was most of the cost of dragging the year slider, so each
    // feature keeps its own, tagged with the projection it was built under.
    const projection = [x0, y0, scale, left, features.length].join(",");

    for (const feature of features) {
        const id = standsFor(feature);
        const value = byId.get(id);
        const fill = colourFor(value);

        if (feature.__projection !== projection) {
            feature.__d = rings(feature)
                .map((ring) =>
                    "M" + ring.map((p) => px(p).map((n) => n.toFixed(1)).join(" ")).join("L") + "Z")
                .join(" ");
            feature.__projection = projection;
        }
        const d = feature.__d;
        // Provinces standing in for a region are drawn edge to edge in its colour: the
        // border between two provinces of the same region is not a border of anything
        // being shown, so it is painted over rather than left to suggest a division.
        // The stroke is in screen pixels, not viewBox units. Zooming shrinks the viewBox,
        // so a plain 0.6 grew with every wheel click until the borders were fat black
        // bands swallowing the districts between them.
        svg += '<path class="area" data-area="' + (id || "") + '" d="' + d +
               '" fill="' + fill + '" vector-effect="non-scaling-stroke" stroke="' +
               (rolls ? fill : token("--bg-card")) + '" stroke-width="0.6" data-name="' +
               (rolls ? nameFor.get(id) || feature.properties.name_tr
                      : feature.properties.name_tr) +
               '" data-value="' +
               (value === undefined ? "veri yok" : fmt(value)) + '" data-colour="' + fill + '"/>';
    }
    svg += "</svg>";
    hover = {kind: "shape"};

    // Two separate questions, so two labelled pairs rather than four bare chips: how the
    // colour is spread across the range, and what range the ends of the ramp stand for.
    const ramp =
        "<span>Renk sınıfları</span>" +
        "<button class='chip" + (state.scale !== "equal" ? " on" : "") +
        "' data-scale='quantile' title='Her renkte kabaca eşit sayıda alan. İstanbul gibi aykırı bir değer varken haritayı okunur tutan bölme budur.'>Her renkte eşit sayıda alan</button>" +
        "<button class='chip" + (state.scale === "equal" ? " on" : "") +
        "' data-scale='equal' title='Aralık eşit genişlikte bölünür. Sayının kendisi okunur ama aykırı bir değer varken alanların çoğu tek renge yığılır.'>Eşit genişlikte aralıklar</button>" +
        "<button class='chip" + (state.reverse ? " on" : "") +
        "' data-reverse='1' title='Rengin yönünü çevirir: düşük değer koyu yerine parlak olur. Düşüşün kendisi haber olduğunda okunması kolaylaşır.'>Rengi ters çevir</button>";

    const scaleToggle = values.length
        ? "<span class='spacer'></span>" + ramp + "<span>Renk aralığı</span>" +
          "<button class='chip" + (state.scaleSpan === "fixed" ? " on" : "") +
          "' data-span='fixed' title='Uçlar bütün yıllara göre sabit kalır, böylece yıllar oynatılınca rengin değişmesi gerçek değişimi gösterir.'>Bütün yıllara sabit</button>" +
          "<button class='chip" + (state.scaleSpan !== "fixed" ? " on" : "") +
          "' data-span='year' title='Uçlar her yıl yeniden hesaplanır, yani renk o yılın kendi sıralamasını gösterir.'>Her yıla yeniden</button>" +
          "<button class='chip' id='map-fit' title='Tekerlek yakınlaştırır, sürükleme kaydırır'>⤢ Sığdır</button>"
        : "";

    const head = "<div class='map-head'>" +
        // The district controls belong to indicators that have districts. Median age is
        // published per province only, so offering to open one is offering nothing.
        (opened
            ? "<button class='link-inline' id='map-back'>← Türkiye</button><span>" +
              opened.name_tr + " · " + features.length + " ilçe" +
              (values.length ? "" : " · ilçe düzeyinde veri yok, sınırlar gösteriliyor") + "</span>"
            : "<span>" + (LEVEL_LABELS[state.level] || state.level) + " düzeyinde · " +
              drawnIds.size + " alan" +
              (OFFERED_LEVELS.includes("district") &&
               (state.indicator.levels || []).includes("district") && state.level !== "district"
                  ? " · bir alana tıklayınca ilçeleri açılır"
                  : "") +
              "</span>") +
        scaleToggle + "</div>";

    return head + wrapPlot(svg) +
           // The gap swatch counts *areas*, not shapes: seven regions drawn as eighty-one
           // provinces are not seventy-four missing values.
           (values.length
               ? legend(low, high, edges, colours, values.length < drawnIds.size)
               : "") +
           // Off the ids actually drawn, so a region map summarises seven regions rather
           // than the eighty-one province shapes they were painted from.
           summaryLine([...drawnIds].map((id) => ({
               name: nameFor.get(id) || nameOf(id),
               value: byId.get(id),
           })));
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

    // Enough decimals to tell the classes apart. At the indicator's own precision a map
    // of district shares of the country printed six classes all reading "0,0–0,0": the
    // numbers really are that small, so the legend follows the data rather than the
    // indicator's usual rounding.
    let places = decimals();
    while (
        places < 6 &&
        bounds.some((v, i) => i && v.toFixed(places) === bounds[i - 1].toFixed(places))
    ) {
        places += 1;
    }
    const show = (v) => formatter(places).format(v);

    const swatches = colours
        .map((colour, i) =>
            "<span class='key'>" +
            "<span class='chip-colour' style='background:" + colour + "'></span>" +
            "<span class='key-range'>" + show(bounds[i]) +
            (i === colours.length - 1 ? "+" : "–" + show(bounds[i + 1])) +
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

/** Two indicators against each other, one point per area, at the year on the slider. */
function scatter() {
    const other = versusIndicator();
    if (!other) {
        return empty(
            "Yatay eksene bir gösterge seçin.",
            "Üstteki “Karşılaştırılan” kutusundan"
        );
    }

    // The picker is part of every answer this view gives, the empty ones included: it is
    // the only way back to a pairing that works, and returning it only on success left
    // the reader stranded on a blank frame with no control on it.
    const head = (note) =>
        "<div class='map-head'><span>" + note +
        "</span><span class='spacer'></span>" + scaleTypeToggle() +
        "<span>Karşılaştırılan</span>" +
        "<select id='versus'>" + versusOffered()
            .map((i) => "<option value='" + i.id + "'" +
                        (i.id === state.versus ? " selected" : "") + ">" + i.label + "</option>")
            .join("") +
        "</select></div>";

    const year = state.year;
    const xs = versusAt(state.level, year);
    if (!xs.size) {
        // Distinguish the two ways this comes up empty. A breakdown with no whole is not
        // a gap in the data — it is a measure that was never published for everybody, and
        // saying "değer yok" about it sends the reader looking for a missing file.
        const dims = other.dims || [];
        return head("değer yok") + (dims.length && !other.additive
            ? empty(
                  other.label + " yalnızca " + dims.map(dimLabel).join(" ve ") +
                      " kırılımıyla yayımlanıyor; toplamı olmadan yatay eksene konamaz.",
                  "Toplamı olan bir gösterge seçin"
              )
            : empty(other.label + " için " + year + " yılında bu düzeyde değer yok."));
    }

    // The y axis is the chosen indicator, read exactly as every other view reads it — the
    // breakdown, the share and the derivation all still apply.
    const points = [];
    for (const row of derivedSlice(state.level)) {
        if (row.year !== year) {
            continue;
        }
        const x = xs.get(row.area_id);
        if (!Number.isFinite(x) || !Number.isFinite(row.value)) {
            continue;
        }
        points.push({id: row.area_id, name: nameOf(row.area_id), x, y: row.value});
    }
    if (!points.length) {
        return head("ortak alan yok") + empty("İki göstergenin ortak alanı yok.");
    }

    // The x value belongs to the other indicator, so it is printed with *its* precision.
    // Borrowing the chosen indicator's rounded a fertility rate of 1,6 to "2".
    const fmtX = formatter(other.decimals ?? 2).format;

    // Room at the top for the y axis name. Written above the plot rather than beside it:
    // at the old height it sat on the same line as the topmost tick and the two printed
    // over each other ("↑ Nüfus200,0").
    const L = 88, R = 24, T = 40, B = 46;
    // Both axes follow the same chip. Population on one of them is exactly the case a log
    // scale is for, and a scatter with one axis logged and the other not is a chart whose
    // shape means something different in each direction.
    const xScale = axisScale(points.map((p) => p.x), {log: logScale(), fromZero: false});
    const yScale = axisScale(points.map((p) => p.y), {log: logScale(), fromZero: state.axis === "zero"});
    if (!xScale || !yScale) {
        return head("çizilemedi") +
               empty("Logaritmik eksende çizilecek pozitif değer yok.");
    }
    const plotted = points.filter((p) => xScale.plots(p.x) && yScale.plots(p.y));
    if (!plotted.length) {
        return head("çizilemedi") + empty("Bu eksende çizilebilen nokta kalmadı.");
    }

    const px = (v) => L + xScale.at(v) * (PLOT_W - L - R);
    const py = (v) => T + (1 - yScale.at(v)) * (PLOT_H - T - B);

    let svg = '<svg class="plot" viewBox="0 0 ' + PLOT_W + " " + PLOT_H + '" role="img">';

    for (const v of yScale.ticks) {
        svg += '<line x1="' + L + '" x2="' + (PLOT_W - R) + '" y1="' + py(v) + '" y2="' + py(v) +
               '" stroke="' + token("--stroke-divider") + '" stroke-dasharray="4 5"/>' +
               axisText(L - 12, py(v) + 4,
                        yScale.log ? tickText(v, decimals()) : fmt(v), "end");
    }
    for (const v of xScale.ticks) {
        svg += '<line y1="' + T + '" y2="' + (PLOT_H - B) + '" x1="' + px(v) + '" x2="' + px(v) +
               '" stroke="' + token("--stroke-divider") + '" stroke-dasharray="4 5"/>' +
               axisText(px(v), PLOT_H - B + 18,
                        xScale.log ? tickText(v, other.decimals ?? 2) : fmtX(v), "middle");
    }

    // The chosen areas are the ones the reader is following, so they keep their colour and
    // their name; the rest of the country stays as context rather than being thrown away.
    // A scatter of five points cannot show a relationship — the cloud is the point.
    const chosen = new Set(drawn());
    const named = plotted.filter((p) => chosen.has(p.id));

    for (const point of plotted) {
        const on = chosen.has(point.id);
        svg += '<circle cx="' + px(point.x).toFixed(1) + '" cy="' + py(point.y).toFixed(1) +
               '" r="' + (on ? 5 : 3) + '" fill="' + (on ? colourOf(point.id) : token("--text-tertiary")) +
               '" opacity="' + (on ? 1 : 0.35) + '" data-colour="' +
               (on ? colourOf(point.id) : token("--text-tertiary")) + '" data-name="' + point.name +
               '" data-value="' + fmtX(point.x) + " / " + fmt(point.y) + '"/>';
    }
    if (named.length <= LABEL_LIMIT) {
        for (const point of named) {
            svg += '<text class="legend-label" x="' + (px(point.x) + 8) + '" y="' + (py(point.y) + 4) +
                   '" fill="' + colourOf(point.id) + '">' + point.name + "</text>";
        }
    }

    svg += axisText(PLOT_W - R, PLOT_H - 8, other.label + " →", "end") +
           '<text class="legend-label" x="8" y="16" fill="' + token("--text-tertiary") +
           '">↑ ' + state.indicator.label + (unitLabel() ? " (" + unitLabel() + ")" : "") +
           "</text>";

    hover = {kind: "shape"};

    const missing = points.length - plotted.length;
    return head(plotted.length + " alan · " + year +
                (missing ? " · " + missing + " nokta bu ölçekte çizilemedi" : "")) +
           wrapPlot(svg + "</svg>");
}

const RENDERERS = {line: lineChart, bar: barChart, table, pyramid, map, scatter};

// endregion

// region Reading the screen
//
// What the number on screen actually is, in words, under the view that drew it.
//
// The definitions used to carry this: every trap, every denominator, every caveat, in one
// paragraph above the chart. It was unreadable for two reasons. It sat *before* the thing
// it explained, and it described every setting at once — including the eleven the reader
// had not chosen. The paragraph for kütük nüfusu explained "il dışında" to a reader
// looking at "tümü".
//
// So the definition above the chart is one or two sentences about the measure, and this
// block, below the view, is assembled from the settings that are actually on: one entry
// per choice, each with a worked example off the rows now in hand. Every combination is
// covered because the combination is never written down — the clauses are, and they
// compose. Nothing here is a fixed string with a number in it; if the arithmetic below
// disagrees with the chart, the chart is what changed.

/** Run `fn` with parts of the state temporarily replaced, then put it back.
 *
 *  This is how the examples reach the numbers *behind* the current reading: the raw
 *  measurement under a percentage, the undifferenced series under a year-on-year change.
 *  Safe because every memo key names the state it depends on (see `choices`), so the
 *  borrowed reading is cached under its own key and neither answer overwrites the other. */
function asIf(patch, fn) {
    const saved = {};
    for (const key of Object.keys(patch)) {
        saved[key] = state[key];
        state[key] = patch[key];
    }
    try {
        return fn();
    } finally {
        Object.assign(state, saved);
    }
}

function esc(text) {
    return String(text).replace(/[&<>]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"})[c]);
}

/** A number in the reader's own format, at the precision the screen is using. */
function say(value, places) {
    if (!Number.isFinite(value)) {
        return "—";
    }
    return formatter(places === undefined ? decimals() : places).format(value);
}

/** The area the examples are worked on: the first one actually drawn.
 *
 *  One area, named, all the way through the block. Worked on whichever area happened to
 *  be largest per clause, the examples would each be arithmetically right and together
 *  read as one calculation that does not add up. */
function exampleArea() {
    const drawnNow = drawn();
    if (drawnNow.length) {
        return drawnNow[0];
    }
    return state.selection[0] || null;
}

/** The year the examples stand on. The views that draw one year use that year; the line
 *  and the table draw all of them, and there the last year is the one a reader looks at
 *  first. */
function exampleYear() {
    const span = years();
    const perYear = state.view !== "line" && state.view !== "table";
    return perYear ? state.year : span[span.length - 1];
}

/** The value now on screen for the example area and year, derivation and share included.
 *  Read from the same slice the view drew, not recomputed. */
function exampleValue() {
    const area = exampleArea();
    if (!area) {
        return undefined;
    }
    return seriesFor(area).find((p) => p.year === exampleYear())?.value;
}

/** The raw measurement under the example: no share, no derivation. */
function exampleRaw(patch = {}) {
    const area = exampleArea();
    if (!area) {
        return undefined;
    }
    return asIf({share: "", derivation: "", ...patch}, () => {
        const rows = byArea(levelOfArea(area)).get(area) || [];
        return rows.find((r) => r.year === exampleYear())?.value;
    });
}

/** The raw unit's precision — the share's two decimals belong to the percentage, not to
 *  the count underneath it. */
function rawPlaces() {
    return state.indicator.decimals ?? 0;
}

function entry(term, body, example) {
    return (
        "<div class='reading-item'><dt>" + esc(term) + "</dt><dd>" + body +
        (example ? "<span class='reading-eg'>Örnek: " + example + "</span>" : "") +
        "</dd></div>"
    );
}

/** What one number on screen is: which area, which year, which unit. */
function readingMeasure() {
    const area = exampleArea();
    const value = exampleValue();
    // "bir türkiye ve bir yıl" — the country is one area, not one of a kind, and the
    // lower-cased label reads as a typo. Named separately rather than left to the
    // sentence that works for the other five levels.
    const level = effectiveLevel();
    const where =
        level === "country"
            ? "Ekrandaki her sayı Türkiye'nin bir yılı içindir"
            : "Ekrandaki her sayı bir " +
              esc((LEVEL_LABELS[level] || "alan").toLocaleLowerCase("tr")) +
              " ve bir yıl içindir";
    const body =
        where + "; birimi <b>" + esc(unitLabel()) + "</b>. " +
        (state.indicator.additive
            ? "Sayılabilir bir büyüklük, yani alanlar ve kırılım değerleri toplanabilir."
            : "Toplanamaz bir büyüklük — bir oran ya da bir konum — o yüzden iki alanın " +
              "değeri toplanmaz, ancak karşılaştırılır.");
    const example =
        area && Number.isFinite(value)
            ? "<b>" + esc(nameOf(area)) + "</b>, " + exampleYear() + ": <b>" +
              esc(say(value)) + "</b> " + esc(unitLabel())
            : null;
    return entry("Ölçü — " + state.indicator.label, body, example);
}

/** Which areas the screen holds, and whether the source published them or we added them
 *  up. A summed level is not a published one and the reader is told which they are on. */
function readingLevel() {
    const level = effectiveLevel();
    const count = new Set(slice(level).map((r) => r.area_id)).size;
    const flags = new Set(slice(level).map((r) => r.quality_flag));
    const body =
        "Satırlar <b>" + esc(LEVEL_LABELS[level] || level) + "</b> düzeyinde: " +
        count + " alan" +
        (state.focus ? ", " + esc(nameOf(state.focus)) + " içine girilmiş hâlde" : "") +
        ". " +
        (flags.has("estimated")
            ? "Bir kısmı <b>tahmin</b> işaretli — kaynakta yayımlanmadı, hesaplandı; " +
              "künyedeki sarı rozet bunu söylüyor."
            : "Hepsi kaynağın yayımladığı ölçüm.");
    return entry("Düzey", body, null);
}

/** The example area's raw value at each value of one breakdown, every other choice held.
 *
 *  The same filter `sliceRaw` applies, for one area and one year: the numbers printed
 *  here are the ones the chart added together, not a second reading of the file. */
function examplePartsOf(dim, values) {
    const area = exampleArea();
    const year = exampleYear();
    const others = (state.indicator.dims || []).filter((d) => d !== dim);
    const sums = new Map();
    for (const row of rowsAt(levelOfArea(area))) {
        // Id or name: the selection is keyed by id, but `byArea` indexes both and a
        // shared link can carry either, so this matches the way that lookup does.
        if ((row.area_id !== area && row.area !== area) || row.year !== year) {
            continue;
        }
        if (
            !others.every(
                (d) =>
                    state.dims[d] === TOTAL ||
                    String(groupValue(d, row[d])) === String(state.dims[d])
            )
        ) {
            continue;
        }
        const key = String(groupValue(dim, row[dim]));
        sums.set(key, (sums.get(key) || 0) + row.value);
    }
    return values
        .map((value) => ({label: dimValue(dim, value), value: sums.get(String(value))}))
        .filter((p) => Number.isFinite(p.value));
}

/** One entry per breakdown the indicator carries: what was kept, what was summed away,
 *  and the arithmetic of the sum where a sum happened. */
function readingDims() {
    const area = exampleArea();
    const out = [];
    for (const dim of state.indicator.dims || []) {
        const values = valuesOf(dim);
        if (values.length < 2) {
            continue;
        }
        const chosen = state.dims[dim];
        const group = grouping(dim);
        const notes = [];

        if (chosen === TOTAL) {
            notes.push(
                "<b>Tümü (topla)</b> seçili: " + values.length + " değerin (" +
                esc(values.map((v) => dimValue(dim, v)).join(", ")) +
                ") satırları tek sayıya toplanıyor."
            );
        } else {
            notes.push(
                "Yalnızca <b>" + esc(dimValue(dim, chosen)) + "</b> satırları sayılıyor; " +
                "geri kalan " + (values.length - 1) +
                " değer ekranda hiç yok — eksik değil, sorulmamış."
            );
        }
        if (group) {
            notes.push(
                "Değerler <b>" + esc(group.label) + "</b> okumasıyla gruplanmış: " +
                "ham değerler önce gruplara toplanıyor, sonra seçim onlara uygulanıyor."
            );
        }
        if (state.split === dim) {
            notes.push(
                "Bu kırılım <b>serilere ayrılmış</b>: her alan için tek çizgi yerine " +
                values.length + " çizgi çiziliyor, seçim kutusu devre dışı."
            );
        }

        // The arithmetic of the choice, on the example area: the parts and the total, so
        // "toplanıyor" is a claim the reader can check rather than a word.
        //
        // One pass over the area's own rows rather than one slice per value. Marital
        // status has sixteen age bands and a slice of it is 184.000 rows; asking for a
        // slice per value put sixteen of them through the memo on every draw, which is
        // the whole table rebuilt to print four numbers.
        let example = null;
        if (area) {
            const parts = examplePartsOf(dim, values);
            if (parts.length) {
                const total = parts.reduce((sum, p) => sum + p.value, 0);
                const shown = parts.slice(0, 4);
                example =
                    esc(nameOf(area)) + " " + exampleYear() + " — " +
                    shown
                        .map(
                            (p) =>
                                esc(p.label) + ": " +
                                esc(say(p.value, rawPlaces()))
                        )
                        .join(" · ") +
                    (parts.length > shown.length ? " · …" : "") +
                    (chosen === TOTAL && state.indicator.additive
                        ? " → toplam <b>" + esc(say(total, rawPlaces())) + "</b>"
                        : "");
            }
        }
        out.push(entry("Kırılım — " + dimLabel(dim), notes.join(" "), example));
    }
    return out.join("");
}

//: What each derivation does, and how to read its sign. The formula is written the way
//: the code computes it, so the two can be checked against each other.
const DERIVATION_READING = {
    index: {
        what: "Her seri kendi ilk yılına bölünüp 100 ile çarpılıyor.",
        formula: "(değer ÷ ilk yılın değeri) × 100",
        reads: "100 ilk yıl demek; 120 ilk yıla göre beşte bir artmış demek. " +
               "Büyüklükleri değil, hareketleri karşılaştırır — İstanbul ile Tunceli " +
               "aynı çizgiden başlar.",
        drops: "",
    },
    yoy: {
        what: "Bir önceki yıla göre yüzde değişim.",
        formula: "((bu yıl − geçen yıl) ÷ geçen yıl) × 100",
        reads: "Tek yılın hareketi. İyi ya da kötü bir yıl bütün resmi değiştirir; " +
               "uzun dönem için bileşik büyüme daha sağlam.",
        drops: "İlk yılın öncesi yok, o yüzden çizilmiyor — sıfır değil, yok.",
    },
    diff: {
        what: "Bir önceki yıla göre fark, ölçünün kendi biriminde.",
        formula: "bu yıl − geçen yıl",
        reads: "Yüzde küçük bir tabanda büyük görünür; bu, kaç kişi olduğunu söyler.",
        drops: "İlk yıl çizilmiyor.",
    },
    total_change: {
        what: "İlk yıldan bu yana toplam yüzde değişim.",
        formula: "((değer − ilk yıl) ÷ ilk yıl) × 100",
        reads: "Endeksin sıfır merkezli hâli: 100 yerine 0 başlangıç, −51,4 yarıdan " +
               "fazla düşmüş demek. 'En çok nerede düştü' sorusunun sıralanacağı sütun.",
        drops: "",
    },
    total_diff: {
        what: "İlk yıldan bu yana toplam fark, ölçünün kendi biriminde.",
        formula: "değer − ilk yılın değeri",
        reads: "Ortanca yaşın 34'ten 36'ya çıkması '+2 yaş'tır; buna '%5,9' demek " +
               "kimsenin sormadığı bir aritmetiktir.",
        drops: "",
    },
    cagr: {
        what: "İlk yıldan o yıla kadar, yılda ortalama bileşik büyüme.",
        formula: "((değer ÷ ilk yıl)^(1 ÷ geçen yıl sayısı) − 1) × 100",
        reads: "'Ne hızla büyüyor' sorusunun tek yıla takılmayan cevabı. Bileşik: " +
               "18 yılda %20, yılda %1,0'dır — 20 ÷ 18 = 1,1 değil.",
        drops: "İlk yılın kendi tabanı olduğu için oranı yok, çizilmiyor.",
    },
    ma3: {
        what: "Üç yıllık ortalanmış hareketli ortalama.",
        formula: "(önceki yıl + bu yıl + sonraki yıl) ÷ 3",
        reads: "Küçük alanlar yıldan yıla zıplar ve zıplamanın çoğu gürültüdür; bu " +
               "onu yatıştırır, eğilimi bırakır.",
        drops: "İlk ve son yılın bir komşusu eksik, o yüzden çizilmiyor.",
    },
};

/** The derivation in words, with its own arithmetic done on the example area. */
function readingDerivation() {
    const id = state.derivation;
    if (!id) {
        return entry(
            "Türetme — Ölçüm (ham)",
            "Türetme kapalı: ekrandaki sayı ölçünün kendisi, zamana göre bir " +
            "dönüştürmeden geçmiyor.",
            null
        );
    }
    const reading = DERIVATION_READING[id];
    const label = meta.derivations?.[id]?.label || id;
    if (!reading) {
        return entry("Türetme — " + label, "Seri zamana göre türetiliyor.", null);
    }

    // The example is the code's own arithmetic, run on the undivided series: the numbers
    // that go into the formula, and the number that comes out — which is the number on
    // screen, not a second one computed here.
    let example = null;
    const area = exampleArea();
    if (area) {
        const points = asIf({derivation: ""}, () => seriesFor(area)).filter((p) =>
            Number.isFinite(p.value)
        );
        const year = exampleYear();
        const here = points.find((p) => p.year === year);
        const first = points[0];
        const previous = points[points.findIndex((p) => p.year === year) - 1];
        const out = seriesFor(area).find((p) => p.year === year)?.value;
        const places = state.share ? 2 : rawPlaces();
        const parts =
            id === "yoy" || id === "diff"
                ? previous && here && [previous, here]
                : id === "ma3"
                  ? here && points.slice(Math.max(0, points.indexOf(here) - 1), points.indexOf(here) + 2)
                  : first && here && [first, here];
        if (parts && parts.length && Number.isFinite(out)) {
            example =
                esc(nameOf(area)) + " — " +
                parts.map((p) => p.year + ": " + esc(say(p.value, places))).join(", ") +
                " → <b>" + esc(say(out)) + "</b> " + esc(unitLabel());
        }
    }

    return entry(
        "Türetme — " + label,
        reading.what + " <span class='reading-formula'>" + esc(reading.formula) +
            "</span> " + reading.reads + (reading.drops ? " " + reading.drops : ""),
        example
    );
}

/** The share mode: which total the number was divided by, said in full, with the
 *  division actually carried out on the example area. */
function readingShare() {
    const area = exampleArea();
    const year = exampleYear();
    const level = effectiveLevel();
    const within = shareWithin();
    const top = exampleRaw();
    let body;
    let bottom;

    if (!state.share) {
        body =
            "Bölme yok: ekrandaki sayı mutlak büyüklüğün kendisi. Büyük alanlar büyük " +
            "sayılar verir, o yüzden 'nerede yoğun' sorusu için bir yüzde kipine geçmek " +
            "gerekir.";
    } else if (state.share === "population") {
        body =
            "Payda <b>başka bir gösterge</b>: aynı alanın ve yılın nüfusu. Diğer " +
            "kiplerden farkı bu — ölçüyü kendi bir parçasına değil, o yerde yaşayan " +
            "insan sayısına oranlıyor.";
        bottom = area && populationTotals(level).get(area + "|" + year);
    } else if (within) {
        body =
            "Payda, <b>" + esc(dimLabel(within)) + "</b> kırılımının bu alandaki " +
            "toplamı: diğer bütün seçimler yerinde tutulup yalnızca bu kırılımın " +
            "değerleri toplanıyor. '65+ kadınlarda dul olanların oranı' bu kiptir; " +
            "alanın kendi toplamına bölmek onu 'nüfusun içinde 65+ dul kadın' " +
            "sorusuna çevirirdi, ki başka bir sayıdır.";
        bottom = area && withinTotals(level, within).get(area + "|" + year);
    } else if (state.share === "own") {
        body =
            "Payda, <b>alanın kendi toplamı</b>: kırılımın bütün değerleri toplanmış " +
            "hâli. Bileşimi verir — bu yerin yüzde kaçı seçili değer. Alanlar arası " +
            "büyüklük farkını temizler.";
        bottom = area && wholeOf(level).get(area + "|" + year);
    } else {
        body =
            "Payda, <b>o yılın ülke toplamı</b>: ekrandaki bütün alanların aynı yıldaki " +
            "değerlerinin toplamı. Dağılımı verir — bu büyüklüğün yüzde kaçı burada. " +
            "Sütunlar 100'e tamamlanır.";
        const rows = asIf({share: ""}, () => slice(level));
        bottom = rows
            .filter((r) => r.year === year)
            .reduce((sum, r) => sum + (Number.isFinite(r.value) ? r.value : 0), 0);
    }

    let example = null;
    if (state.share && area && Number.isFinite(top) && Number.isFinite(bottom) && bottom) {
        example =
            esc(nameOf(area)) + " " + year + ": " + esc(say(top, rawPlaces())) + " ÷ " +
            esc(say(bottom, rawPlaces())) + " × 100 = <b>" +
            esc(say((top / bottom) * 100, 2)) + "</b>%";
    }

    const label = state.share ? unitLabel() : "Mutlak sayı";
    return entry("Kip — " + label, body, example);
}

//: What each view is for. Short: the reader is looking at it, so this says what it is
//: good at, not what it looks like.
const VIEW_READING = {
    table: "Her alan bir satır. Sıralanabilir olduğu için 'en yüksek/en düşük' " +
           "sorularının cevabı burada, haritada değil.",
    map: "Renk, seçili yılın değeri. Renk sınıfları ölçek kutusundan geliyor: " +
         "'nicelik' her sınıfa yakın sayıda alan koyar, 'eşit aralık' değer " +
         "aralığını eşit böler — aynı veri, iki farklı harita.",
    line: "Yıllar yatay eksende, seçili her alan bir çizgi. Zaman içinde ne olduğu " +
          "buradan okunur; tek bir yılın karşılaştırması için sütun daha nettir.",
    bar: "Seçili yılın değerleri, alan alan. Sıra büyüklüğe göre, o yüzden " +
         "karşılaştırma doğrudan.",
    pyramid: "Yaş grupları dikey, cinsiyet iki yana. Türetme burada kapalı: eksen " +
             "yaş bantları, yıllar değil.",
    scatter: "İki gösterge, aynı alanlar. Yatay eksendeki gösterge ayrıca seçiliyor; " +
             "nokta bir alanın o yıldaki iki değeri.",
};

function readingView() {
    return entry(
        "Görünüm — " + (VIEW_LABELS[state.view] || state.view).replace(/^\S+\s/, ""),
        VIEW_READING[state.view] || "",
        null
    );
}

function drawReading() {
    const blocks =
        readingMeasure() +
        readingDims() +
        readingDerivation() +
        readingShare() +
        readingLevel() +
        readingView();
    $("reading").innerHTML =
        "<h3>Bu ekranda ne var</h3><dl class='reading-list'>" + blocks + "</dl>";
}

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

    // A split belongs to the views that draw series. Dropped rather than carried silently
    // into a map, where it would change nothing and then reappear on the way back looking
    // like the page had remembered something the reader did not ask for.
    if (state.split && !SPLIT_VIEWS.includes(state.view)) {
        state.split = "";
    }

    // Only the pyramid cannot carry a derivation — see derivationControl. Everywhere else
    // the value drawn is the derived one, so switching views keeps the reader's choice
    // instead of silently resetting it to the raw measurement.
    if (derivation()?.needs_span && state.view === "pyramid") {
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
    // The district map needs eighty-one boundary files. They are fetched once, on the
    // first draw that actually needs them, and the frame says so meanwhile rather than
    // going blank for several seconds.
    if (state.view === "map" && state.level === "district" && !districtFeatures.length) {
        $("view").innerHTML = empty("İlçe sınırları yükleniyor…");
        allDistricts().then((features) => {
            districtFeatures = features;
            render();
        });
        return;
    }

    // Reading against the population means a second dataset, fetched the first time it is
    // actually asked for rather than on every visit.
    if (state.share === "population" && !versusRows.has(AGAINST)) {
        $("view").innerHTML = empty("Nüfus yükleniyor…");
        ensurePopulation().then(render);
        return;
    }

    // The second indicator is a second file. Same treatment as the district boundaries:
    // fetched on the first draw that needs it, with the frame saying so meanwhile.
    if (state.view === "scatter") {
        const offered = versusOffered();
        if (!offered.some((i) => i.id === state.versus)) {
            state.versus = offered[0]?.id || "";
        }
        if (state.versus && !versusRows.has(state.versus)) {
            $("view").innerHTML = empty(versusIndicator().label + " yükleniyor…");
            ensureVersus().then(render);
            return;
        }
    }

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

    drawReading();
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
        s: state.share || "",
        a: state.selection.join("~"),
        ...Object.fromEntries(Object.entries(state.dims).map(([k, v]) => ["d." + k, v])),
    });
    history.replaceState(null, "", "#" + params);
}

function readHash() {
    return new URLSearchParams(location.hash.slice(1));
}

function downloadShown() {
    // Per area, at that area's own level: the selection may hold more than one (K18), and
    // taking the slice at the box's level alone would quietly drop the rest from the file.
    const rows = drawn().flatMap((id) =>
        slice(levelOfArea(id)).filter((r) => r.area_id === id)
    );
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
    state.grouping = {};
    attached.clear();
    fineRows = [];
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
    resetMapView();

    const levels = levelsInData();
    state.level = levels.includes(state.level) ? state.level : levels[0];
    await ensureLevel(state.level);

    // Sharing carries over between indicators where it still means something, and is
    // dropped where it does not — a share of a fertility rate is not a number. Against
    // the population is its own question and survives on its own terms: an indicator with
    // no breakdown can still be read as a share of the people who live there.
    state.share = shareStillMeans(state.share);

    state.dims = {};
    for (const dim of indicator.dims || []) {
        const values = valuesOf(dim);
        // Default to the whole where there is one — summed for a count, and now also
        // where a total is *stored* rather than summed: the average age at marriage has
        // a real "Toplam" row (see marriage_age_total) and opening on "Kadın" made the
        // page look like it was about women. Otherwise the first value, and a chart of
        // one arbitrary age band is a lie by omission either way.
        state.dims[dim] =
            indicator.additive || values.includes(TOTAL) ? TOTAL : values[0];
    }

    const span = years();
    state.year = span[span.length - 1];
    if (!(indicator.views || []).includes(state.view)) {
        state.view = indicator.views[0];
    }

    // Same rule as sharing, for the same reason: a derivation that divides by the series
    // is dropped when the new indicator's series goes to zero or below, rather than
    // carried over into an empty chart.
    if (NEEDS_POSITIVE.includes(state.derivation) && everNegative()) {
        state.derivation = "";
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
        // The selection survives the move. Changing the box used to wipe it and seed the
        // new level's five largest, which made "Türkiye against Bursa against one of
        // Bursa's districts" impossible to even ask for: every step of building it threw
        // away the step before. Now the box says which list is on offer and the chosen
        // block keeps what is chosen, tagged with where each one came from. Seeding is
        // still there for the case it was written for — nothing chosen, blank page.
        if (!state.selection.length) {
            seedSelection();
        }
        render();
    };

    $("dims").onchange = async (ev) => {
        // A dropdown identifies itself by id; a group of buttons cannot, since an id may
        // not repeat across its options, so those carry `data-role` instead. Read as one
        // thing here, and neither the handler nor the state below knows which shape the
        // reader was given.
        const role = ev.target.id || ev.target.dataset.role || "";
        if (role === "indicator") {
            if (await useIndicator(ev.target.value)) {
                render();
            }
            return;
        }
        if (role === "share") {
            state.share = ev.target.value;
            render();
            return;
        }
        if (role === "split") {
            state.split = ev.target.value;
            render();
            return;
        }
        if (role === "derivation") {
            state.derivation = ev.target.value;
            render();
            return;
        }
        if (ev.target.dataset.grouping) {
            const dim = ev.target.dataset.grouping;
            const was = state.grouping[dim];
            state.grouping = {...state.grouping, [dim]: ev.target.value};
            // Only a change of *resolution* invalidates: it swaps the rows themselves, so
            // the level buckets and everything counted off them go stale. An ordinary
            // grouping changes nothing but the slice, and the slice keys already name it
            // — throwing the whole working set away for that cost a redraw twice over.
            // A grouping built off the single years needs them fetched too, and needs the
            // buckets thrown away on the way out again — the rows underneath the answer
            // change in both directions.
            const fineNow = meta.groupings?.[ev.target.value]?.needs_fine;
            const fineWas = meta.groupings?.[was]?.needs_fine;
            if (ev.target.value === FINE || was === FINE || fineNow || fineWas) {
                await ensureFine(dim);
                invalidate();
            }
            // The old choice named a band that may not be a group any more.
            state.dims[dim] = state.indicator.additive ? TOTAL : valuesOf(dim)[0];
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
    // The scatter's x-axis picker lives in the chart's own head rather than the breakdown
    // strip: it belongs to that one view, and the strip is already the busiest control on
    // the page. So the change handler has to sit on the frame the view is drawn into.
    $("view").onchange = async (ev) => {
        if (ev.target.id !== "versus") {
            return;
        }
        state.versus = ev.target.value;
        await ensureVersus();
        render();
    };

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

        if (ev.target.closest("[data-reverse]")) {
            state.reverse = !state.reverse;
            render();
            return;
        }

        const scaleType = ev.target.closest("[data-scaletype]");
        if (scaleType) {
            state.scaleType = scaleType.dataset.scaletype;
            render();
            return;
        }

        const axis = ev.target.closest("[data-axis]");
        if (axis) {
            state.axis = axis.dataset.axis;
            render();
            return;
        }

        // Clicking the column you are already sorted by turns it around.
        const sorted = ev.target.closest("[data-sort]");
        if (sorted) {
            const column = sorted.dataset.sort;
            state.sort = {
                column,
                descending: state.sort.column === column ? !state.sort.descending
                                                         : column !== "name",
            };
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
        if (!area || state.view !== "map" || state.focus ||
            !OFFERED_LEVELS.includes("district")) {
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
    state.share = shareStillMeans(hash.get("s") || "");
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
