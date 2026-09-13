"""Crop production — MEDAS "Bitkisel Üretim İstatistikleri", country and province, yearly.

Pulled 2026-09-13 by the topic run (`bitkisel-NN`), province files in year slices
(`-province-1.csv` …). A row label is `<variable> ve [<qualifier> ve …] <code>. (<name>) -
<unit>`: `Ekilen Alan ve 01.11.12.00.00. (Buğday, Durum Buğdayı Hariç) - Dekar`. The code
is TÜİK's product code (CPA) and is what is stored; the name is the dictionary label.

One file holds several variables in different units (sown area in decares, production in
tonnes, yield in kg per decare), so each variable is its own indicator. A variable whose
unit is not the one declared here stops the load rather than being summed across units.

Not every crop grows in every province, and greenhouse fruit or dry/irrigated second
sowings exist in a handful: a province with no row is not an error here.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get, load
from ..schema import format_dims
from .tuik_median_age import single_province_regions
from .tuik_simple import read_text
from .tuik_vital import header_of

DOWNLOADS = RAW / "medas" / "basit"

LABEL = re.compile(
    r"^(?P<pre>(?:.*? ve )?)(?P<code>\d{2}(?:\.\d{2})+)\.\s*\((?P<name>.*)\)\s*-\s*(?P<unit>.+)$"
)

COVER = {
    "Alçak Tünel": "low_tunnel",
    "Yüksek Tünel": "high_tunnel",
    "Plastik Sera": "plastic_greenhouse",
    "Cam Sera": "glass_greenhouse",
}
IRRIGATION = {"Kuru": "rainfed", "Sulu": "irrigated"}
SOWING = {"Birinci Ekiliş": "first", "İkinci Ekiliş": "second"}

#: measure number → qualifier dims in label order (after the variable, before the code)
QUALIFIERS = {
    "02": (),
    "03": (),
    "04": (),
    "05": (),
    "06": (("cover_type", COVER),),
    "07": (("cover_type", COVER),),
    "08": (("cover_type", COVER),),
    "10": (("irrigation", IRRIGATION), ("sowing", SOWING)),
}

#: (measure number, variable as written, unit as written) → indicator id
INDICATORS = {
    ("02", "Ekilen Alan", "Dekar"): "field_crop_sown_area",
    ("02", "Hasat Edilen Alan", "Dekar"): "field_crop_harvested_area",
    ("02", "Üretim Miktarı", "Ton"): "field_crop_production",
    ("02", "Verim", "Kg/Dekar"): "field_crop_yield",
    ("03", "Ekilen Alan", "Dekar"): "vegetable_sown_area",
    ("03", "Üretim Miktarı", "Ton"): "vegetable_production",
    ("04", "Meyve Veren Yaşta Ağaç Sayısı", "Adet Sayısı"): "fruit_trees_bearing",
    (
        "04",
        "Meyve Vermeyen Yaşta Ağaç Sayısı",
        "Adet Sayısı",
    ): "fruit_trees_not_bearing",
    ("04", "Toplu Meyveliklerin Alanı", "Dekar"): "orchard_area",
    ("04", "Üretim Miktarı", "Ton"): "fruit_production",
    ("04", "Verim", "Kg/Dekar"): "fruit_yield_per_decare",
    ("04", "Verim", "Kg/Meyve Veren Ağaç"): "fruit_yield_per_tree",
    ("05", "Ekilen Alan", "Metrekare"): "ornamental_area",
    ("05", "Üretim Miktarı", "Adet Sayısı"): "ornamental_production",
    ("06", "Ekilen Alan", "Dekar"): "greenhouse_vegetable_area",
    ("06", "Üretim Miktarı", "Ton"): "greenhouse_vegetable_production",
    ("07", "Alan", "Dekar"): "greenhouse_fruit_area",
    ("07", "Üretim Miktarı", "Ton"): "greenhouse_fruit_production",
    ("08", "Ekilen Alan", "Metrekare"): "greenhouse_ornamental_area",
    ("08", "Üretim Miktarı", "Adet Sayısı"): "greenhouse_ornamental_production",
    ("10", "Ekilen Alan", "Dekar"): "irrigation_sown_area",
    ("10", "Hasat Edilen Alan", "Dekar"): "irrigation_harvested_area",
    ("10", "Üretim Miktarı", "Ton"): "irrigation_production",
    ("10", "Verim", "Kg/Dekar"): "irrigation_yield",
}


def files_of(raw: Path, number: str) -> list[Path]:
    out = []
    for level in ("country", "province"):
        plain = raw / f"nufus-bitkisel-{number}-{level}.csv"
        sliced = sorted(
            p
            for p in raw.glob(f"nufus-bitkisel-{number}-{level}-*.csv")
            if re.fullmatch(r"\d+", p.stem.rsplit("-", 1)[1])
        )
        out.extend([plain] if plain.exists() else sliced)
    return out


def read_export(path: Path, number: str, single: dict[str, str]) -> list[dict]:
    lines = read_text(path).splitlines()
    header = header_of(lines, single)
    if not header:
        raise KeyError("bitkisel-" + number + ": alan sutunu yok: " + path.name)
    crops = load().dimensions["crop"].values_tr
    rows, unknown, label = [], set(), ""
    for line in lines:
        cells = line.split("|")
        if len(cells) < 4 or not re.fullmatch(r"\d{4}", cells[2].strip()):
            continue
        label = cells[1].strip() or label
        found = LABEL.match(label)
        if not found:
            unknown.add(label)
            continue
        parts = [p.strip() for p in found.group("pre").split(" ve ") if p.strip()]
        variable, qualifiers = parts[0], parts[1:]
        indicator_id = INDICATORS.get((number, variable, found.group("unit").strip()))
        spec = QUALIFIERS[number]
        code = found.group("code")
        if indicator_id is None or len(qualifiers) != len(spec) or code not in crops:
            unknown.add(label)
            continue
        dims = {"crop": code}
        for (dim, values), text in zip(spec, qualifiers):
            if text not in values:
                unknown.add(label)
                break
            dims[dim] = values[text]
        else:
            for index, (area_id, level) in header.items():
                cell = cells[index].strip() if index < len(cells) else ""
                if not cell:
                    continue
                value = float(cell)
                if value <= -9e8:
                    continue
                rows.append(
                    {
                        "indicator_id": indicator_id,
                        "area_id": area_id,
                        "area_level": level,
                        "year": int(cells[2]),
                        "dims": format_dims(dims),
                        "value": value,
                    }
                )
    if unknown:
        raise KeyError(
            "bitkisel-"
            + number
            + ": taninmayan etiket ("
            + str(len(unknown))
            + "): "
            + ", ".join(sorted(unknown)[:5])
        )
    return rows


class CropMeasure:
    source_id = "tuik_medas"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 13)
    indicator_id = ""
    number = ""

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        single = single_province_regions()
        records = [
            row
            for path in files_of(raw, self.number)
            for row in read_export(path, self.number, single)
            if row["indicator_id"] == self.indicator_id
        ]
        if not records:
            raise ValueError("dosya bulunamadi ya da bos: " + self.indicator_id)
        frame = pl.DataFrame(records)
        if frame.select("area_id", "year", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni alan-yil-kirilim iki kez")
        indicator = get(self.indicator_id)
        return frame.with_columns(
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


CROP_ADAPTERS = {
    "tuik_" + ident: type(
        "Tuik" + "".join(part.title() for part in ident.split("_")),
        (CropMeasure,),
        {"indicator_id": ident, "number": number},
    )
    for (number, _variable, _unit), ident in INDICATORS.items()
}
