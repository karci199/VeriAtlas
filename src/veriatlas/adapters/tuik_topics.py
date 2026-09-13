"""Health and road-accident measures — MEDAS topic runs, country and province, yearly.

Pulled 2026-09-13 by `scripts/fetch_medas_topic.py` (`saglik-NN`, `trafik-NN`), every
breakdown on. The same transposed export as the vehicle and municipal files, but the row
labels come in three spellings within one topic: coded (`1. (Uzman Hekim) ve 2.
(Üniversite)`), bare (`Erkek ve Yaya`) and prefixed (`Araç türü:1. (Otomobil)`). Each
part is reduced to its name and looked up; an unknown name stops the load.

"Every breakdown on" is again not every breakdown: deaths came back as sex × time of death
only, injured as sex × road user only. The dims below are what the files hold, not what
the survey listed.
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
from .tuik_median_age import single_province_regions
from .tuik_simple import read_text
from .tuik_vital import header_of

DOWNLOADS = RAW / "medas" / "basit"

CODED = re.compile(r"^\d+\.\s*\((.*)\)$")

#: dim → Turkish name as MEDAS writes it → stored id.
NAMES = {
    "hospital_sector": {
        "Hastane (Sağlık Bakanlığı)": "ministry",
        "Hastane (Özel)": "private",
        "Hastane (Üniversite)": "university",
        "Diğer": "other",
    },
    "health_sector": {
        "Sağlık Bakanlığı": "ministry",
        "Üniversite": "university",
        "Özel": "private",
    },
    "health_profession": {
        "Uzman Hekim": "specialist",
        "Pratisyen Hekim": "general_practitioner",
        "Asistan Hekim": "resident",
        "Diş Hekimi": "dentist",
        "Hemşire": "nurse",
        "Ebe": "midwife",
        "Eczacı": "pharmacist",
        "Diğer Sağlık Personeli": "other",
    },
    "facility_type": {
        "Yataklı Sağlık Kurumları": "inpatient",
        "Yataksız Sağlık Kurumları": "outpatient",
    },
    "accident_location": {
        "Yerleşim Yeri": "inside_settlement",
        "Yerleşim Yeri Dışı": "outside_settlement",
    },
    "sex": {"Erkek": "male", "Kadın": "female"},
    "death_timing": {
        "Kaza Yerinde": "at_scene",
        "Kaza Sonrası (30 Gün)": "within_30_days",
    },
    "road_user": {"Sürücü": "driver", "Yolcu": "passenger", "Yaya": "pedestrian"},
    "vehicle_type": {
        "Otomobil": "car",
        "Minibüs": "minibus",
        "Otobüs": "bus",
        "Kamyonet": "pickup",
        "Kamyon": "truck",
        "Motosiklet": "motorcycle",
        "Traktör": "tractor",
        "Çekici": "tractor_unit",
        "Diğer": "other",
    },
}

#: file stem → (indicator id, dims in label order).
MEASURES = {
    "saglik-01": ("hospitals", ("hospital_sector",)),
    "saglik-02": ("hospital_beds", ("hospital_sector",)),
    "saglik-03": ("health_staff", ("health_profession", "health_sector")),
    "saglik-04": ("health_facilities", ("facility_type",)),
    "saglik-05": ("visits_per_doctor", ()),
    "saglik-06": ("hospital_beds_per_100k", ()),
    "saglik-07": ("doctors_per_thousand", ()),
    "trafik-01": ("driving_licence_holders", ()),
    "trafik-02": ("injury_accidents", ("accident_location",)),
    "trafik-03": ("road_deaths", ("sex", "death_timing")),
    "trafik-04": ("road_injured", ("sex", "road_user")),
    "trafik-05": ("vehicles_in_injury_accidents", ("vehicle_type",)),
    "trafik-06": ("accidents_per_million", ()),
    "trafik-07": ("road_deaths_per_million", ()),
    "trafik-08": ("road_injured_per_million", ()),
    "trafik-09": ("road_deaths_per_million_vehicles", ()),
    "trafik-10": ("road_injured_per_million_vehicles", ()),
    "trafik-11": ("road_deaths_per_million_cars", ()),
    "trafik-12": ("road_injured_per_million_cars", ()),
}


def part_name(part: str) -> str:
    """`Araç türü:1. (Otomobil)` → `Otomobil`; `Erkek` stays `Erkek`."""
    part = part.strip()
    if ":" in part and not part.startswith("Hastane"):
        part = part.split(":", 1)[1].strip()
    found = CODED.match(part)
    if found:
        part = found.group(1)
    return " ".join(part.split())


def read_label(label: str, dims: tuple[str, ...]) -> dict[str, str] | None:
    parts = label.split(" ve ")
    if len(parts) != len(dims):
        return None
    out = {}
    for dim, part in zip(dims, parts):
        stored = NAMES[dim].get(part_name(part))
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
        raise KeyError(
            indicator_id + ": taninmayan satir etiketi: " + ", ".join(sorted(unknown))
        )
    return rows


class TopicMeasure:
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
            path = raw / ("nufus-" + self.stem + "-" + level + ".csv")
            if path.exists():
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


TOPIC_ADAPTERS = {
    "tuik_" + spec[0]: type(
        "Tuik" + "".join(part.title() for part in spec[0].split("_")),
        (TopicMeasure,),
        {
            "stem": stem,
            "spec": spec,
            "__doc__": "MEDAS health/road accidents: " + spec[0],
        },
    )
    for stem, spec in MEASURES.items()
}
