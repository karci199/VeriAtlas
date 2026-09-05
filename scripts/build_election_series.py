"""Build the election comparison dataset served by web/elections.html.

Source: the TUIK "by district" parliamentary election table, scraped earlier into
raw/tuik_secim_ilce/secim_ilce.csv (17 elections, 1961-2023, one row per
year x constituency x unit x measure).

Output (under public/elections/):

* index.json -- election list, party bloc map, province/district directory and
  the national series.
* <province-slug>.json -- that province's own series plus one series per district.

A unit's series is raw counts only (registered / voted / valid / votes per party);
every rate, share, bloc and effective-party-count is derived in the browser, so a
change of definition does not need a rebuild.

Rows that are constituency totals or section captions are dropped: a province is
the sum of its own district rows, and the country is the sum of the provinces.
That keeps provinces created after 1989 comparable with their districts.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = pathlib.Path(r"C:\veri\raw\tuik_secim_ilce\secim_ilce.csv")
OUT_DIR = REPO / "public" / "elections"
AREAS = REPO / "src" / "veriatlas" / "data" / "areas_tr.csv"

YEARS = [
    "1961",
    "1965",
    "1969",
    "1973",
    "1977",
    "1983",
    "1987",
    "1991",
    "1995",
    "1999",
    "2002",
    "2007",
    "2011",
    "2015_7_haziran",
    "2015_1_kasim",
    "2018",
    "2023",
]
YEAR_LABEL = {"2015_7_haziran": "2015 Haziran", "2015_1_kasim": "2015 Kasım"}

# Aggregate measures, kept apart from the party columns.
REGISTERED = "Kayıtlı seçmen sayısı"
VOTED = "Oy kullanan seçmen sayısı"
VALID = "Geçerli oy sayısı"
BALLOT_BOXES = "Sandık sayısı"
AGGREGATE = {REGISTERED, VOTED, VALID, BALLOT_BOXES}

INDEPENDENT = "BĞMZ"  # pooled independents column, not a party

# Bloc classification: a judgement call, spelled out so it can be argued with.
# Kurdish parties are flagged separately as well, because they drive most of the
# long-run left/right movement.
KURDISH = {"HADEP", "DEHAP", "HDP", "YEŞİL SOL PARTİ", "DTP"}
LEFT = {
    "CHP",
    "SHP",
    "HP",
    "DSP",
    "TİP",
    "TBP",
    "BİRLİK PARTİSİ",
    "SP",
    "SİP",
    "ÖDP",
    "EMEP",
    "TKP",
    "TKH",
    "KP",
    "HKP",
    "SOL PARTİ",
    "MEMLEKET",
    "İP",
    "VATAN PARTİSİ",
} | KURDISH
RIGHT = {
    "AP",
    "CKMP",
    "MİLLET PARTİSİ",
    "MİLLET",
    "GP",
    "CGP",
    "DEMOKRATİK PARTİ",
    "MSP",
    "MHP",
    "MÇP",
    "ANAP",
    "MDP",
    "IDP",
    "RP",
    "FP",
    "SAADET PARTİSİ",
    "DYP",
    "DP",
    "BBP",
    "BÜYÜK BİRLİK",
    "LDP",
    "YDP",
    "YDH",
    "YENİ PARTİ",
    "AK PARTİ",
    "GENÇ PARTİ",
    "BTP",
    "HYP",
    "ATP",
    "YURT-P",
    "HEPAR",
    "HAS PARTİ",
    "MMP",
    "HÜDA PAR",
    "İYİ PARTİ",
    "YENİDEN REFAH",
    "ZAFER PARTİSİ",
    "ANADOLU PARTİSİ",
    "MİLLİ YOL",
}

# Aggregate rows and section captions that are not districts.
NOT_A_DISTRICT = re.compile(
    r"toplam|türkiye|il/ilçe merkezi|belde|bucağ|seçim çevresi", re.IGNORECASE
)
PROVINCE_ALIAS = {
    "afyon": "afyonkarahisar",
    "icel": "mersin",
    "k_maras": "kahramanmaras",
}


def lower_tr(text: str) -> str:
    return text.replace("İ", "i").replace("I", "ı").lower()


def slugify(text: str) -> str:
    text = lower_tr(text)
    for src, dst in zip("çğıöşü", "cgiosu"):
        text = text.replace(src, dst)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def bloc_of(party: str, year: str) -> str:
    """YTP is two unrelated parties: right in 1961-69, centre-left in 2002."""
    if party == "YTP":
        return "left" if year == "2002" else "right"
    if party in LEFT:
        return "left"
    if party in RIGHT:
        return "right"
    return "other"


def province_names() -> dict[str, tuple[str, str]]:
    """Election-table province slug -> (area id, display name)."""
    out = {}
    with AREAS.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["area_level"] == "province":
                out[slugify(row["name_tr"])] = (row["area_id"], row["name_tr"])
    return out


def read_source(path: pathlib.Path):
    """(year, province, constituency, unit) -> {measure: count}, plus first unit."""
    first_unit: dict[tuple[str, str], str] = {}
    cells: dict[tuple[str, str, str, str], dict[str, int]] = collections.defaultdict(
        dict
    )
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            province = re.sub(r"_\d+$", "", row["cevre"])
            province = PROVINCE_ALIAS.get(province, province)
            first_unit.setdefault((row["yil"], row["cevre"]), row["birim"])
            cells[(row["yil"], province, row["cevre"], row["birim"])][row["olcut"]] = (
                int(row["deger"])
            )
    return first_unit, cells


def series_entry(measures: dict[str, int]) -> dict:
    parties = {
        name: count
        for name, count in measures.items()
        if name not in AGGREGATE and "İTTİFAK" not in name and count
    }
    return {
        "e": measures.get(REGISTERED, 0),
        "v": measures.get(VOTED, 0),
        "g": measures.get(VALID, 0),
        "p": parties,
    }


def add_into(target: dict, entry: dict) -> None:
    for key in ("e", "v", "g"):
        target[key] = target.get(key, 0) + entry[key]
    parties = target.setdefault("p", {})
    for name, count in entry["p"].items():
        parties[name] = parties.get(name, 0) + count


def build(source: pathlib.Path) -> None:
    names = province_names()
    first_unit, cells = read_source(source)

    districts: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    province_series: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    national: dict[str, dict] = {}
    unknown = set()

    for (year, province, constituency, unit), measures in cells.items():
        if unit == first_unit[(year, constituency)]:
            continue  # constituency total
        if NOT_A_DISTRICT.search(lower_tr(unit)):
            continue  # section caption or sub-total
        if slugify(unit) == slugify(province):
            continue  # pre-1991 reports repeat the province as a row
        if province not in names:
            unknown.add(province)
            continue

        name = unit.strip()
        slug = slugify(name)
        if slug == "merkez" or slug.endswith("-merkez"):
            slug = "merkez"
            name = f"{names[province][1]} Merkez"

        entry = series_entry(measures)
        if not entry["g"]:
            continue
        district = districts[province].setdefault(slug, {"name": name, "years": {}})
        if year in district["years"]:
            add_into(district["years"][year], entry)  # name split over constituencies
        else:
            district["years"][year] = entry
        add_into(province_series[province].setdefault(year, {}), entry)
        add_into(national.setdefault(year, {}), entry)

    if unknown:
        print(f"uyarı: eşleşmeyen il: {sorted(unknown)}", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUT_DIR.glob("*.json"):
        stale.unlink()

    directory = []
    for province in sorted(districts, key=lambda p: names[p][1]):
        area_id, display = names[province]
        rows = districts[province]
        payload = {
            "slug": province,
            "name": display,
            "areaId": area_id,
            "total": province_series[province],
            "districts": rows,
        }
        (OUT_DIR / f"{province}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        directory.append(
            {
                "slug": province,
                "name": display,
                "areaId": area_id,
                "districts": [
                    {"slug": s, "name": rows[s]["name"]}
                    for s in sorted(rows, key=lambda s: rows[s]["name"])
                ],
            }
        )

    blocs = {}
    for year in YEARS:
        for party in national.get(year, {}).get("p", {}):
            blocs.setdefault(party, bloc_of(party, year))
    blocs["YTP"] = "right"  # 2002 is corrected per year in the page

    index = {
        "source": "TÜİK, milletvekili genel seçimleri (biruni.tuik.gov.tr)",
        "years": [
            {"id": y, "label": YEAR_LABEL.get(y, y)} for y in YEARS if y in national
        ],
        "blocs": blocs,
        "kurdish": sorted(KURDISH),
        "independent": INDEPENDENT,
        "national": national,
        "provinces": directory,
    }
    (OUT_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    total_districts = sum(len(v) for v in districts.values())
    print(f"{len(directory)} il, {total_districts} ilçe, {len(index['years'])} seçim")
    print(f"-> {OUT_DIR}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=pathlib.Path, default=DEFAULT_SOURCE)
    args = ap.parse_args()
    if not args.source.exists():
        sys.exit(f"kaynak yok: {args.source}")
    build(args.source)


if __name__ == "__main__":
    main()
