r"""Schools by district in 2017, from the Ministry of Health code server (SKRS).

SKRS carries MEB's school list so that school health screenings can name the school. It
was loaded once and never refreshed: every one of its 60.129 rows is dated 01.01.2017.
So this is a **2017 cross-section**, and the only district-level school count in the
warehouse (MEB's own lists are closed to us by robots.txt; MEDAS stops at province —
`schools` in `meb_counts`). Schools opened since 2017 are missing and closed ones still
read "Aktif"; the indicator is named `schools_2017` so nobody reads it as current.

Each row gives MEB's institution code, the NVİ district code and a school type ("Tür
Adı"). District names come from SKRS's own address feed (`ilce_kodlari.csv`, written by
the fetcher) and are matched like the health register (`skrs_facilities.place`).

**Types to levels** follow MEB's own statistics: imam-hatip high schools count as
vocational upper secondary, fine-arts and sports high schools as general. Special
education schools and non-formal institutions (Halk Eğitim, apprenticeship centres) get
their own values. A type no rule places stops the parse.

**Ownership** is read from the type: "Özel Türk İlkokulu" is private, but "Özel Eğitim
Uygulama Merkezi" is a *special-education* school run by the state — the word "özel"
means both. Private special-education schools are written "Özel Özel Eğitim ..." or
"Özel Hafif Düzeyde ...".
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import polars as pl

from ..config import RAW
from ..schema import format_dims
from .skrs_facilities import district_index, place

FOLDER = RAW / "skrs"
SOURCE_ID = "skrs"
VINTAGE = "2026-09"
RETRIEVED = dt.date(2026, 9, 25)
SNAPSHOT_YEAR = 2017

#: Checked in order; the first rule whose word appears in the type wins.
LEVEL_RULES = [
    ("special_education", ("Engelli", "Özel Eğitim", "Otistik")),
    (
        "non_formal",
        ("Halk Eğitim", "Eğitim Merkezi", "Olgunlaşma Enstitüsü"),
    ),
    ("preschool", ("Okul Öncesi", "Anaokulu")),
    ("primary", ("İlkokul", "İlköğretim")),
    ("lower_secondary", ("Ortaokul",)),
    (
        "upper_secondary_vocational",
        (
            "Meslek",
            "Teknik",
            "İmam Hatip Lisesi",
            "Çok Programlı",
            "Öğretmen Lisesi",
        ),
    ),
    ("upper_secondary_general", ("Lise", "Ortaöğretim Kurumu")),
]


def level_of(school_type: str) -> str:
    for level, words in LEVEL_RULES:
        if any(word in school_type for word in words):
            return level
    raise ValueError(f"kademesi belirlenemeyen okul türü: {school_type!r}")


def ownership_of(school_type: str) -> str:
    if school_type.startswith("Özel ") and not school_type.startswith("Özel Eğitim"):
        return "private"
    return "public"


def district_names() -> dict[str, tuple[str, str]]:
    """NVİ district code -> (province id, district name), from SKRS's address feed."""
    names = {}
    with (FOLDER / "ilce_kodlari.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            names[row["ilce_kodu"]] = (f"TR-{int(row['il_kodu']):02d}", row["ilce_adi"])
    return names


def dump() -> Path:
    found = sorted(FOLDER.glob("egitim_kurumlari_*.csv"))
    if not found:
        raise FileNotFoundError(f"SKRS okul dökümü yok: {FOLDER}")
    return found[-1]


class SkrsSchools2017:
    indicator_id = "schools_2017"
    source_id = SOURCE_ID

    def fetch(self) -> Path:
        return dump()

    def parse(self, raw: Path) -> pl.DataFrame:
        provinces, index = district_index()
        names = district_names()
        districts: dict[tuple[str, str, str], int] = {}
        seen: set[str] = set()
        with raw.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["Kodu"] in seen:
                    raise ValueError(f"çift kurum kodu: {row['Kodu']}")
                seen.add(row["Kodu"])
                province_id = f"TR-{int(row['sorgu_il_kodu']):02d}"
                if row["İl Kodu"] != row["sorgu_il_kodu"]:
                    raise ValueError(
                        f"{row['Kodu']}: il kodu {row['İl Kodu']} sorgu dışı"
                    )
                code_province, district = names[row["İlçe Kodu"]]
                if code_province != province_id:
                    raise ValueError(f"{row['Kodu']}: ilçe kodu başka ilin")
                area = place(province_id, district, provinces, index)
                if area is None:
                    raise ValueError(f"{row['Kodu']}: ilçe yerleşmedi ({district})")
                key = (area, level_of(row["Tür Adı"]), ownership_of(row["Tür Adı"]))
                districts[key] = districts.get(key, 0) + 1

        province_totals: dict[tuple[str, str, str], int] = {}
        for (area, level, owner), count in districts.items():
            key = (area[:5], level, owner)
            province_totals[key] = province_totals.get(key, 0) + count
        if len({key[0] for key in province_totals}) != 81:
            raise ValueError("81 il yok")

        records = []
        for area_level, counts in (
            ("district", districts),
            ("province", province_totals),
        ):
            for (area, level, owner), count in sorted(counts.items()):
                records.append(
                    {
                        "indicator_id": self.indicator_id,
                        "area_id": area,
                        "area_level": area_level,
                        "period_start": dt.date(SNAPSHOT_YEAR, 1, 1),
                        "frequency": "annual",
                        "dims": format_dims(
                            {"school_level": level, "school_ownership": owner}
                        ),
                        "value": float(count),
                        "unit": "item",
                        "quality_flag": "measured",
                        "vintage": VINTAGE,
                        "source_id": self.source_id,
                        "retrieved_at": RETRIEVED,
                    }
                )
        return pl.DataFrame(records)


SKRS_SCHOOL_ADAPTERS = {"schools_2017": SkrsSchools2017}
