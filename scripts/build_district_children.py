"""Yearly settlement series for one district's file page.

public/atlas/<district>.json (build_atlas_data.py) holds the 2024 Endeksa snapshot per
settlement, keyed by Endeksa id. TÜİK MEDAS gives every settlement a yearly 0-17 / 18+ ×
sex count from 2013, keyed by MEDAS code — a different id. This joins the two by folded
name within the district and writes public/atlas/<district>.children.json:

    {"years": [2013, ...], "units": [{"id": <atlas unit id>, "name", "urban",
        "series": {"2013": {"child": n, "adult": n, "male": n, "female": n}, ...}}],
     "totals": {"2013": {"urban": {"child", "adult"}, "rural": {...}}, ...},
     "vital": {"2014": {"births": n, "deaths": n}, ...},   # TÜİK district counts
     "households": {"2012": {"count": n, "size": x}, ...}}  # TÜİK district, MEDAS basit

Before 2013 the same measure is published without the age split, and the map was
different: villages, and towns (belde) with their own neighbourhoods. raw/medas/yerlesim
holds those totals per province (fetch_medas_settlement_totals.py, --years 2007..2012).
They are folded in as {"total": n} per unit: villages by name; the district town's
neighbourhoods by name; a former belde — one unit since 6360 — by its belediye total.

Settlements in MEDAS with no Endeksa counterpart (renamed, merged) are listed under
"unmatched" rather than dropped silently; their people still count in "totals".

Run:  uv run python scripts/build_district_children.py TR-16-006
"""

import json
import re
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
ATLAS = PUBLIC / "atlas"

TR_LOWER = str.maketrans(
    "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ", "abcçdefgğhıijklmnoöprsştuüvyz"
)


def fold(name: str) -> str:
    name = name.split("/")[-1].translate(TR_LOWER).strip()
    for suffix in (" mah.", " mahallesi", " köy.", " köyü", " köy", " bel."):
        name = name.removesuffix(suffix)
    return "".join(ch for ch in name if ch.isalnum())


RAW = ROOT / "raw"
RAW_SETTLEMENTS = RAW / "medas" / "yerlesim"

#: Old settlement names that no later MEDAS row repeats, so the code trick cannot find
#: them. Recorded here, not guessed: each entry was checked against the population series.
ALIASES = {"TR-16-006": {"Nüzhetiye": "Çampınar"}}


def read_medas_rows2(path: Path):
    """Like read_medas_rows, for a two-column export (18+ yes / no): yields
    (year, label, adult, child)."""
    year = None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        cells = line.split("|")
        if len(cells) < 4 or not cells[1].strip() or "(" not in cells[1]:
            continue
        if cells[0].strip().isdigit():
            year = int(cells[0])
        if year is None:
            continue
        try:
            yield year, cells[1], int(float(cells[2])), int(float(cells[3]))
        except ValueError:
            continue


def read_medas_rows(path: Path, as_float: bool = False):
    """Yield (year, label, value) from a MEDAS export; a year opens a block, then rows
    continue it with an empty first cell."""
    year = None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        cells = line.split("|")
        if len(cells) < 3 or not cells[1].strip() or "(" not in cells[1]:
            continue
        if cells[0].strip().isdigit():
            year = int(cells[0])
        if year is None:
            continue
        try:
            yield year, cells[1], float(cells[2]) if as_float else int(float(cells[2]))
        except ValueError:
            continue


def backfill_early(
    district: str, atlas: dict, units: dict, unmatched: list[str]
) -> list[int]:
    """Fold pre-2013 village / town / neighbourhood totals into `units`. Returns the years found."""
    province = atlas["province"].upper().replace("İ", "I")
    files = {
        k: next(RAW_SETTLEMENTS.glob(f"nufus-{k}-{province}-*.csv"), None)
        for k in ("koy", "belediye", "mahalle")
    }
    if not all(files.values()):
        return []
    district_name = atlas["name"]
    by_name = {fold(u["name"]): u for u in atlas["units"]}
    for old, new in ALIASES.get(district, {}).items():
        if fold(new) in by_name:
            by_name[fold(old)] = by_name[fold(new)]
    found: set[int] = set()

    def put(unit, year, value, label=None):
        entry = units.setdefault(
            unit["id"],
            {
                "id": unit["id"],
                "name": unit["name"],
                "urban": unit["urban"],
                "medas": [],
                "series": {},
            },
        )
        entry["series"][str(year)] = {"total": value}
        found.add(year)
        if label and fold(label) != fold(
            unit["name"]
        ):  # an earlier name, kept as a note
            entry.setdefault("former", [])
            if label not in entry["former"]:
                entry["former"].append(label)

    # Villages: "Bursa(İznik/Merkez Bucağı/Aydınlar Köy.)-7543". A village renamed
    # between years keeps its code, so rows are grouped by code and the group is matched
    # by whichever of its names the atlas knows.
    by_code: dict[str, list] = {}
    for year, label, value in read_medas_rows(files["koy"]):
        inner = label[label.index("(") + 1 : label.rindex(")")]
        parts = inner.split("/")
        if parts[0] != district_name:
            continue
        by_code.setdefault(label.rsplit("-", 1)[-1], []).append(
            (year, parts[-1], value)
        )
    for code, rows in by_code.items():
        unit = next((by_name[fold(n)] for _, n, _ in rows if fold(n) in by_name), None)
        if unit:
            for year, name, value in rows:
                put(unit, year, value, name.replace(" Köy.", ""))
        else:
            unmatched.append(f"köy kodu {code}: {sorted({n for _, n, _ in rows})}")
    # Towns: "Bursa(İznik/Boyalıca Bel.)-1554" — the district's own town is its centre
    # neighbourhoods (taken below); a former belde is one unit today, so its total is used.
    town_of_district = None
    for year, label, value in read_medas_rows(files["belediye"]):
        inner = label[label.index("(") + 1 : label.rindex(")")]
        parts = inner.split("/")
        if parts[0] != district_name:
            continue
        town = parts[-1].replace(" Bel.", "")
        if fold(town) == fold(district_name):
            town_of_district = parts[-1]
            continue
        unit = by_name.get(fold(town))
        if unit:
            put(unit, year, value)
        elif label not in unmatched:
            unmatched.append(label)
    # Neighbourhoods of the district's town: "Bursa(İznik/İznik Bel./Beyler Mah.)-11415"
    for year, label, value in read_medas_rows(files["mahalle"]):
        inner = label[label.index("(") + 1 : label.rindex(")")]
        parts = inner.split("/")
        if parts[0] != district_name or len(parts) < 3 or parts[1] != town_of_district:
            continue
        unit = by_name.get(fold(parts[-1]))
        if unit:
            put(unit, year, value)
        elif label not in unmatched:
            unmatched.append(label)
    # The 18+ split before 2013 exists for municipality neighbourhoods only. Where a row
    # matches a unit that already has that year's total, the split is added to it; the
    # town's own neighbourhoods are the ones the atlas lists, former belde neighbourhoods
    # (three of Boyalıca, three of Elbeyli) are summed into their belde unit.
    early_split = next(
        (RAW / "medas" / "mahalle").glob(f"nufus-mahalle-{province}-*_*.csv"), None
    )
    if early_split:
        belde_acc: dict[tuple, dict] = {}
        for year, label, adult, child in read_medas_rows2(early_split):
            inner = label[label.index("(") + 1 : label.rindex(")")]
            parts = inner.split("/")
            if parts[0] != district_name or len(parts) < 3:
                continue
            if parts[1] == town_of_district:
                unit = by_name.get(fold(parts[-1]))
                key = unit and unit["id"]
            else:
                unit = by_name.get(fold(parts[1].replace(" Bel.", "")))
                key = unit and unit["id"]
            if not unit:
                continue
            acc = belde_acc.setdefault((key, year), {"adult": 0, "child": 0})
            acc["adult"] += adult
            acc["child"] += child
        for (key, year), acc in belde_acc.items():
            cell = units.get(key, {}).get("series", {}).get(str(year))
            if cell is not None:
                cell.update(acc)
    return sorted(found)


def _span(path: Path) -> int:
    """Number of years a MEDAS pull's filename claims (…-2008-2025.csv -> 18)."""
    m = re.search(r"-(\d{4})-(\d{4})\.csv$", path.name)
    return int(m.group(2)) - int(m.group(1)) + 1 if m else 0


MARITAL_TR = {
    "Hiç Evlenmedi": "never",
    "Evli": "married",
    "Boşandı": "divorced",
    "Eşi Öldü": "widowed",
}


def marital_series(path: Path, district: str) -> dict[str, dict]:
    """Marital status by year for one district, from the multi-year MEDAS district file.

    The year sits in the first column of the first district row of each year block and is
    blank on the rows below it, so it is carried down. Columns are
    "<cinsiyet> ve <yas grubu> ve <medeni durum>"; the page shows the district totals, so
    sex and age are summed here — the 2024 age detail already lives in the atlas bundle.
    """
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("iso-8859-9")
    lines = text.splitlines()
    header = lines[2].split("|")
    out: dict[str, dict] = {}
    year = None
    for line in lines[3:]:
        cells = line.split("|")
        if len(cells) < len(header) or len(cells) < 2:
            continue
        if cells[0].strip():
            year = cells[0].strip()
        if year is None or district not in cells[1]:
            continue
        row = {
            scope: dict.fromkeys(MARITAL_TR.values(), 0)
            for scope in ("total", "male", "female")
        }
        for h, v in zip(header, cells):
            if h.count(" ve ") != 2 or not v.strip():
                continue
            sex, _age, status = h.split(" ve ")
            key = MARITAL_TR[status]
            n = int(float(v))
            row["total"][key] += n
            row["male" if sex == "Erkek" else "female"][key] += n
        if sum(row["total"].values()):
            out[year] = row
    return out


def main(district: str) -> None:
    atlas = json.loads((ATLAS / f"{district}.json").read_text(encoding="utf-8"))
    frames = []
    for dataset in ("population-neighbourhood", "population-village"):
        df = pl.read_csv(PUBLIC / f"{dataset}.csv.gz", infer_schema_length=0)
        frames.append(df.filter(pl.col("area_id").str.starts_with(district + "-")))
    rows = pl.concat(frames).with_columns(
        pl.col("value").cast(pl.Int64), pl.col("year").cast(pl.Int32)
    )
    years = sorted(rows["year"].unique().to_list())

    by_name = {fold(u["name"]): u for u in atlas["units"]}
    units: dict[str, dict] = {}
    unmatched: list[str] = []
    for (medas_id, label), part in rows.group_by(
        ["area_id", "area"], maintain_order=True
    ):
        unit = by_name.get(fold(label))
        if unit is None:
            unmatched.append(label)
            continue
        series = {}
        for (year,), cell in part.group_by(["year"], maintain_order=True):
            child = cell.filter(pl.col("age") == "0-17")["value"].sum()
            adult = cell.filter(pl.col("age") == "18+")["value"].sum()
            male = cell.filter(pl.col("sex") == "male")["value"].sum()
            female = cell.filter(pl.col("sex") == "female")["value"].sum()
            series[str(year)] = {
                "child": child,
                "adult": adult,
                "male": male,
                "female": female,
            }
        entry = units.setdefault(
            unit["id"],
            {
                "id": unit["id"],
                "name": unit["name"],
                "urban": unit["urban"],
                "medas": [],
                "series": {},
            },
        )
        entry["medas"].append(medas_id)
        for (
            year,
            cell,
        ) in series.items():  # a settlement split in MEDAS sums into one atlas unit
            acc = entry["series"].setdefault(
                year, {"child": 0, "adult": 0, "male": 0, "female": 0}
            )
            for key, value in cell.items():
                acc[key] += value

    # 2007-2012 totals, when the province's scoped files are on disk.
    early_years = backfill_early(district, atlas, units, unmatched)
    years = sorted(set(years) | set(early_years))

    urban_names = {fold(u["name"]) for u in atlas["units"] if u["urban"]}
    totals = {}
    for (year,), part in rows.group_by(["year"], maintain_order=True):
        t = {"urban": {"child": 0, "adult": 0}, "rural": {"child": 0, "adult": 0}}
        for row in part.iter_rows(named=True):
            side = "urban" if fold(row["area"]) in urban_names else "rural"
            t[side]["child" if row["age"] == "0-17" else "adult"] += row["value"]
        totals[str(year)] = t

    for (
        year
    ) in early_years:  # totals from the units themselves (no age split before 2013)
        t = {"urban": {"total": 0}, "rural": {"total": 0}}
        for u in units.values():
            cell = u["series"].get(str(year))
            if cell and "total" in cell:
                t["urban" if u["urban"] else "rural"]["total"] += cell["total"]
        totals[str(year)] = t

    vital: dict[str, dict] = {}
    for dataset, key in (("births-district", "births"), ("deaths-district", "deaths")):
        df = pl.read_csv(PUBLIC / f"{dataset}.csv.gz", infer_schema_length=0)
        df = df.filter(pl.col("area_id") == district).with_columns(
            pl.col("value").cast(pl.Int64)
        )
        for (year,), part in df.group_by(["year"]):
            vital.setdefault(str(year), {})[key] = part["value"].sum()

    # District households: count (2012+) and mean size (2008+), from the simple pulls.
    households: dict[str, dict] = {}
    medas_code = f"({atlas['name']})-"
    for dataset, key in (
        ("nufus-hane-sayisi-ilce-district", "count"),
        ("nufus-hane-buyuklugu-ilce-district", "size"),
    ):
        path = ROOT / "raw" / "medas" / "basit" / f"{dataset}.csv"
        if not path.exists():
            continue
        for year, label, value in read_medas_rows(path, as_float=True):
            if medas_code in label and label.startswith(atlas["province"]):
                households.setdefault(str(year), {})[key] = value

    # Marital status 2008-2025 (MEDAS district file for the province). The atlas bundle
    # carries only the reference year; the page needs the series to draw a trend.
    marital: dict[str, dict] = {}
    # Several pulls of the same province exist (single years, re-runs); take the one
    # covering the most years rather than whichever the glob happens to list first.
    candidates = sorted(
        (RAW / "medas" / "medeni").glob(
            f"nufus-medeni-ilce-{fold(atlas['province'])}-*.csv"
        ),
        key=lambda q: -_span(q),
    )
    mar_path = candidates[0] if candidates and _span(candidates[0]) else None
    if mar_path is not None:
        marital = marital_series(mar_path, atlas["name"])

    out = {
        "district": district,
        "marital": marital,
        "vital": vital,
        "households": households,
        "years": years,
        "units": list(units.values()),
        "totals": totals,
        "unmatched": unmatched,
    }
    path = ATLAS / f"{district}.children.json"
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"{len(units)} units matched, {len(unmatched)} unmatched: {unmatched}")
    print("yazildi:", path.name, round(path.stat().st_size / 1e3), "KB")


if __name__ == "__main__":
    main(sys.argv[1])
