"""Municipal water, wastewater and waste, and electricity — MEDAS, country and province.

Pulled 2026-09-13 (`C:/veri-ham/medas_belediye_enerji.py`), one file per measure and
level, transposed like the vital exports: areas across the header, one row per breakdown
value per year. Unlike those, the row label is the *bare* value (`Baraj`, `1. (Mesken)`),
with no "breakdown:" prefix to read — so each measure names its one breakdown here and
maps every Turkish value to an id (K1). A value the map does not know stops the load.

Surveys are irregular: water and wastewater 2001-2004 then every second year to 2022,
waste to 2024, electricity consumption by province 2000-2024, generation and installed
capacity for Türkiye only (1970-2024).

"Toplam belediye sayısı" is published under all three municipal topics; it is loaded
once, from the waste topic, whose series is the longest.

Province rows sum to the Türkiye row in every additive measure and year, with one
exception that is TÜİK's own: wastewater discharged untreated into rivers in 2014, where
the provinces exceed the country by 43.993 thousand m³ (9%). Both are kept as published.
"""

from __future__ import annotations

import datetime as dt
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

WATER_SOURCE = {
    "Akarsu": "river",
    "Baraj": "dam",
    "Deniz": "sea",
    "Göl": "lake",
    "Gölet": "pond",
    "Kaynak": "spring",
    "Kuyu": "well",
}
PHYSICAL = (
    "Fiziksel Arıtma (İnce Ve Kaba Izgaralar, Elekler, Kum Tutucu, Yağ Tutucu, "
    "Ön Çöktürme Tankı, Dengeleme Havuzu Vb.)"
)
WATER_TREATMENT = {
    PHYSICAL: "physical",
    "Konvansiyonel Arıtma": "conventional",
    "Gelişmiş Arıtma": "advanced",
}
WASTEWATER_TREATMENT = {
    PHYSICAL: "physical",
    "Biyolojik Arıtma": "biological",
    "Gelişmiş Arıtma": "advanced",
    "Doğal Arıtma (Yapay Sulak Alan)": "natural",
}
RECEIVING_BODY = {
    "Akarsu (Nehir, Dere, Çay)": "river",
    "Arazi": "land",
    "Baraj": "dam",
    "Deniz": "sea",
    "Diğer": "other",
    "Göl": "lake",
    "Gölet": "pond",
}
TREATED = {"Arıtılıyor": "yes", "Arıtılmıyor": "no"}
DISPOSAL = {
    "Açıkta Yakma": "open_burning",
    "Başka Belediye Çöplüğünde Depolama": "other_municipality_dump",
    "Belediye Çöplüğünde Depolama": "municipal_dump",
    "Büyükşehir Belediye Çöplüğünde Depolama": "metropolitan_dump",
    "Diğer Bertaraf İşlemleri": "other_disposal",
    "Diğer Geri Kazanım İşlemleri": "other_recovery",
    "Düzenli Depolama": "sanitary_landfill",
    "Gömme": "burying",
    "Kompost Tesisine Gönderilen": "composting",
    "Lisanslı Firmalara Gönderilen": "licensed_firms",
    "Nehir, Dere Ve Göle Dökme": "dumping_into_water",
}
CONSUMER = {
    "1. (Mesken)": "residential",
    "2. (Ticaret Ve Kamu Hizmetleri)": "commercial_public",
    "3. (Sanayi)": "industrial",
    "4. (Tarımsal Faaliyetler)": "agricultural",
    "5. (Aydınlatma)": "lighting",
}
ENERGY_SOURCE = {
    "Doğal Gaz": "natural_gas",
    "Hidroelektrik Enerji": "hydro",
    "Kömür Ve Kömür Türevleri": "coal",
    "Sıvı Yakıt": "liquid_fuel",
    "Yenilenebilir Enerji Ve Atıklar": "renewables_waste",
}


def receiving(label: str) -> dict[str, str] | None:
    """`Deniz ve Arıtılıyor` → receiving body and treated, two dims from one label."""
    body, _, treated = label.rpartition(" ve ")
    if body in RECEIVING_BODY and treated in TREATED:
        return {"receiving_body": RECEIVING_BODY[body], "treated": TREATED[treated]}
    return None


def one(dim: str, values: dict[str, str]):
    def read(label: str) -> dict[str, str] | None:
        return {dim: values[label]} if label in values else None

    return read


#: file stem → (indicator id, label reader or None for the single `Ölçüm bazında` row).
MEASURES = {
    "belediye-atik-01": ("municipalities", None),
    "belediye-su-02": ("water_network_municipalities", None),
    "belediye-su-03": ("water_network_population", None),
    "belediye-su-04": ("water_network_population_share", None),
    "belediye-su-05": ("water_abstracted", one("water_source", WATER_SOURCE)),
    "belediye-su-06": ("water_abstracted_per_capita", None),
    "belediye-su-07": ("water_treatment_plants", one("treatment", WATER_TREATMENT)),
    "belediye-su-08": ("water_treatment_capacity", one("treatment", WATER_TREATMENT)),
    "belediye-su-09": ("water_treated", one("treatment", WATER_TREATMENT)),
    "belediye-su-10": ("water_treatment_municipalities", None),
    "belediye-su-11": ("water_treatment_population", None),
    "belediye-su-12": ("water_treatment_population_share", None),
    "belediye-su-13": ("water_distribution_municipalities", None),
    "belediye-su-14": ("water_subscribers", None),
    "belediye-su-15": ("water_distributed", None),
    "belediye-atiksu-02": ("sewer_municipalities", None),
    "belediye-atiksu-03": ("sewer_population", None),
    "belediye-atiksu-04": ("sewer_population_share", None),
    "belediye-atiksu-05": ("wastewater_discharged", receiving),
    "belediye-atiksu-06": ("wastewater_plants", one("treatment", WASTEWATER_TREATMENT)),
    "belediye-atiksu-07": (
        "wastewater_plant_capacity",
        one("treatment", WASTEWATER_TREATMENT),
    ),
    "belediye-atiksu-08": (
        "wastewater_treated",
        one("treatment", WASTEWATER_TREATMENT),
    ),
    "belediye-atiksu-09": ("wastewater_treatment_municipalities", None),
    "belediye-atiksu-10": ("wastewater_treatment_population", None),
    "belediye-atiksu-11": ("wastewater_treatment_population_share", None),
    "belediye-atiksu-12": ("wastewater_per_capita", None),
    "belediye-atik-02": ("waste_service_municipalities", None),
    "belediye-atik-03": ("waste_service_population", None),
    "belediye-atik-04": ("waste_service_population_share", None),
    "belediye-atik-05": ("waste_collected", None),
    "belediye-atik-06": ("waste_per_capita", None),
    "belediye-atik-07": ("waste_by_disposal", one("disposal", DISPOSAL)),
    "belediye-atik-08": ("municipalities_by_disposal", one("disposal", DISPOSAL)),
    "enerji-01": ("electricity_consumption", one("consumer", CONSUMER)),
    "enerji-02": ("electricity_consumption_per_capita", one("consumer", CONSUMER)),
    "enerji-03": ("electricity_generation", one("energy_source", ENERGY_SOURCE)),
    "enerji-04": ("installed_capacity", None),
}


#: Treatment-plant measures: a province with no plant in any surveyed year has no row at
#: all (checked 2026-09-13 — water treatment: Bingöl, Burdur, Kayseri, Malatya, Muş,
#: Tunceli, Osmaniye; wastewater: Ağrı, Hakkari, and Şırnak for the served-population
#: measures). Every other measure must cover all 81 provinces.
NO_PLANT_NO_ROW = {
    "water_treatment_plants",
    "water_treatment_capacity",
    "water_treated",
    "water_treatment_municipalities",
    "water_treatment_population",
    "water_treatment_population_share",
    "wastewater_plants",
    "wastewater_plant_capacity",
    "wastewater_treated",
    "wastewater_treatment_municipalities",
    "wastewater_treatment_population",
    "wastewater_treatment_population_share",
}


def read_export(path: Path, spec: tuple, single: dict[str, str]) -> list[dict]:
    indicator_id, reader = spec
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
        if reader is None:
            if label != "Ölçüm bazında":
                unknown.add(label)
                continue
            dims = ""
        else:
            found = reader(label)
            if found is None:
                unknown.add(label)
                continue
            dims = format_dims(found)
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
                    "dims": dims,
                    "value": value,
                }
            )
    if unknown:
        raise KeyError(
            indicator_id + ": taninmayan satir etiketi: " + ", ".join(sorted(unknown))
        )
    return rows


class MunicipalMeasure:
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
        records: list[dict] = []
        for level in ("country", "province"):
            path = raw / ("nufus-" + self.stem + "-" + level + ".csv")
            if path.exists():
                records.extend(read_export(path, self.spec, single))
        if not records:
            raise ValueError("dosya bulunamadi ya da bos: " + self.stem)

        frame = pl.DataFrame(records)
        if frame.select("area_id", "year", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni alan-yil-kirilim iki kez")

        provinces = frame.filter(pl.col("area_level") == "province")
        if provinces.height:
            expected = set(
                load_areas().filter(pl.col("area_level") == "province")["area_id"]
            )
            missing = expected - set(provinces["area_id"])
            if missing and self.indicator_id in NO_PLANT_NO_ROW:
                print(
                    "   ",
                    self.indicator_id,
                    "· tesisi olmayan il (satir yok):",
                    ", ".join(sorted(missing)),
                )
            elif missing:
                raise KeyError(
                    self.indicator_id + ": ili olmayan: " + ", ".join(sorted(missing))
                )

        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
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


MUNICIPAL_ADAPTERS = {
    "tuik_" + spec[0]: type(
        "Tuik" + "".join(part.title() for part in spec[0].split("_")),
        (MunicipalMeasure,),
        {"stem": stem, "spec": spec, "__doc__": "MEDAS municipal/energy: " + spec[0]},
    )
    for stem, spec in MEASURES.items()
}
