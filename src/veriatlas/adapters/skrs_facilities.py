r"""Health facilities by district, from the Ministry of Health code server (SKRS).

`scripts/fetch_skrs_institutions.py` reads SKRS's institution list province by province:
every active institution with a ministry code, its district and its type. The yearbook
(`moh_*`) stops at province; this is the first district-level count of hospitals, family
health centres and family medicine units in the warehouse.

**A snapshot, not a series.** The list shows what is active on the day it is read and
returns no closed institutions, so there is no history to rebuild. Rows are filed under
the snapshot's year and replaced on a refetch, like `pharmacies`.

**What the kinds mean.** SKRS's own "Kurum Türü" is mapped onto a short list; everything
else (opticians, device shops, OSGB, sub-units of hospitals, administrative offices, ...)
is read and deliberately not stored. The mapping is `KINDS`; an unmapped type is fine,
a *new hospital-looking* type is not — see `HOSPITAL_WORDS`.

* `family_medicine_unit` — one family physician's post (AHB), filled or vacant. The
  number of AHBs is effectively the number of family-physician posts.
* `family_health_centre` — the building (ASM) that houses several AHBs; what used to be
  the "sağlık ocağı".
* Hospitals are split by who runs them and checked against TÜİK's 2024 sector counts
  (docs/saglik.md): ministry 930 vs 941, university 72 vs 69, private 510 vs 552.
  Two SKRS types are *not* hospitals in that sense and are left out of the hospital kinds:
  `EĞİTİM HASTANESİ` (the separately coded buildings inside a city-hospital campus —
  Bilkent alone has six) and dental hospitals, which go to `oral_health_centre`.
  University rows (SUAM) include dental teaching centres; those are recognised by their
  "Kurum Tipi" and moved the same way.

**Districts.** The register writes district names in capitals; they are matched to the
area registry with Turkish-aware upper-casing. The province is always the one queried,
never the row's own label. `M.KEMALPAŞA` and `ONDOKUZMAYIS` are this source's own spellings. Rows whose
district is `MERKEZ` in a metropolitan province, `Bilinmiyor` or `YOK` — provincial
offices with no district — count towards the province and no district; their number is
checked against `MAX_UNPLACED` so a matching failure cannot hide among them.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import polars as pl

from ..areas import DISTRICT_ALIASES, load_areas, load_districts
from ..config import RAW
from ..schema import format_dims

FOLDER = RAW / "skrs"
SOURCE_ID = "skrs"
VINTAGE = "2026-09"
RETRIEVED = dt.date(2026, 9, 25)
SNAPSHOT = dt.date(2026, 9, 25)

MINISTRY_HOSPITALS = {
    "DEVLET HASTANESİ",
    "ENTEGRE İLÇE HASTANESİ",
    "SB+SBÜ",
    "SB+Üniversite",
    "FİZİK TED. ve REHABİLİTASYON HASTANESİ",
    "RUH SAĞLIĞI HASTALIKLARI HASTANESİ",
    "GÖĞÜS HASTALIKLARI HASTANESİ",
    "KADIN, DOĞUM VE ÇOCUK HAST. HASTANESİ",
    "ÇOCUK HASTALIKLARI HASTANESİ",
    "MESLEK HASTALIKLARI HASTANESİ",
    "ONKOLOJİ HASTANESİ",
    "LEPRA HASTANESİ",
    "KEMİK HASTALIKLARI HASTANESİ",
}
UNIVERSITY_HOSPITALS = {
    "Devlet Üniversitesi SUAM",
    "Vakıf Üniversitesi SUAM",
    "Tıp Fakültesi Hastanesi",
}
KINDS = {
    **dict.fromkeys(MINISTRY_HOSPITALS, "hospital_ministry"),
    **dict.fromkeys(UNIVERSITY_HOSPITALS, "hospital_university"),
    "Özel Hastane": "hospital_private",
    "Vakıf Üniversitesi+Özel": "hospital_private",
    "Belediye Bünyesinde Hastane": "hospital_other",
    "AİLE SAĞLIĞI MERKEZİ": "family_health_centre",
    "AİLE HEKİMLİĞİ BİRİMİ": "family_medicine_unit",
    "YETKİLENDİRİLMİŞ AİLE HEKİMLİĞİ BİRİMİ": "family_medicine_unit",
    "SAĞLIK EVİ": "health_post",
    "TOPLUM SAĞLIĞI MERKEZİ": "community_health_centre",
    "112 İSTASYONLARI": "emergency_station",
    "Diyaliz Merkezi": "dialysis_centre",
    "Diyaliz": "dialysis_centre",
    "DİYALİZ MERKEZİ": "dialysis_centre",
    "AĞIZ VE DİŞ SAĞLIĞI MERKEZİ": "oral_health_centre",
    "Ağız ve Diş Sağlığı Merkezi": "oral_health_centre",
    "AĞIZ VE DİŞ SAĞLIĞI HASTANESİ": "oral_health_centre",
    "Diş Hekimliği Fakültesi Hastanesi": "oral_health_centre",
    "Tıp Merkezi": "medical_centre",
    "Poliklinik": "polyclinic",
    "SEMT POLİKLİNİĞİ": "polyclinic",
    "GÖÇMEN SAĞLIĞI MERKEZİ": "migrant_health_centre",
    "GÜÇLENDİRİLMİŞ GÖÇMEN SAĞLIĞI MERKEZİ": "migrant_health_centre",
    "Sağlıklı Hayat Merkezi": "healthy_life_centre",
    "Tıbbi Laboratuvar": "laboratory",
    "Muayenehaneler (ADSM ve Genel)": "private_practice",
    "Optisyenlik Müesseseleri": "optician",
}
#: SKRS types that look like hospitals but are not counted as one — see the module note.
NOT_HOSPITALS = {"EĞİTİM HASTANESİ", "Tıp Fakültesi (Hastanesi Olmayan-Vakıf)"}
HOSPITAL_WORDS = ("HASTANE", "Hastane")
#: University rows whose "Kurum Tipi" is a dental centre, not a hospital.
DENTAL_TYPES = ("Ağız ve Diş", "Diş Hekimliği")

UNPLACED = {"MERKEZ", "BİLİNMİYOR", "YOK", "MERKEZTEŞKİLAT"}
MAX_UNPLACED = 200
#: This source's own spellings, keyed like `areas.DISTRICT_ALIASES`.
SOURCE_ALIASES = {
    ("TR-16", "M.KEMALPAŞA"): "Mustafakemalpaşa",
    ("TR-55", "ONDOKUZMAYIS"): "19 Mayıs",
}


def upper_tr(text: str) -> str:
    """Turkish upper case with circumflexes and spaces removed, for name matching only."""
    text = text.replace("i", "İ").replace("ı", "I").upper()
    for accented, plain in (("Â", "A"), ("Î", "I"), ("Û", "U")):
        text = text.replace(accented, plain)
    return text.replace(" ", "")


def district_index() -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    provinces = {
        row["area_id"]: row["name_tr"]
        for row in load_areas()
        .filter(pl.col("area_level") == "province")
        .iter_rows(named=True)
    }
    index = {
        (row["parent_id"], upper_tr(row["name_tr"])): row["area_id"]
        for row in load_districts().iter_rows(named=True)
    }
    for (province, spelling), name in {**DISTRICT_ALIASES, **SOURCE_ALIASES}.items():
        index[(province, upper_tr(spelling))] = index[(province, upper_tr(name))]
    return provinces, index


def place(
    province_id: str,
    district: str,
    provinces: dict[str, str],
    index: dict[tuple[str, str], str],
) -> str | None:
    """The district's area id; None for a row the register gives no district."""
    key = upper_tr(district)
    if key == "MERKEZ" and (province_id, upper_tr(provinces[province_id])) in index:
        key = upper_tr(provinces[province_id])
    area = index.get((province_id, key))
    if area is None and key not in UNPLACED:
        raise KeyError(f"kayıt defterinde olmayan ilçe: {province_id} / {district!r}")
    return area


def kind_of(row: dict) -> str | None:
    source_type = row["Kurum Türü"]
    kind = KINDS.get(source_type)
    if kind == "hospital_university" and row["Kurum Tipi"].startswith(DENTAL_TYPES):
        return "oral_health_centre"
    if (
        kind is None
        and source_type not in NOT_HOSPITALS
        and any(word in source_type for word in HOSPITAL_WORDS)
    ):
        raise ValueError(f"sınıflanmamış hastane türü: {source_type!r}")
    return kind


def dump() -> Path:
    found = sorted(FOLDER.glob("saglik_tesisleri_*.csv"))
    if not found:
        raise FileNotFoundError(f"SKRS sağlık tesisi dökümü yok: {FOLDER}")
    return found[-1]


class SkrsHealthFacilities:
    indicator_id = "health_facility_register"
    source_id = SOURCE_ID

    def fetch(self) -> Path:
        return dump()

    def parse(self, raw: Path) -> pl.DataFrame:
        provinces, index = district_index()
        districts: dict[tuple[str, str], int] = {}
        province_totals: dict[tuple[str, str], int] = {}
        unplaced = 0
        seen: set[str] = set()
        with raw.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["Kodu"] in seen:
                    raise ValueError(f"çift kurum kodu: {row['Kodu']}")
                seen.add(row["Kodu"])
                if row["Durum"] != "Aktif":
                    continue
                kind = kind_of(row)
                if kind is None:
                    continue
                province_id = f"TR-{int(row['sorgu_il_kodu']):02d}"
                key = (province_id, kind)
                province_totals[key] = province_totals.get(key, 0) + 1
                area = place(province_id, row["İlçe Adı"], provinces, index)
                if area is None:
                    unplaced += 1
                    continue
                districts[(area, kind)] = districts.get((area, kind), 0) + 1
        if unplaced > MAX_UNPLACED:
            raise ValueError(f"ilçesiz {unplaced} kayıt, sınır {MAX_UNPLACED}")
        if len({p for p, _ in province_totals}) != 81:
            raise ValueError("81 il yok")

        records = []
        for level, counts in (("district", districts), ("province", province_totals)):
            for (area, kind), count in sorted(counts.items()):
                records.append(
                    {
                        "indicator_id": self.indicator_id,
                        "area_id": area,
                        "area_level": level,
                        "period_start": dt.date(SNAPSHOT.year, 1, 1),
                        "frequency": "annual",
                        "dims": format_dims({"health_facility_kind": kind}),
                        "value": float(count),
                        "unit": "facility",
                        "quality_flag": "measured",
                        "vintage": VINTAGE,
                        "source_id": self.source_id,
                        "retrieved_at": RETRIEVED,
                    }
                )
        return pl.DataFrame(records)


SKRS_ADAPTERS = {"health_facility_register": SkrsHealthFacilities}
