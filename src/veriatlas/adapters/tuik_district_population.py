"""District population from MEDAS, one CSV per year.

`scripts/fetch_medas_districts.py` walks the report wizard and downloads a CSV per year;
this reads whatever years are on disk. The two halves are kept apart on purpose: driving
a browser is slow and fragile, parsing is neither, and a parse fixed after the fact must
not require going back to TÜİK (decision K8).

The file is pipe-delimited with a five-line preamble and rows like::

    2023|Adana(Aladağ)-1757|16954.0|
        |Adana(Ceyhan)-1219|156610.0|

The year appears once and then stays blank, and the area label packs three things: the
province, the district, and MEDAS's own district code. That code is worth keeping — it
is the only stable id either side of a rename — so it goes into the registry as a
crosswalk rather than being thrown away after the join.

Names are matched folded (`Şarköy` ≡ `sarkoy`), and an unmatched district stops the
load. A district silently dropped here would show up as a hole in the map that looks
exactly like "no data".

Two shapes of export exist per year, and only one of them is loaded:

``nufus-ilce-2023.csv``
    the district total, one value column.

``nufus-ilce-kirilim-2023.csv``
    the same districts broken down by sex and age band, 38 value columns headed
    ``Erkek ve 0-4``.

Where a year has both, the breakdown wins and the total file is ignored. Loading both
would put a district's total *and* its 38 parts in the fact table at the same level, and
anything that sums across the breakdown — the explorer's "Tümü (topla)", the share
mode's denominator — would then count that district twice.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..areas import load_areas, load_districts
from ..config import RAW
from ..indicators import get
from ..schema import format_dims

DOWNLOADS = RAW / "medas" / "ilce"

#: `Adana(Aladağ)-1757` — province, district, MEDAS code.
LABEL = re.compile(r"^(?P<province>[^(]+)\((?P<district>[^)]*)\)-(?P<code>\d+)$")

#: `nufus-ilce-2023.csv` / `nufus-ilce-kirilim-2023.csv`.
FILENAME = re.compile(r"^nufus-ilce-(?P<breakdown>kirilim-)?(?P<year>\d{4})\.csv$")

#: `Erkek ve 0-4` — a column of the breakdown export.
COLUMN = re.compile(r"^(?P<sex>\S+)\s+ve\s+(?P<age>\S+)$")

SEXES = {"Erkek": "male", "Kadın": "female"}


def fold(name: str) -> str:
    """Turkish name to a comparable key. Same rule as the geometry join."""
    lowered = name.strip().lower()
    for turkish, plain in (
        ("ı", "i"),
        ("İ", "i"),
        ("ğ", "g"),
        ("ü", "u"),
        ("ş", "s"),
        ("ö", "o"),
        ("ç", "c"),
        ("â", "a"),
    ):
        lowered = lowered.replace(turkish, plain)
    return "".join(ch for ch in lowered if ch.isalnum())


#: (year, province, district, medas code, sex, age band, value). Sex and age are empty
#: strings on the total export, which is what `format_dims` turns into `DIMS_NONE`.
Record = tuple[int, str, str, str, str, str, float]


def read_export(path: Path, breakdown: bool = False) -> list[Record]:
    """One MEDAS CSV to fact rows.

    The two exports share a layout — preamble, then one line per district with the year
    filled in only on the first — and differ only in how many value columns follow. So
    the breakdown reads the column headings once and then walks the same rows.
    """
    rows: list[Record] = []
    year = None
    columns: list[tuple[str, str]] = []

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 3:
            continue

        # The heading line carries no area, so it can only be read before the rows and
        # cannot be confused with one. Column order is MEDAS's, and it is alphabetical
        # rather than numeric (5-9 lands after 55-59) — another reason to read the
        # headings instead of assuming a layout.
        if breakdown and not columns and any(COLUMN.match(c) for c in cells[2:]):
            for cell in cells[2:]:
                match = COLUMN.match(cell)
                columns.append(
                    (SEXES.get(match["sex"], match["sex"]), match["age"])
                    if match
                    else ("", "")
                )
            continue

        if cells[0].isdigit() and len(cells[0]) == 4:
            year = int(cells[0])

        match = LABEL.match(cells[1])
        if match is None or year is None:
            continue

        wanted = columns if breakdown else [("", "")]
        for index, (sex, age) in enumerate(wanted):
            if index + 2 >= len(cells):
                break
            try:
                value = float(cells[index + 2])
            except ValueError:
                # Suppressed cells are footnote markers, not numbers. Skipping them
                # leaves a gap, which is the truth; a zero would be a claim.
                continue

            rows.append(
                (
                    year,
                    match["province"],
                    match["district"],
                    match["code"],
                    sex,
                    age,
                    value,
                )
            )
    return rows


def exports(directory: Path) -> list[tuple[Path, bool]]:
    """The files to load, one per year: the breakdown where it exists, else the total."""
    found: dict[int, tuple[Path, bool]] = {}
    for path in sorted(directory.glob("nufus-ilce-*.csv")):
        match = FILENAME.match(path.name)
        if match is None:
            continue
        year = int(match["year"])
        is_breakdown = bool(match["breakdown"])
        if is_breakdown or year not in found:
            found[year] = (path, is_breakdown)
    return [found[year] for year in sorted(found)]


class TuikDistrictPopulation:
    """Total population per district and year, from the downloaded MEDAS exports."""

    source_id = "tuik_medas"
    indicator_id = "population"

    #: MEDAS shows no release date on the export, so the vintage is when we took it —
    #: the same known gap as the other TÜİK files.
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 14)

    def fetch(self) -> Path:
        """The downloads directory. Fetching is `scripts/fetch_medas_districts.py`."""
        if not any(DOWNLOADS.glob("nufus-ilce-*.csv")):
            raise FileNotFoundError(
                "indirilmis yil yok: once 'uv run python scripts/fetch_medas_districts.py --all'"
            )
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        indicator = get(self.indicator_id)

        records: list[Record] = []
        for path, breakdown in exports(raw):
            records.extend(read_export(path, breakdown))
        if not records:
            raise ValueError("indirilen dosyalarda satir yok")

        frame = pl.DataFrame(
            records,
            schema=[
                "year",
                "province",
                "district",
                "medas_code",
                "sex",
                "age",
                "value",
            ],
            orient="row",
        )

        provinces = {
            fold(row["name_tr"]): row["area_id"] for row in load_areas().to_dicts()
        }
        districts = {
            (row["parent_id"], fold(row["name_tr"])): row["area_id"]
            for row in load_districts().to_dicts()
        }

        def area_of(province: str, district: str) -> str | None:
            parent = provinces.get(fold(province))
            if parent is None:
                return None

            found = districts.get((parent, fold(district)))
            if found is not None:
                return found

            # The two sources name the central district differently: MEDAS calls it
            # "Merkez", the boundary registry gives it the province's own name
            # (Adıyaman(Merkez) ≡ the district "Adıyaman"). Fifty-one provinces are
            # affected — every one that never split its centre.
            if fold(district) == "merkez":
                return districts.get((parent, fold(province)))
            return None

        pairs = frame.select("province", "district").unique().to_dicts()
        lookup = {
            (p["province"], p["district"]): area_of(p["province"], p["district"])
            for p in pairs
        }

        missing = sorted(
            k[0] + "(" + k[1] + ")" for k, v in lookup.items() if v is None
        )
        if missing:
            raise KeyError(
                "kayitta karsiligi olmayan ilce ("
                + str(len(missing))
                + "): "
                + ", ".join(missing[:20])
                + (" …" if len(missing) > 20 else "")
            )

        # One string per distinct pair, built once: the year-by-year breakdown is close
        # to seven hundred thousand rows and formatting each one separately is the
        # slowest thing in the load.
        combinations = frame.select("sex", "age").unique().to_dicts()
        dims = {
            (c["sex"], c["age"]): format_dims(
                {"sex": c["sex"], "age": c["age"]} if c["sex"] else None
            )
            for c in combinations
        }

        return frame.with_columns(
            pl.struct("province", "district")
            .map_elements(
                lambda s: lookup[(s["province"], s["district"])], return_dtype=pl.String
            )
            .alias("area_id"),
            pl.lit("district").alias("area_level"),
            pl.date(pl.col("year").cast(pl.Int32), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.struct("sex", "age")
            .map_elements(lambda s: dims[(s["sex"], s["age"])], return_dtype=pl.String)
            .alias("dims"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        ).drop("year", "province", "district", "medas_code", "sex", "age")
