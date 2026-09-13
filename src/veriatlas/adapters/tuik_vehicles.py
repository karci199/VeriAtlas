"""Motor land vehicles — MEDAS, country and province, yearly.

Pulled 2026-09-13 (`scripts/fetch_medas_simple.py tasit-*`). Same transposed export as the
municipal files: areas across the header, one row per breakdown value per year. A row
label is one or more `code. (Name)` parts joined by " ve " — `10680. (Alfa Romeo) ve 1.
(Otomobil)` — so each file names its dims in order and every part is read by its MEDAS
code, not its spelling (the export writes "Audı", "Lpg   ").

"Every breakdown on" does not cross them all. "Motorlu Kara Taşıt Sayısı" came back as
registration status × vehicle type — the year's registrations and deregistrations, a
flow — while the same measure by fuel or by age is the stock at year end (Türkiye 2025:
33 million). They are therefore separate indicators, not one indicator's breakdowns.

At province level the brand files come one year per file (`...-province-2004.csv`): with
brand open they are 426 and 472 indicators, one year per query under the cell limit.

Codes and names the dictionary does not know stop the load. Brand and colour are read
by code, and their names live in the dictionary as labels (K1).
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..areas import load_areas
from ..config import RAW
from ..indicators import get, load
from ..schema import format_dims
from .tuik_median_age import single_province_regions
from .tuik_simple import read_text
from .tuik_vital import header_of

DOWNLOADS = RAW / "medas" / "basit"

PART = re.compile(r"^(\d+)\.\s*\((.*)\)$")
SEPARATOR = re.compile(r"\)\s+ve\s+(?=\d+\.)")

#: MEDAS code → dimension value id, for dims whose values have English ids.
CODES = {
    "vehicle_type": {
        "1": "car",
        "2": "minibus",
        "3": "bus",
        "4": "pickup",
        "5": "truck",
        "6": "motorcycle",
        "7": "special_purpose",
        "8": "construction_machinery",
        "9": "tractor",
    },
    "registration": {"1": "registered", "2": "deregistered"},
    "vehicle_age": {"1": "0-5", "2": "6-10", "3": "11-15", "4": "16-20", "5": "21+"},
    "fuel": {
        "1": "petrol",
        "2": "diesel",
        "5": "electric",
        "6": "lpg",
        "20": "hybrid",
        "99": "unknown",
    },
}

#: file stem → (indicator id, dims in label order).
MEASURES = {
    "tasit-01": ("vehicle_registrations", ("registration", "vehicle_type")),
    "tasit-01-yakit": ("vehicles_by_fuel", ("fuel",)),
    "tasit-01-marka": ("vehicles_by_brand", ("brand",)),
    "tasit-03-yas": ("vehicles_transferred_by_age", ("vehicle_age",)),
    "tasit-02": ("vehicles_newly_registered", ("brand", "vehicle_type")),
    "tasit-02-yakit": ("vehicles_newly_registered_by_fuel", ("fuel",)),
    "tasit-02-silindir": ("vehicles_newly_registered_by_engine", ("engine_size",)),
    "tasit-03": ("vehicles_transferred", ("brand", "vehicle_type")),
    "tasit-04": ("cars_per_thousand", ()),
    "tasit-05": ("vehicle_mean_age", ("vehicle_type",)),
    "tasit-06": ("transferred_vehicle_mean_age", ("vehicle_type",)),
}


def value_id(dim: str, code: str) -> str | None:
    """A code's stored id: mapped for the small dims, the code itself for the rest."""
    if dim in CODES:
        return CODES[dim].get(code)
    known = load().dimensions[dim].values_tr
    return code if code in known else None


def read_label(label: str, dims: tuple[str, ...]) -> dict[str, str] | None:
    parts = SEPARATOR.sub(")\x00", label).split("\x00")
    if len(parts) != len(dims):
        return None
    out = {}
    for dim, part in zip(dims, parts):
        found = PART.match(part.strip())
        if not found:
            return None
        stored = value_id(dim, found.group(1))
        if stored is None:
            return None
        out[dim] = stored
    return out


def read_export(path: Path, indicator_id: str, dims, single) -> list[dict]:
    lines = read_text(path).splitlines()
    header = header_of(lines, single)
    if not header:
        raise KeyError(indicator_id + ": alan sutunu yok: " + path.name)

    rows: list[dict] = []
    unknown: set[str] = set()
    label = ""
    for line in lines:
        cells = line.split("|")
        if len(cells) < 4:
            continue
        stamp = cells[2].strip()
        if not (stamp.isdigit() and len(stamp) == 4):
            continue
        if cells[1].strip():
            label = cells[1].strip()
        if not dims:
            if label != "Ölçüm bazında":
                unknown.add(label)
                continue
            found = {}
        else:
            found = read_label(label, dims)
            if found is None:
                unknown.add(label)
                continue
        for index, (area_id, level) in header.items():
            cell = cells[index].strip() if index < len(cells) else ""
            if not cell:
                continue
            value = float(cell)
            if value < 0:
                # MEDAS's withheld marker (-9.98E8), never a count.
                continue
            rows.append(
                {
                    "area_id": area_id,
                    "area_level": level,
                    "year": int(stamp),
                    "dims": format_dims(found),
                    "value": value,
                }
            )
    if unknown:
        shown = sorted(unknown)
        raise KeyError(
            indicator_id
            + ": taninmayan satir etiketi ("
            + str(len(shown))
            + "): "
            + ", ".join(shown[:20])
        )
    return rows


def files_for(stem: str, level: str) -> list[Path]:
    """The plain file, or the per-year pieces of a measure taken a year at a time."""
    plain = DOWNLOADS / ("nufus-" + stem + "-" + level + ".csv")
    if plain.exists():
        return [plain]
    # By year (`-2004`) or by slice (`-3`), whichever the fetcher cut it into.
    pattern = re.compile(re.escape("nufus-" + stem + "-" + level) + r"-\d+\.csv$")
    return sorted(
        p
        for p in DOWNLOADS.glob("nufus-" + stem + "-" + level + "-*.csv")
        if pattern.match(p.name)
    )


class VehicleMeasure:
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
        single = single_province_regions()
        indicator_id, dims = self.spec
        records: list[dict] = []
        for level in ("country", "province"):
            for path in files_for(self.stem, level):
                records.extend(read_export(path, indicator_id, dims, single))
        if not records:
            raise ValueError("dosya bulunamadi ya da bos: " + self.stem)

        frame = pl.DataFrame(records)
        if frame.select("area_id", "year", "dims").is_duplicated().any():
            raise ValueError(indicator_id + ": ayni alan-yil-kirilim iki kez")

        provinces = frame.filter(pl.col("area_level") == "province")
        if provinces.height:
            expected = set(
                load_areas().filter(pl.col("area_level") == "province")["area_id"]
            )
            missing = expected - set(provinces["area_id"])
            if missing:
                raise KeyError(
                    indicator_id + ": ili olmayan: " + ", ".join(sorted(missing))
                )

        indicator = get(indicator_id)
        return frame.with_columns(
            pl.lit(indicator_id).alias("indicator_id"),
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


VEHICLE_ADAPTERS = {
    "tuik_" + spec[0]: type(
        "Tuik" + "".join(part.title() for part in spec[0].split("_")),
        (VehicleMeasure,),
        {"stem": stem, "spec": spec, "__doc__": "MEDAS motor vehicles: " + spec[0]},
    )
    for stem, spec in MEASURES.items()
}
