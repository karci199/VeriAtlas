"""One-off patch: add the province level to the election map and load its bounds.

Kept as a script rather than typed into the page by hand so the change is reviewable and
repeatable; delete it once the page has settled.
"""

import io
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / "web" / "secim.html"


def replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"bulunamadi: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    s = io.open(PAGE, encoding="utf-8").read()

    s = replace(
        s,
        '    <div class="seg" id="duzey">\n      <button data-v="ilce" class="on">İlçe</button>',
        '    <div class="seg" id="duzey">\n      <button data-v="il">İl</button>\n'
        '      <button data-v="ilce" class="on">İlçe</button>',
        "duzey dugmesi",
    )

    s = replace(
        s,
        '    <select id="oy">\n'
        '      <option value="cb2023t1">Cumhurbaşkanlığı 2023 · 1. tur</option>\n'
        '      <option value="cb2023t2">Cumhurbaşkanlığı 2023 · 2. tur</option>\n'
        '      <option value="cb2018">Cumhurbaşkanlığı 2018</option>\n'
        "    </select></div>",
        '    <select id="oy"></select></div>',
        "secim kutusu",
    )

    s = replace(
        s,
        '      ilce: { type: "vector", url: "pmtiles://../public/tiles/ilce.pmtiles", promoteId: "id" },',
        '      il: { type: "vector", url: "pmtiles://../public/tiles/il.pmtiles", promoteId: "id" },\n'
        '      ilce: { type: "vector", url: "pmtiles://../public/tiles/ilce.pmtiles", promoteId: "id" },',
        "il kaynagi",
    )

    s = replace(
        s,
        '      { id: "ilce-dolgu", type: "fill", source: "ilce", "source-layer": "ilce",\n'
        '        paint: { "fill-color": ["coalesce", ["feature-state", "renk"], "#22252b"] } },',
        '      { id: "il-dolgu", type: "fill", source: "il", "source-layer": "il",\n'
        '        layout: { visibility: "none" },\n'
        '        paint: { "fill-color": ["coalesce", ["feature-state", "renk"], "#22252b"] } },\n'
        '      { id: "ilce-dolgu", type: "fill", source: "ilce", "source-layer": "ilce",\n'
        '        paint: { "fill-color": ["coalesce", ["feature-state", "renk"], "#22252b"] } },',
        "il dolgusu",
    )

    s = replace(
        s,
        '      { id: "vurgu", type: "line", source: "ilce", "source-layer": "ilce",',
        '      { id: "il-kenar", type: "line", source: "il", "source-layer": "il",\n'
        '        paint: { "line-color": "#0f1012", "line-width": 1.1, "line-opacity": 0.9 } },\n'
        '      { id: "vurgu", type: "line", source: "ilce", "source-layer": "ilce",',
        "il kenari",
    )

    s = replace(
        s,
        "const mahalleModu = () => state.duzey === \"mahalle\";\nconst kaynak = () => (mahalleModu() ? \"mahalle\" : \"ilce\");",
        "const mahalleModu = () => state.duzey === \"mahalle\";\n"
        "const ilModu = () => state.duzey === \"il\";\n"
        "const kaynak = () => (mahalleModu() ? \"mahalle\" : ilModu() ? \"il\" : \"ilce\");\n"
        "\n"
        "/** Province results are the districts added up rather than a table of their own:\n"
        " *  one source of truth, and the two levels can never disagree. */\n"
        "function ilTablosu() {\n"
        "  const out = {};\n"
        "  for (const [id, row] of Object.entries(ilce)) {\n"
        "    const ilId = id.slice(0, 5);\n"
        "    const acc = (out[ilId] = out[ilId] || { k: 0, o: 0, g: 0, v: {}, ad: ilAdlari[ilId] || ilId });\n"
        "    acc.k += row.k || 0;\n"
        "    acc.o += row.o || 0;\n"
        "    acc.g += row.g || 0;\n"
        "    for (const [ad, oy] of Object.entries(row.v || {})) acc.v[ad] = (acc.v[ad] || 0) + oy;\n"
        "  }\n"
        "  return out;\n"
        "}",
        "il tablosu",
    )

    s = replace(
        s,
        "function satir(id) {\n  if (!mahalleModu()) return ilce[id];",
        "function satir(id) {\n  if (ilModu()) return ilTablo[id];\n  if (!mahalleModu()) return ilce[id];",
        "satir",
    )

    s = replace(
        s,
        "let ilce = {};        // area_id -> { k, o, g, v, ad }",
        "let ilce = {};        // area_id -> { k, o, g, v, ad }\n"
        "let ilTablo = {};     // TR-XX -> ilçelerin toplamı\n"
        "let ilSinir = {};     // TR-XX -> [batı, güney, doğu, kuzey]",
        "il degiskenleri",
    )

    s = replace(
        s,
        "function kimlikler() {\n  return mahalleModu() ? (ozet ? Object.keys(ozet.y) : []) : Object.keys(ilce);\n}",
        "function kimlikler() {\n"
        "  if (mahalleModu()) return ozet ? Object.keys(ozet.y) : [];\n"
        "  return Object.keys(ilModu() ? ilTablo : ilce);\n}",
        "kimlikler",
    )

    s = replace(
        s,
        "  if (mahalleModu()) mahalleKatmaniEkle();\n"
        "  goster(\"ilce-dolgu\", !mahalleModu());",
        "  if (mahalleModu()) mahalleKatmaniEkle();\n"
        "  goster(\"il-dolgu\", ilModu());\n"
        "  goster(\"ilce-dolgu\", !mahalleModu() && !ilModu());",
        "duzey gorunurluk",
    )

    s = replace(
        s,
        "  goster(\"ilce-kenar\", true);",
        "  goster(\"ilce-kenar\", !ilModu());\n  goster(\"il-kenar\", true);",
        "kenar gorunurluk",
    )

    s = replace(
        s,
        "  durum(mahalleModu()\n"
        "    ? `${fmt.format(ozet ? Object.keys(ozet.y).length : 0)} yerleşim`\n"
        "    : `${fmt.format(Object.keys(ilce).length)} ilçe`);",
        "  durum(mahalleModu()\n"
        "    ? `${fmt.format(ozet ? Object.keys(ozet.y).length : 0)} yerleşim`\n"
        "    : ilModu()\n"
        "      ? `${fmt.format(Object.keys(ilTablo).length)} il`\n"
        "      : `${fmt.format(Object.keys(ilce).length)} ilçe`);",
        "sayac",
    )

    s = replace(
        s,
        '  document.getElementById("oneri").innerHTML =',
        "  ilTablo = ilTablosu();\n  document.getElementById(\"oneri\").innerHTML =",
        "il tablosu kur",
    )

    s = replace(
        s,
        '  for (const layer of ["ilce-dolgu", "mahalle-dolgu"]) {\n    if (map.getLayer(layer)) {',
        '  for (const layer of ["il-dolgu", "ilce-dolgu", "mahalle-dolgu"]) {\n    if (map.getLayer(layer)) {',
        "tema dolgu",
    )
    s = replace(
        s,
        '  for (const layer of ["ilce-kenar", "mahalle-kenar"]) {',
        '  for (const layer of ["il-kenar", "ilce-kenar", "mahalle-kenar"]) {',
        "tema kenar",
    )

    # Province bounds come from a file: querySourceFeatures only sees the tiles already
    # loaded, so flying to a province that is off screen found nothing to fly to.
    s = replace(
        s,
        "  if (state.il) {\n"
        "    const bounds = new maplibregl.LngLatBounds();\n"
        "    for (const f of map.querySourceFeatures(\"ilce\", { sourceLayer: \"ilce\" })) {\n"
        "      if (!(f.properties.id || \"\").startsWith(state.il)) continue;\n"
        "      const walk = (c) => (Array.isArray(c[0]) ? c.forEach(walk) : bounds.extend(c));\n"
        "      walk(f.geometry.coordinates);\n"
        "    }\n"
        "    if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 60, duration: 700 });",
        "  if (state.il) {\n"
        "    const kutu = ilSinir[state.il];\n"
        "    if (kutu) {\n"
        "      map.fitBounds([[kutu[0], kutu[1]], [kutu[2], kutu[3]]], { padding: 60, duration: 700 });\n"
        "    }",
        "il sinirlari",
    )

    s = replace(
        s,
        '  if (!Object.keys(ilAdlari).length) {',
        '  if (!document.getElementById("oy").options.length) {\n'
        '    const secimler = (await jsonYukle("../public/tiles/secimler.json")) || [];\n'
        '    const kutu = document.getElementById("oy");\n'
        "    for (const secim of secimler) {\n"
        '      const option = document.createElement("option");\n'
        "      option.value = secim.anahtar;\n"
        "      option.textContent = secim.ad;\n"
        "      kutu.appendChild(option);\n"
        "    }\n"
        "    if (secimler.length && !secimler.some((v) => v.anahtar === state.oy)) {\n"
        "      state.oy = secimler[0].anahtar;\n"
        "    }\n"
        "    kutu.value = state.oy;\n"
        "  }\n"
        '  if (!Object.keys(ilSinir).length) {\n'
        '    ilSinir = (await jsonYukle("../public/tiles/il-sinirlar.json")) || {};\n'
        "  }\n"
        '  if (!Object.keys(ilAdlari).length) {',
        "secim listesi",
    )

    s = replace(
        s,
        'map.on("mousemove", "ilce-dolgu", (e) => {\n'
        '  map.getCanvas().style.cursor = "pointer";\n'
        "  if (!mahalleModu()) ipucuGoster(e, e.features[0]);\n"
        "});\n"
        'map.on("mouseleave", "ilce-dolgu", () => {\n'
        '  map.getCanvas().style.cursor = "";\n'
        '  ipucu.style.display = "none";\n'
        "});\n"
        'map.on("click", "ilce-dolgu", (e) => { if (!mahalleModu()) alanSec(e.features[0]); });',
        'for (const layer of ["il-dolgu", "ilce-dolgu"]) {\n'
        '  const kendiDuzeyi = layer === "il-dolgu" ? ilModu : () => !ilModu() && !mahalleModu();\n'
        '  map.on("mousemove", layer, (e) => {\n'
        "    if (!kendiDuzeyi()) return;\n"
        '    map.getCanvas().style.cursor = "pointer";\n'
        "    ipucuGoster(e, e.features[0]);\n"
        "  });\n"
        '  map.on("mouseleave", layer, () => {\n'
        '    map.getCanvas().style.cursor = "";\n'
        '    ipucu.style.display = "none";\n'
        "  });\n"
        '  map.on("click", layer, (e) => { if (kendiDuzeyi()) alanSec(e.features[0]); });\n'
        "}",
        "olaylar",
    )

    s = replace(
        s,
        "  } else {\n    map.setFilter(\"vurgu\", [\"==\", \"id\", id]);\n  }\n"
        "  panelAc(id, feature.properties.ad);",
        "  } else if (!ilModu()) {\n    map.setFilter(\"vurgu\", [\"==\", \"id\", id]);\n  }\n"
        "  panelAc(id, ilModu() ? ilAdlari[id] || feature.properties.ad : feature.properties.ad);",
        "alan sec",
    )

    io.open(PAGE, "w", encoding="utf-8", newline="").write(s)
    print("secim.html yamalandi")


if __name__ == "__main__":
    main()
