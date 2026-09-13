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
from ..indicators import get, load
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
    "origin": {"Yerli": "domestic", "Yabancı": "foreign"},
    "sale_financing": {"İpotekli Satış": "mortgaged", "Diğer Satış": "other"},
    "sale_hand": {"İlk Satış": "first", "İkinci El Satış": "second_hand"},
    # Nine leaves that partition "Binalar" exactly (checked every year, all twelve
    # measures); the three subtotals map to "" and are skipped.
    "building_use": {
        "Binalar": "",
        "İkamet Amaçlı Binalar": "",
        "İkamet Amaçlı Olmayan Binalar": "",
        "Bir Daireli Binalar": "residential_single",
        "İki Ve Daha Fazla Daireli Binalar": "residential_multi",
        "Halka Açık İkamet Yerleri": "residential_communal",
        "Otel Vb. Binalar": "hotel",
        "Ofis (İşyeri) Binaları": "office",
        "Toptan Ve Perakende Ticaret Binaları": "retail",
        "Trafik Ve İletişim Binaları": "transport_communication",
        "Sanayi Binaları Ve Depolar": "industrial_storage",
        "Kamu Eğlence, Eğitim, Hastane Veya Bakım Kuruluşları Binaları": "public_education_health",
        "İkamet Amaçlı Binalar Dışındaki Diğer Binalar": "other_non_residential",
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
    "kutuphane-01": ("public_libraries", ()),
    "kutuphane-02": ("public_library_books", ()),
    "kutuphane-03": ("public_library_users", ()),
    "kutuphane-04": ("ministry_museums", ()),
    "kutuphane-05": ("ministry_museum_artefacts", ()),
    "kutuphane-06": ("ministry_museum_visitors", ()),
    "kutuphane-07": ("private_museums", ()),
    "kutuphane-08": ("private_museum_artefacts", ()),
    "kutuphane-09": ("private_museum_visitors", ()),
    "kutuphane-10": ("archaeological_sites", ()),
    "kutuphane-11": ("library_uses_per_thousand", ()),
    "kutuphane-12": ("library_loans", ()),
    "kutuphane-13": ("private_museum_staff", ()),
    "sinema-01": ("cinema_halls", ()),
    "sinema-02": ("cinema_seats", ()),
    "sinema-03": ("films_shown", ("origin",)),
    "sinema-04": ("cinema_audience", ("origin",)),
    "tiyatro-01": ("theatre_halls", ()),
    "tiyatro-02": ("theatre_seats", ()),
    "tiyatro-03": ("theatre_works", ("origin",)),
    "tiyatro-04": ("theatre_performances", ("origin",)),
    "tiyatro-05": ("theatre_audience", ("origin",)),
    "intihar-02": ("suicide_rate", ()),
    "cocuk-demografi-02": ("child_population_share", ("sex",)),
    "cocuk-demografi-03": ("child_population_growth", ("sex",)),
    "cocuk-demografi-04": ("child_sex_ratio", ()),
    "cocuk-demografi-05": ("child_dependency_ratio", ()),
    "cocuk-demografi-10": ("foreign_born_children", ("sex",)),
    "cocuk-demografi-12": ("child_marriages", ("sex",)),
    "cocuk-demografi-13": ("child_marriage_share", ("sex",)),
    "cocuk-demografi-14": ("children_in_custody_cases", ()),
    "cocuk-demografi-16": ("households_with_children", ()),
    "cocuk-demografi-17": ("single_parent_households_with_children", ()),
    "cocuk-demografi-18": ("children_in_single_parent_households", ("sex",)),
    "cocuk-demografi-19": ("foreign_national_children", ("sex",)),
    "cocuk-saglik-03": ("facility_birth_share", ()),
    "cocuk-saglik-04": ("births_to_child_mothers", ()),
    "cocuk-saglik-05": ("maternal_mortality", ()),
    "cocuk-saglik-06": ("caesarean_share", ()),
    "cocuk-saglik-07": ("adolescent_birth_share", ()),
    "cocuk-saglik-09": ("dtap3_vaccination", ()),
    "cocuk-saglik-13": ("neonatal_mortality", ("sex",)),
    "cocuk-saglik-14": ("postneonatal_mortality", ("sex",)),
    "cocuk-saglik-19": ("child_suicide_rate", ("sex",)),
    "cocuk-egitim-01": ("preschool_gross_enrolment", ("sex",)),
    "cocuk-egitim-02": ("preschool_net_enrolment", ("sex",)),
    "cocuk-egitim-13": ("children_in_after_school_care", ()),
    "cocuk-egitim-14": ("children_in_daycare", ()),
    "cocuk-egitim-15": ("children_cared_at_home", ()),
    "konut-satis-01": ("housing_sales", ("sale_financing", "sale_hand")),
    "hayvan-01": ("livestock", ("livestock",)),
    "hayvan-02#ton": ("animal_products_tonnes", ("animal_product",), "Ton"),
    "hayvan-02#kovan": ("beehives", ("animal_product",), "Kovan Sayısı"),
    "hayvan-02#kutu": ("silkworm_boxes", (), "Kutu"),
    "hayvan-03": ("beekeeping_holdings", ()),
    "hayvan-04": ("sericulture_villages", ()),
    "hayvan-05": ("sericulture_holdings", ()),
    "hayvan-06": ("broilers", ()),
    "hayvan-07": ("laying_hens", ()),
    "hayvan-08": ("other_poultry", ("poultry",)),
    "hayvan-09": ("shorn_animals", ("livestock_group",)),
    "hayvan-10": ("milked_animals", ("livestock_group",)),
    "hayvan-11": ("large_livestock", ()),
    "hayvan-12": ("small_livestock", ()),
    "hayvan-13": ("raw_milk", ("animal_product",)),
    "hayvan-14": ("cattle", ()),
    "hayvan-15": ("buffalo", ()),
    "hayvan-16": ("sheep", ()),
    "hayvan-17": ("goats", ()),
    **{
        f"yapi-izin-{n:02d}": (f"{kind}_{what}", ("building_use",))
        for n, (kind, what) in enumerate(
            [
                (kind, what)
                for kind in ("permit", "occupancy")
                for what in (
                    "buildings",
                    "floor_area",
                    "dwellings",
                    "residential_area",
                    "other_area",
                    "common_area",
                )
            ],
            start=1,
        )
    },
}


SUBTOTAL: dict[str, str] = {"": ""}

#: Sericulture is practised in a few dozen provinces; the rest have no column at all.
NOT_EVERY_PROVINCE = {"silkworm_boxes", "sericulture_villages", "sericulture_holdings"}


def part_name(part: str) -> str:
    """`Araç türü:1. (Otomobil)` → `Otomobil`; `Erkek` stays `Erkek`."""
    part = part.strip()
    if ":" in part and not part.startswith("Hastane"):
        part = part.split(":", 1)[1].strip()
    found = CODED.match(part)
    if found:
        part = found.group(1)
    return " ".join(part.split())


#: Dims stored by TÜİK product code (`01.41.10.01.01`); names are dictionary labels.
CODE_DIMS = {"livestock", "animal_product", "poultry", "livestock_group"}
PRODUCT = re.compile(r"^([\d.]+?)\.?\s*\((.*)\)$")


def read_label(label: str, dims: tuple[str, ...]) -> dict[str, str] | None:
    parts = label.split(" ve ")
    if len(parts) != len(dims):
        return None
    out = {}
    for dim, part in zip(dims, parts):
        if dim in CODE_DIMS:
            found = PRODUCT.match(part.strip())
            code = found.group(1).rstrip(".") if found else ""
            if code not in load().dimensions[dim].values_tr:
                return None
            out[dim] = code
            continue
        stored = NAMES[dim].get(part_name(part))
        if stored is None:
            return None
        out[dim] = stored
    # An empty id is a known subtotal row, skipped so the stored values partition.
    return SUBTOTAL if "" in out.values() else out


def read_export(
    path: Path, indicator_id: str, dims, single, unit: str = ""
) -> list[dict]:
    """`unit`: keep only rows whose label ends in " ve <unit>" and drop that part.

    "Hayvansal üretim" puts tonnes, hives and silkworm boxes in one table, told apart
    only by the last part of the label; each becomes its own indicator.
    """
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
        if unit:
            head, _, tail = label.rpartition(" ve ")
            if tail.strip() != unit:
                continue
            if not dims:
                label = "Ölçüm bazında"
            else:
                found = read_label(head, dims)
                if found is None:
                    unknown.add(label)
                    continue
        if unit and dims:
            pass
        elif not dims:
            if label != "Ölçüm bazında":
                unknown.add(label)
                continue
            found = {}
        else:
            found = read_label(label, dims)
            if found is None:
                unknown.add(label)
                continue
            if found is SUBTOTAL:
                continue
        for index, (area_id, level) in header.items():
            cell = cells[index].strip() if index < len(cells) else ""
            if not cell:
                continue
            value = float(cell)
            if value <= -9e8:
                # MEDAS's withheld marker (-9.98E8). Not `< 0`: a growth rate is
                # negative in a shrinking province, and eleven provinces lost theirs.
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
        indicator_id, dims, *rest = self.spec
        unit = rest[0] if rest else ""
        stem = self.stem.split("#")[0]
        records: list[dict] = []
        for level in ("country", "province"):
            plain = raw / ("nufus-" + stem + "-" + level + ".csv")
            # A measure over the cell limit comes in numbered slices (`-province-1.csv`).
            sliced = sorted(
                p
                for p in raw.glob("nufus-" + stem + "-" + level + "-*.csv")
                if re.fullmatch(r"\d+", p.stem.rsplit("-", 1)[1])
            )
            for path in [plain] if plain.exists() else sliced:
                records.extend(read_export(path, indicator_id, dims, single, unit))
        if not records:
            raise ValueError("dosya bulunamadi ya da bos: " + self.stem)

        frame = pl.DataFrame(records)
        # Deaths within 30 days were not counted before 2015 (country 0 in 2012, 2.768
        # men in 2024); the export writes those years as zeros. A zero there is "not
        # collected", so the rows go rather than reading as nobody dying.
        if indicator_id == "road_deaths":
            later = pl.col("dims").str.contains("death_timing=within_30_days")
            empty = (
                frame.filter(later & (pl.col("area_level") == "country"))
                .group_by("year")
                .agg(pl.col("value").sum())
                .filter(pl.col("value") == 0)["year"]
            )
            frame = frame.filter(~(later & pl.col("year").is_in(empty.implode())))
        if frame.select("area_id", "year", "dims").is_duplicated().any():
            raise ValueError(indicator_id + ": ayni alan-yil-kirilim iki kez")

        provinces = frame.filter(pl.col("area_level") == "province")
        if provinces.height:
            expected = set(
                load_areas().filter(pl.col("area_level") == "province")["area_id"]
            )
            missing = expected - set(provinces["area_id"])
            if missing and indicator_id in NOT_EVERY_PROVINCE:
                print("   ", indicator_id, "· faaliyet olmayan il:", len(missing))
            elif missing:
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
