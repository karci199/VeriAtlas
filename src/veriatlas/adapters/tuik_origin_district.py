"""Where a district's people come from, and where its registered people went.

Three MEDAS squares at district level, one province of districts per file, 81 provinces
across the columns:

    hemsehri   residents of the district, by province of registration (nüfus kütüğü)
    diaspora   people registered to the district, by province of residence
    dogumyeri  residents of the district, by province of birth (+ abroad)

Stored whole (decision C, 2026-09-13): every district × province cell goes into the fact
table, and the page gets a summary built from it (`export_web.export_origin_summary`), so
nothing is lost and the screen does not carry 700 thousand rows.

Three traps, each of which would pass for data:

* **Suppressed cells are written as `-9.98E8`.** Read as a number, one Aladağ row would
  subtract a billion people from Adana. A negative count is withheld, never a value.
* **The row label's number is a MEDAS district code**, `Adana(Aladağ)-1757`, not a plate —
  resolved by code and year exactly as `tuik_vital_district` does.
* **The file name's province is Python's lower() of Turkish upper case** (`ağri`), so the
  name is never used to identify anything; the rows and the header carry it.

Checked against what the warehouse holds (2026-09-13):

* diaspora summed over a province's districts = kütük nüfusu, 243 of 243 province-years;
* hemşehri row totals fall short of district population by exactly the foreign nationals
  (2015: 650.308, 2025: 1.519.515 nationally) — they have no Turkish register, so no
  province column; the gap is real: Gülnar 24%, Kemer 16%, Alanya 10% in 2025;
* birthplace rows fall short by 0,15% on average (at most 2,4%): 24.327 withheld cells.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..areas import load_areas
from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .tuik_simple import LABEL, read_text
from .tuik_vital_district import area_at, districts_by_code

DOWNLOADS = RAW / "medas" / "hemsehri"

#: `nufus-hemsehri-ilce-adana-2025-2025.csv` — one year per file.
FILE = re.compile(r"-(?P<year>\d{4})-(?P=year)\.csv$")

#: Column header: `Nüfusa Kayıtlı Olunan İl:Adana`, `İkamet Edilen İl:Adana`, `Doğum Yeri:Adana`.
COLUMN = re.compile(
    r"^(?:Nüfusa Kayıtlı Olunan İl|İkamet Edilen İl|Doğum Yeri)\s*:\s*(?P<name>.+)$"
)

#: The columns that are not a province (birthplace only).
ABROAD = {"Yurtdışı": "abroad", "Bilinmeyen": "unknown"}

#: stem → (indicator id, dim).
MEASURES = {
    "hemsehri": ("population_by_registry_province", "registry_province"),
    "diaspora": ("registered_by_residence_province", "residence_province"),
    "dogumyeri": ("population_by_birth_province", "birth_province"),
}


def provinces_by_name() -> dict[str, str]:
    areas = load_areas().filter(pl.col("area_level") == "province")
    return dict(zip(areas["name_tr"], areas["area_id"], strict=True))


def read_square(
    path: Path,
    spec: tuple,
    names: dict[str, str],
    codes: dict[str, list[dict]],
) -> tuple[list[dict], int]:
    """One province's file as fact rows, and how many cells the source withheld."""
    indicator_id, dim = spec
    named = FILE.search(path.name)
    if not named:
        raise ValueError("dosya adinda yil yok: " + path.name)
    year = int(named.group("year"))
    lines = read_text(path).splitlines()

    header: dict[int, str] = {}
    for line in lines:
        found = {}
        for index, cell in enumerate(line.split("|")):
            column = COLUMN.match(cell.strip())
            if column:
                found[index] = column.group("name").strip()
        if len(found) > len(header):
            header = found
    unknown = {n for n in header.values() if n not in names and n not in ABROAD}
    if not header or unknown:
        raise KeyError(
            indicator_id
            + ": taninmayan sutun "
            + path.name
            + ": "
            + ", ".join(sorted(unknown))
        )
    columns = {i: names.get(n) or ABROAD[n] for i, n in header.items()}

    rows: list[dict] = []
    withheld = 0
    unresolved: set[str] = set()
    for line in lines:
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 3:
            continue
        if cells[0].isdigit() and len(cells[0]) == 4 and int(cells[0]) != year:
            raise ValueError(
                path.name
                + ": dosya adindaki yil "
                + str(year)
                + ", icindeki "
                + cells[0]
            )
        label = LABEL.match(cells[1])
        if not label or not label.group("code").isdigit():
            continue
        district = area_at(codes.get(label.group("code"), []), year)
        if district is None:
            if any(cells[2:]):
                unresolved.add(cells[1])
            continue
        for index, origin in columns.items():
            if index >= len(cells) or not cells[index]:
                continue
            value = float(cells[index])
            if value < 0:
                withheld += 1
                continue
            rows.append(
                {
                    "area_id": district,
                    "year": year,
                    "dims": format_dims({dim: origin}),
                    "value": value,
                }
            )
    if unresolved:
        raise KeyError(
            indicator_id
            + ": kayitta karsiligi olmayan ilce "
            + path.name
            + ": "
            + ", ".join(sorted(unresolved)[:10])
        )
    return rows, withheld


class OriginSquare:
    source_id = "tuik_medas"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 13)

    stem = ""
    spec: tuple = ()

    @property
    def indicator_id(self) -> str:
        return self.spec[0]

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        names = provinces_by_name()
        codes = districts_by_code()
        paths = sorted(raw.glob("nufus-" + self.stem + "-ilce-*.csv"))
        if not paths:
            raise ValueError("dosya bulunamadi: " + self.stem)

        records: list[dict] = []
        withheld = 0
        for path in paths:
            rows, hidden = read_square(path, self.spec, names, codes)
            records.extend(rows)
            withheld += hidden

        frame = pl.DataFrame(records)
        duplicated = frame.select("area_id", "year", "dims").is_duplicated()
        if duplicated.any():
            raise ValueError(
                self.indicator_id
                + ": ayni ilce-yil-il iki kez ("
                + str(int(duplicated.sum()))
                + " hucre) — cakisan dosya var"
            )

        # Every province present in every year: one province file missing is 5-40
        # districts drawn as "veri yok".
        provinces = set(names.values())
        for year, part in frame.group_by("year"):
            found = {area[:5] for area in part["area_id"]}
            if provinces - found:
                raise KeyError(
                    self.indicator_id
                    + ": "
                    + str(year[0])
                    + " yilinda ilcesi olmayan il: "
                    + ", ".join(sorted(provinces - found))
                )
        if withheld:
            print("   ", self.indicator_id, "· kaynak gizlemis hucre:", withheld)

        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("district").alias("area_level"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        ).select(
            "indicator_id",
            "area_id",
            "area_level",
            "period_start",
            "frequency",
            "dims",
            "value",
            "unit",
            "quality_flag",
            "vintage",
            "source_id",
            "retrieved_at",
        )


ORIGIN_ADAPTERS = {
    "tuik_" + spec[0]: type(
        "Tuik" + "".join(part.title() for part in spec[0].split("_")),
        (OriginSquare,),
        {"stem": stem, "spec": spec, "__doc__": "MEDAS district square: " + spec[0]},
    )
    for stem, spec in MEASURES.items()
}
