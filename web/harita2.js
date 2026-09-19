// The map: a scope and a level, and nothing else to set.
//
//   scope — where you are looking: Türkiye, a region, a province, a district.
//   level — how finely it is cut inside that scope: regions, provinces, districts,
//           neighbourhoods and villages.
//
// Both are plain selects because the pairs multiply: five levels times a thousand scopes
// is not a row of buttons. The filtering leans on the ids being hierarchical —
// TR-16-006-183945 sits inside TR-16-006 sits inside TR-16 — so a scope is a prefix test
// on the tile's own id and costs nothing at render time.
//
// No basemap: boundaries are the subject here.
"use strict";

const protocol = new pmtiles.Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

const TILES = "../public/tiles";
// Neighbourhoods and villages share one archive and one layer: they are the same kind of
// unit and the source only separates them with a flag, so they are drawn together and
// called what they are.
const LEVELS = {
    ibbs1: { file: "ibbs1", layer: "ibbs1", ad: "İBBS-1 bölgeleri", renk: "#4a7fb5", zoom: [0, 8] },
    ibbs2: { file: "ibbs2", layer: "ibbs2", ad: "İBBS-2 bölgeleri", renk: "#4590ab", zoom: [0, 9] },
    il: { file: "il", layer: "il", ad: "İller", renk: "#429a9c", zoom: [0, 10] },
    ilce: { file: "ilce", layer: "ilce", ad: "İlçeler", renk: "#4f9c84", zoom: [0, 12] },
    mahalle: { file: "mahalle", layer: "mahalle", ad: "Mahalle ve köyler", renk: "#79a05f", zoom: [5, 14] },
};
const ORDER = ["ibbs1", "ibbs2", "il", "ilce", "mahalle"];
// Which levels make sense inside a scope: never the scope's own level or a coarser one.
const INSIDE = {
    tr: ["ibbs1", "ibbs2", "il", "ilce", "mahalle"],
    ibbs1: ["ibbs2", "il", "ilce", "mahalle"],
    ibbs2: ["il", "ilce", "mahalle"],
    il: ["ilce", "mahalle"],
    ilce: ["mahalle"],
};

let kapsam = {};
let scope = { level: "tr", id: "TR" };
let level = "il";

const map = new maplibregl.Map({
    container: "map",
    style: {
        version: 8,
        sources: Object.fromEntries(
            [...new Set(ORDER.map((k) => LEVELS[k].file))].map((file) => [
                file,
                { type: "vector", url: "pmtiles://" + TILES + "/" + file + ".pmtiles", promoteId: "id" },
            ]),
        ),
        layers: [
            { id: "zemin", type: "background", paint: { "background-color": "#0b0c0f" } },
            ...ORDER.flatMap((key) => {
                const spec = LEVELS[key];
                const base = {
                    source: spec.file, "source-layer": spec.layer,
                    minzoom: spec.zoom[0], maxzoom: spec.zoom[1],
                    layout: { visibility: "none" },
                };
                return [
                    {
                        id: key + "-dolgu", type: "fill", ...base,
                        paint: {
                            "fill-color": spec.renk,
                            "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.95, 0.68],
                        },
                    },
                    {
                        id: key + "-kenar", type: "line", ...base,
                        paint: {
                            "line-color": "#eef1f5", "line-opacity": 0.32,
                            "line-width": ["case", ["boolean", ["feature-state", "hover"], false], 1.8, 0.5],
                        },
                    },
                ];
            }),
        ],
    },
    center: [35.3, 39.0], zoom: 5.1, minZoom: 4.2, maxZoom: 13,
    maxBounds: [[19.0, 33.0], [51.0, 45.5]],
    attributionControl: false,
    dragRotate: false,
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

// ---------- filtering ----------

// A scope narrows a level to the shapes whose id starts with the scope's id. Regions are
// the exception: their ids (TR1, TRC2) are not prefixes of a province id, so kapsam.json
// carries their member provinces and the test runs against those.
function filterFor(key) {
    if (scope.level === "tr") return null;
    if (key === "ibbs1" || key === "ibbs2") {
        return scope.level === key ? ["==", ["get", "id"], scope.id] : null;
    }
    if (scope.level === "ibbs1" || scope.level === "ibbs2") {
        const members = (kapsam[scope.id] || {}).iller || [];
        return ["in", ["slice", ["get", "id"], 0, 5], ["literal", members]];
    }
    return ["==", ["slice", ["get", "id"], 0, scope.id.length], scope.id];
}

// The panel is filled as soon as the page has the area list; the map may still be
// fetching its first tiles. Nothing that touches the style runs before it is ready —
// an earlier version hung the whole panel off map.on("load") and a slow tile left the
// page with two empty dropdowns.
let styleReady = false;

function draw() {
    if (!styleReady) return;
    for (const key of ORDER) {
        const on = key === level;
        for (const suffix of ["dolgu", "kenar"]) {
            const id = key + "-" + suffix;
            map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
            if (on) map.setFilter(id, filterFor(key));
        }
    }
    clearHover();
    const area = kapsam[scope.id];
    document.getElementById("note").textContent =
        (area ? area.ad : "Türkiye") + " · " + LEVELS[level].ad;
}

function fitScope() {
    const area = kapsam[scope.id];
    if (!area || !styleReady) return;
    const [w, s, e, n] = area.bbox;
    map.fitBounds([[w, s], [e, n]], { padding: 64, duration: 650 });
}

// ---------- hover ----------

let hovered = null;
function clearHover() {
    if (!hovered) return;
    map.setFeatureState(hovered, { hover: false });
    hovered = null;
}

// ---------- panel ----------

const $ = (id) => document.getElementById(id);
const collator = new Intl.Collator("tr");

function fillLevels() {
    const options = INSIDE[scope.level];
    if (!options.includes(level)) level = options[0];
    $("duzey").innerHTML = options
        .map((k) => '<option value="' + k + '"' + (k === level ? " selected" : "") + ">" + LEVELS[k].ad + "</option>")
        .join("");
}

function fillAreas() {
    const wanted = $("kapsam-duzey").value;
    const select = $("kapsam-alan");
    if (wanted === "tr") {
        select.innerHTML = "<option>Türkiye geneli</option>";
        select.disabled = true;
        return;
    }
    const rows = Object.entries(kapsam)
        .filter(([, a]) => a.duzey === wanted)
        .sort((a, b) => collator.compare(a[1].ad, b[1].ad));
    select.disabled = false;
    // A district's name repeats across provinces — Merkez, Ereğli, Gölbaşı — so the
    // province is printed beside it or the list is a guessing game.
    select.innerHTML = rows
        .map(([id, a]) => {
            const parent = wanted === "ilce" && kapsam[a.ust] ? " — " + kapsam[a.ust].ad : "";
            return '<option value="' + id + '">' + a.ad + parent + "</option>";
        })
        .join("");
}

function readPanel() {
    const wanted = $("kapsam-duzey").value;
    scope = wanted === "tr" ? { level: "tr", id: "TR" } : { level: wanted, id: $("kapsam-alan").value };
    fillLevels();
    level = $("duzey").value;
    draw();
    fitScope();
}

async function boot() {
    kapsam = await fetch("../public/geo/kapsam.json").then((r) => r.json());
    fillAreas();
    fillLevels();
    draw();

    $("kapsam-duzey").addEventListener("change", () => { fillAreas(); readPanel(); });
    $("kapsam-alan").addEventListener("change", readPanel);
    $("duzey").addEventListener("change", () => { level = $("duzey").value; draw(); });
}

function wireMap() {
    styleReady = true;
    draw();
    for (const key of ORDER) {
        map.on("mousemove", key + "-dolgu", (event) => {
            if (key !== level || !event.features.length) return;
            const feature = event.features[0];
            if (hovered && hovered.id === feature.id) return;
            clearHover();
            hovered = { source: LEVELS[key].file, sourceLayer: LEVELS[key].layer, id: feature.id };
            map.setFeatureState(hovered, { hover: true });
            map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", key + "-dolgu", () => {
            if (key !== level) return;
            clearHover();
            map.getCanvas().style.cursor = "";
        });
    }
}

boot();
map.on("load", wireMap);
