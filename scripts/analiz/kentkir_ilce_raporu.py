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

import json
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
