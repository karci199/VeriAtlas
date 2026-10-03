"""District report of the hand-made urban/rural classification (Bursa and Ankara).

Reads the classification decisions, the per-unit table of the kent/kır check page and the
2007-2025 population series, joins election results and 18+ population, and writes one
self-contained page, `web/kentkir-ilce.html`: for every district, province and both together

* urban/rural population per year (2013-2025: the first year every unit has an id) with the
  annual change and the urban share,
* average and median village size per year,
* buildings, dwellings and households per class (dwelling per building, household size),
* election profile per general election: registered voters, turnout, 18+ population and the
  AKP/CHP/MHP/İYİ/DEM(YSP/HDP)/other split, urban against rural.

Urban = İlçe Merkezi + Kentsel Belde. Rural = Kırsal Belde + Köy.

Run from the repository root. The decision file lives in the worktree where the page is
used (see DECISIONS); the warehouse and the election tiles in the main checkout.
"""

from __future__ import annotations

import csv
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
WORK = Path("C:/veri/.claude/worktrees/durum-nerede-kaldik-a0f14b")
DECISIONS = WORK / "scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json"
CHECK = WORK / "public/kentkir_kontrol.json"
SERIES = WORK / "public/kentkir_nufus.json"
FACT = "C:/veri/public/fact.parquet"
TILES = Path("C:/veri/public/tiles")
TEMPLATE = ROOT / "web/kentkir-ilce.template.html"
OUT = ROOT / "web/kentkir-ilce.html"

PROVINCES = {"Bursa": "16", "Ankara": "06"}
URBAN = {"İlçe Merkezi", "Kentsel Belde"}
CLASSES = ["İlçe Merkezi", "Kentsel Belde", "Kırsal Belde", "Köy"]
YEARS = list(range(2013, 2026))
#: (tile name, label, year of the 18+ population it is compared with)
ELECTIONS = [
    ("mv2015h", "2015 Haziran", 2015),
    ("mv2015k", "2015 Kasım", 2015),
    ("mv2018", "2018", 2018),
    ("mv2023", "2023", 2023),
]
PARTIES = ["AKP", "CHP", "MHP", "İYİ", "DEM", "SP/YRP", "Zafer"]
PARTY_NAMES = {
    "AK PARTİ": "AKP",
    "CHP": "CHP",
    "MHP": "MHP",
    "İYİ PARTİ": "İYİ",
    "HDP": "DEM",
    "YEŞİL SOL PARTİ": "DEM",
    "SAADET PARTİSİ": "SP/YRP",
    "YENİDEN REFAH": "SP/YRP",
    "ZAFER PARTİSİ": "Zafer",
}


def side_of(klass: str) -> str:
    return "kent" if klass in URBAN else "kir"


def load_inputs():
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    check = json.loads(CHECK.read_text(encoding="utf-8"))
    keys = {name: i for i, name in enumerate(check["keys"])}
    rows = [
        r
        for r in check["rows"]
        if r[keys["il"]] in PROVINCES and r[keys["id"]] in decisions
    ]
    series = json.loads(SERIES.read_text(encoding="utf-8"))
    return decisions, rows, keys, series


def adult_population(year: int, prefixes: tuple[str, ...]) -> dict[str, float]:
    """18+ population of every neighbourhood in the given provinces."""
    like = " or ".join(f"area_id like '{p}%'" for p in prefixes)
    rows = (
        duckdb.connect()
        .sql(
            f"""select area_id, sum(value) from read_parquet('{FACT}')
            where indicator_id='population' and dims='age=18+' and year(period_start)={year}
            and ({like}) group by 1"""
        )
        .fetchall()
    )
    return dict(rows)


def party_votes(votes: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for name, count in votes.items():
        canonical = PARTY_NAMES.get(name.replace("\ufffd", "İ").upper())
        if canonical:
            out[canonical] += count
    return out


def empty_election() -> dict:
    return {"k": 0, "o": 0, "g": 0, "a": 0, "n": 0, "p": defaultdict(int)}


CENSUS = Path("C:/veri-ham/tuik_sayim")
DISTRICTS_CSV = ROOT / "src/veriatlas/data/areas_tr_districts.csv"
#: years shown in the age table; the three census years and 2010-2025 are measured, 1995
#: and 2005 are interpolated between the neighbouring measurements (2005 between the 2000
#: census and the first ADNKS year, 2007).
AGE_YEARS = [1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]
CENSUS_YEARS = [1985, 1990, 2000]
ADNKS_YEARS = [2007, 2010, 2015, 2020, 2025]
#: names the census prints that the registry spells differently
CENSUS_ALIAS = {
    "M.Kemalpaşa": "Mustafakemalpaşa",
    "Kazan": "Kahramankazan",
    "Ş.Koçhisar": "Şereflikoçhisar",
}


def census_table_rows(path: Path) -> list[list[str]]:
    text = path.read_text(encoding="windows-1254", errors="replace")
    out = []
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", text):
        cells = [
            html.unescape(re.sub(r"<[^>]+>", " ", c)).replace(" ", " ").strip()
            for c in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row)
        ]
        cells = [c for c in cells if c]
        if cells:
            out.append(cells)
    return out


def census_ages(year: int, province: str) -> dict[str, list[int]]:
    """{district: [unknown, 0-14, 15-64, 65+]} from the census district table. The 1985
    central row prints its numbers one row above its label, hence `previous`."""
    rows = census_table_rows(
        CENSUS / str(year) / f"{province.lower()}-0-1415-6465-ilce.html"
    )
    out: dict[str, list[int]] = {}
    previous: list[str] | None = None
    to_int = lambda s: int(s.replace(".", ""))
    for row in rows:
        if "Toplam" in row[:3] and len(row) >= 5 and row[-1].replace(".", "").isdigit():
            i = row.index("Toplam")
            name = CENSUS_ALIAS.get(row[i - 1], row[i - 1])
            values = [to_int(v) for v in row[i + 1 :]]
            if len(values) == 4:
                out[name] = values
        elif (
            row[-1] == "Toplam"
            and previous
            and len(previous) == 4
            and all(v.replace(".", "").isdigit() for v in previous)
        ):
            out[row[-2]] = [to_int(v) for v in previous]
        previous = row
    return out


def adnks_ages(prefixes: tuple[str, ...]) -> dict[tuple[str, int], list[float]]:
    """{(district id, year): [0-14, 15-64, 65+]} from the five-year age bands."""
    like = " or ".join(f"area_id like '{p}%'" for p in prefixes)
    rows = (
        duckdb.connect()
        .sql(
            f"""select area_id, year(period_start), dims, sum(value)
            from read_parquet('{FACT}')
            where indicator_id='population' and area_level='district'
            and year(period_start) in ({",".join(map(str, ADNKS_YEARS))}) and ({like})
            group by 1,2,3"""
        )
        .fetchall()
    )
    out: dict[tuple[str, int], list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for area, year, dims, value in rows:
        low = int(re.match(r"age=(\d+)", dims).group(1))
        out[(area, year)][0 if low < 15 else 1 if low < 65 else 2] += value
    return out


def interpolate(points: dict[int, list[float]], year: int):
    """Linear between the two nearest measured years; None outside them."""
    if year in points:
        return points[year], "ölçüm"
    before = [y for y in points if y < year]
    after = [y for y in points if y > year]
    if not before or not after:
        return None, None
    a, b = max(before), min(after)
    w = (year - a) / (b - a)
    return [
        x + (y - x) * w for x, y in zip(points[a], points[b], strict=True)
    ], "enterpolasyon"


def age_series() -> dict:
    """{scope key: {year: {t, c, w, o, k}}}: total and 0-14 / 15-64 / 65+ for every
    district, province and both provinces."""
    names = {}
    in_province: dict[str, set[str]] = defaultdict(set)
    with DISTRICTS_CSV.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            names[row["area_id"]] = row["name_tr"]
            in_province[row["parent_id"]].add(row["name_tr"])
    prefixes = tuple(f"TR-{code}-" for code in PROVINCES.values())
    code_to_province = {f"TR-{code}": name for name, code in PROVINCES.items()}
    adnks = adnks_ages(prefixes)
    points: dict[str, dict[int, list[float]]] = defaultdict(dict)
    for (area, year), (c, w, o) in adnks.items():
        province = code_to_province[area[:5]]
        name = names.get(area)
        if not name:
            continue
        for key in (f"{province}|{name}", f"{province}|*", "*|*"):
            cur = points[key].setdefault(year, [0.0, 0.0, 0.0])
            cur[0] += c
            cur[1] += w
            cur[2] += o
    for province in PROVINCES:
        for year in CENSUS_YEARS:
            table = census_ages(year, province)
            # the 1985 Ankara table still holds the districts of Kırıkkale, a province only
            # from 1989; "Merkez" is Bursa's undivided central district
            own = in_province[f"TR-{PROVINCES[province]}"] | {"Merkez"}
            for name, (unknown, c, w, o) in table.items():
                if name not in own:
                    continue
                # the unknown-age count rides on the working-age group so the total holds
                values = [c, w + unknown, o]
                for key in (f"{province}|{name}", f"{province}|*", "*|*"):
                    cur = points[key].setdefault(year, [0.0, 0.0, 0.0])
                    for i, v in enumerate(values):
                        cur[i] += v
    out: dict = {}
    for key, measured in points.items():
        cells = {}
        for year in AGE_YEARS:
            values, how = interpolate(measured, year)
            if values is None:
                continue
            cells[str(year)] = {
                "t": sum(values),
                "c": values[0],
                "w": values[1],
                "o": values[2],
                "k": how,
            }
        out[key] = cells
    return out


def build() -> dict:
    decisions, rows, keys, series = load_inputs()
    year_index = {y: i for i, y in enumerate(series["years"])}
    prefixes = tuple(f"TR-{code}-" for code in PROVINCES.values())

    def groups(row):
        """Aggregation keys of a unit: district, province, both provinces."""
        return (
            f"{row[keys['il']]}|{row[keys['ilce']]}",
            f"{row[keys['il']]}|*",
            "*|*",
        )

    population = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    units = defaultdict(lambda: defaultdict(list))
    structure = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for row in rows:
        unit = row[keys["id"]]
        klass = decisions[unit]["s"]
        side = side_of(klass)
        values = series["s"].get(unit) or []
        for g in groups(row):
            for year in YEARS:
                v = values[year_index[year]] if values else None
                if v is None:
                    continue
                population[g][year][klass] += v
                population[g][year][side] += v
                if klass == "Köy":
                    units[g][year].append(v)
            for field in ("bl", "dw", "hh", "n"):
                structure[g][side][field] += row[keys[field]] or 0
                structure[g][klass][field] += row[keys[field]] or 0
            structure[g][side]["units"] += 1
            structure[g][klass]["units"] += 1

    towns: dict = {}
    for row in rows:
        unit = row[keys["id"]]
        klass = decisions[unit]["s"]
        if klass not in ("Kentsel Belde", "Kırsal Belde"):
            continue
        name = decisions[unit].get("y") or row[keys["ad"]]
        key = f"{row[keys['il']]}|{row[keys['ilce']]}|{name}"
        town = towns.setdefault(
            key,
            {
                "il": row[keys["il"]],
                "ilce": row[keys["ilce"]],
                "ad": name,
                "sinif": klass,
                "mahalleler": [],
                "pop": defaultdict(float),
                "bl": 0,
                "dw": 0,
                "hh": 0,
                "area": 0.0,
                "election": {},
            },
        )
        town["mahalleler"].append(row[keys["ad"]])
        for field in ("bl", "dw", "hh"):
            town[field] += row[keys[field]] or 0
        town["area"] += row[keys["area"]] or 0
        values = series["s"].get(unit) or []
        for year in YEARS:
            v = values[year_index[year]] if values else None
            if v is not None:
                town["pop"][year] += v

    election: dict = {}
    for tile, label, year in ELECTIONS:
        adults = adult_population(year, prefixes)
        by_group = defaultdict(
            lambda: {"kent": empty_election(), "kir": empty_election()}
        )
        by_id = {r[keys["id"]]: r for r in rows}
        for code in PROVINCES.values():
            path = TILES / f"secim-{tile}-mahalle-TR-{code}.json"
            for unit, data in json.loads(path.read_text(encoding="utf-8")).items():
                row = by_id.get(unit)
                if row is None:
                    continue
                side = side_of(decisions[unit]["s"])
                shares = party_votes(data["v"])
                klass = decisions[unit]["s"]
                if klass in ("Kentsel Belde", "Kırsal Belde"):
                    name = decisions[unit].get("y") or row[keys["ad"]]
                    town = towns[f"{row[keys['il']]}|{row[keys['ilce']]}|{name}"]
                    cell = town["election"].setdefault(tile, empty_election())
                    cell["k"] += data["k"]
                    cell["o"] += data["o"]
                    cell["g"] += data["g"]
                    cell["a"] += adults.get(unit, 0)
                    cell["n"] += 1
                    for party, count in shares.items():
                        cell["p"][party] += count
                for g in groups(row):
                    cell = by_group[g][side]
                    cell["k"] += data["k"]
                    cell["o"] += data["o"]
                    cell["g"] += data["g"]
                    cell["a"] += adults.get(unit, 0)
                    cell["n"] += 1
                    for party, count in shares.items():
                        cell["p"][party] += count
        election[tile] = {"label": label, "year": year, "groups": by_group}

    return {
        "years": YEARS,
        "population": population,
        "villages": units,
        "structure": structure,
        "towns": list(towns.values()),
        "election": election,
        "elections": [(t, label, y) for t, label, y in ELECTIONS],
        "age": age_series(),
        "ageYears": AGE_YEARS,
        "parties": PARTIES,
    }


def to_jsonable(obj):
    if isinstance(obj, defaultdict | dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 1)
    return obj


def main() -> None:
    data = to_jsonable(build())
    html = TEMPLATE.read_text(encoding="utf-8").replace(
        "/*DATA*/", "const DATA = " + json.dumps(data, ensure_ascii=False) + ";"
    )
    OUT.write_text(html, encoding="utf-8")
    print(
        f"wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(data['population'])} groups)"
    )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
