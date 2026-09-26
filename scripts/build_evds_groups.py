r"""Generate the EVDS catch-all groups: every downloaded non-archive group no adapter reads.

The curated EVDS adapters (`evds_series.py`, `evds_housing.py`, `evds_prices.py`,
`evds_tourism.py`) turn chosen groups into named indicators; the archive adapter stores
the 177 retired groups as they are. This covers the rest the same way as the archive:
one indicator per group (`evds_<group>`), one dimension value per series, unit
"source unit" because units differ inside a group. A group becomes curated later by
adding it to one of those adapters; this script then drops it from the list on its own.

Inputs (`C:\veri-ham\evds`): the downloads `<group>.json` / `<group>-aylik.json` and the
catalogue `_katalog_<date>.json` (`/categories/withDatagroups`) with the category tree
`_kategoriler_<date>.json` (`/categories`).

Left out on purpose:
- archive groups (their own adapter) and groups any other adapter names;
- "Uluslararası İstatistikler" (IMF, BIS, OECD): other countries' series, and the
  warehouse only has Türkiye and its regions as areas;
- `bie_pydibs`: benchmark values of 4,158 individual government bonds;
- groups not on disk. The 36 daily and weekly groups the 2026-09-14 pull skipped were
  downloaded on 2026-09-26 (daily ones as monthly values, each series by its EVDS default
  aggregation; `scripts/fetch_evds_housing.py` with EVDS_AYLIK=1).

Writes `src/veriatlas/data/evds_groups.json` and the block between the
`# BEGIN evds_groups` / `# END evds_groups` markers in `indicators.toml`.

    .venv\Scripts\python.exe scripts\build_evds_groups.py
"""

from __future__ import annotations

import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")

from veriatlas.adapters.evds_series import item_value, rows_of
from veriatlas.config import DATA

RAW = Path("C:/veri-ham/evds")
CATALOGUE = max(RAW.glob("_katalog_*.json"))
CATEGORIES = max(RAW.glob("_kategoriler_*.json"))
TOML = DATA / "indicators.toml"
BEGIN, END = "# BEGIN evds_groups (generated)", "# END evds_groups"

EXCLUDED_TOP = {55}  # international statistics
EXCLUDED_GROUPS = {"bie_pydibs"}
FREQUENCIES = {
    "AYLIK": "monthly",
    "ÜÇ AYLIK": "quarterly",
    "YILLIK": "annual",
    "ALTI AYLIK": "semiannual",
    "HAFTALIK(CUMA)": "weekly",
    "HAFTALIK(ÇARŞAMBA)": "weekly",
    "İŞ GÜNÜ": "daily",
    "GÜNLÜK": "daily",
}
#: Top-level EVDS category → (topic id, Turkish label, English label, order).
TOPICS = {
    10: (
        "evds_surveys",
        "Beklenti ve eğilim anketleri (EVDS)",
        "Expectation and tendency surveys (EVDS)",
    ),
    15: (
        "evds_growth_public",
        "Büyüme, istihdam, kamu maliyesi (EVDS)",
        "Growth, employment, public finance (EVDS)",
    ),
    20: ("evds_prices", "Fiyat endeksleri (EVDS)", "Price indices (EVDS)"),
    25: (
        "evds_fx_metals",
        "Döviz kurları ve kıymetli madenler (EVDS)",
        "Exchange rates and precious metals (EVDS)",
    ),
    30: (
        "evds_central_bank",
        "Merkez Bankası bilanço ve piyasa verileri (EVDS)",
        "Central bank balance sheet and market data (EVDS)",
    ),
    35: (
        "evds_payments",
        "Ödeme sistemleri ve emisyon (EVDS)",
        "Payment systems and emission (EVDS)",
    ),
    40: (
        "evds_external",
        "Ödemeler dengesi ve dış istatistikler (EVDS)",
        "Balance of payments and external statistics (EVDS)",
    ),
    45: (
        "evds_monetary",
        "Parasal ve finansal istatistikler (EVDS)",
        "Monetary and financial statistics (EVDS)",
    ),
    50: (
        "evds_real_sector",
        "Reel sektör istatistikleri (EVDS)",
        "Real sector statistics (EVDS)",
    ),
}


def q(text: str) -> str:
    """A TOML basic string (JSON escapes are valid TOML)."""
    return json.dumps(" ".join(str(text).split()), ensure_ascii=False)


def claimed_groups() -> set[str]:
    """Groups another adapter already reads: named in its code or data files."""
    root = Path("src/veriatlas")
    text = ""
    for path in glob.glob(str(root / "adapters" / "*.py")) + glob.glob(
        str(root / "data" / "*.json")
    ):
        if Path(path).name in ("evds_groups.py", "evds_groups.json"):
            continue
        text += Path(path).read_text(encoding="utf-8").lower()
    return set(re.findall(r"bie_[a-z0-9]+", text))


def main() -> None:
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    categories = {
        int(c["CATEGORY_ID"]): c
        for c in json.loads(CATEGORIES.read_text(encoding="utf-8"))
    }

    def top(category_id) -> int:
        c = categories[int(category_id)]
        while int(c["UST_CATEGORY_ID"]) != -1:
            c = categories[int(c["UST_CATEGORY_ID"])]
        return int(c["CATEGORY_ID"])

    claimed = claimed_groups()
    specs: dict[str, dict] = {}
    blocks: list[str] = []
    skipped: Counter = Counter()
    for category in catalogue:
        title = category["TOPIC_TITLE_TR"].strip()
        top_id = top(category["CATEGORY_ID"])
        for group in category["DATAGROUPS"]:
            code = group["DATAGROUP_CODE"]
            if "ARŞİV" in title.upper() or "(ARŞİV)" in group["DATAGROUP_TYPE"].upper():
                skipped["arşiv"] += 1
                continue
            if code in claimed:
                skipped["başka adaptörde"] += 1
                continue
            if top_id in EXCLUDED_TOP or code in EXCLUDED_GROUPS:
                skipped["bilerek dışarıda"] += 1
                continue
            main_file, monthly_file = RAW / f"{code}.json", RAW / f"{code}-aylik.json"
            frequency = FREQUENCIES[group["FREQUENCY_STR"]]
            if frequency == "daily" and monthly_file.exists():
                path, frequency = monthly_file, "monthly"
            elif main_file.exists():
                path = main_file
            elif monthly_file.exists():
                path, frequency = monthly_file, "monthly"
            else:
                skipped["indirilmemiş"] += 1
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            filled = {s["SERIE_CODE"] for s, _, _ in rows_of(payload)}
            series = [
                s
                for s in payload["series"]
                if s["SERIE_CODE"] in filled
                # the group's own frequency only; a monthly-average download is all monthly
                and (
                    path == monthly_file
                    or FREQUENCIES.get(s["FREQUENCY_STR"]) == frequency
                )
            ]
            if not series:
                skipped["boş"] += 1
                continue
            values = [item_value(s["SERIE_CODE"]) for s in series]
            if len(set(values)) != len(values):
                raise ValueError(f"{code}: kalem kodları çakışıyor")
            ident = "evds_" + code.removeprefix("bie_")
            dim = ident + "_item"
            specs[ident] = {
                "group": code,
                "file": path.name,
                "dim": dim,
                "frequency": frequency,
                "codes": [s["SERIE_CODE"] for s in series],
            }
            topic = TOPICS[top_id][0]
            unit = group.get("BIRIMI") or "belirtilmemiş"
            lines = [
                f"[dim.{dim}]",
                'label_tr = "Kalem"',
                f'label_en = "{dim}"',
                "",
                f"[dim.{dim}.values]",
                *(
                    f"{v} = {q(s['SERIE_NAME'])}"
                    for v, s in zip(values, series, strict=True)
                ),
                "",
                f"[indicator.{ident}]",
                f"label_tr = {q(group['DATAGROUP_TYPE'])}",
                f"label_en = {q(group.get('DATAGROUP_TYPE_ENG') or ident)}",
                f'topic = "{topic}"',
                'unit = "source_unit"',
                f'frequency = "{frequency}"',
                f'dims = ["{dim}"]',
                'views = ["table", "line"]',
                "definition_tr = "
                + q(
                    f"EVDS {code} ({title}); kaynak {group.get('DATASOURCE', '')}; grubun birimi: "
                    f"{unit}. Seri seri birim ve baz yılı kalem adındadır; kalemler toplanmaz. "
                    f"Yalnız Türkiye. İndirme "
                    + ("2026-09-26" if "aggregation" in payload else "2026-09-14")
                    + (
                        (
                            ", günlük seri aylığa her serinin EVDS varsayılan birleştirmesiyle "
                            "çevrildi (akım toplam, stok ay sonu, oran ortalama)"
                            if "aggregation" in payload
                            else ", günlük seri aylık ortalama olarak"
                        )
                        if path == monthly_file
                        and group["FREQUENCY_STR"] in ("GÜNLÜK", "İŞ GÜNÜ")
                        else ""
                    )
                    + ". Üretici scripts/build_evds_groups.py."
                ),
                "",
            ]
            blocks.append("\n".join(lines))

    topics = "\n".join(
        f'[topic.{t}]\nlabel_tr = "{tr}"\nlabel_en = "{en}"\norder = {91 + i}\n'
        for i, (t, tr, en) in enumerate(TOPICS.values())
    )
    block = (
        f"{BEGIN}\n# Do not edit by hand: scripts/build_evds_groups.py rewrites it.\n\n{topics}\n"
        + "\n".join(blocks)
        + f"{END}\n"
    )
    toml = TOML.read_text(encoding="utf-8")
    if BEGIN in toml:
        head, rest = toml.split(BEGIN, 1)
        toml = head + block + rest.split(END + "\n", 1)[1]
    else:
        toml = toml.rstrip("\n") + "\n\n" + block
    TOML.write_text(toml, encoding="utf-8")
    (DATA / "evds_groups.json").write_text(
        json.dumps(specs, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(len(specs), "grup", dict(skipped))
    print(Counter(s["frequency"] for s in specs.values()))


if __name__ == "__main__":
    main()
