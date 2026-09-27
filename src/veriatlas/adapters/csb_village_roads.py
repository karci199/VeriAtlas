"""Village road length by province, road class and surface, 2020-2025 (ÇŞB).

Source: Çevre, Şehircilik ve İklim Değişikliği Bakanlığı, Yerel Yönetimler Genel Müdürlüğü,
"Köy Yolları Resmi İstatistikleri" (yerelyonetimler.csb.gov.tr/resmi-istatistik-88465), one
Excel per year, downloaded 2026-09-27 into `raw/csb/koy_yollari/koy_yollari_<year>.xlsx`.
Sheet "1-2-KÖY-İÇİ": per province three rows (1st-degree, 2nd-degree and in-village roads),
km by surface. Only the 51 provinces without a metropolitan municipality are listed: in the
other 30 village roads belong to the metropolitan municipality and are not in this series.

Checks: the surface columns add up to the row total; the provinces add up to the TOPLAM
rows; every province name resolves, once per class.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import province_id

FILES = RAW / "csb" / "koy_yollari"
YEARS = range(2020, 2026)
CLASSES = {
    "1. DERECE": "first_degree",
    "2. DERECE": "second_degree",
    "KÖY İÇİ YOL": "village_inner",
}
#: column position -> `surface` value; the header spans two rows (Asfalt: Sathi/BSK,
#: Beton: Klasik/SSB), checked below.
SURFACES = {
    2: "earth",
    3: "graded",
    4: "stabilized",
    5: "surface_treatment",
    6: "asphalt_concrete",
    7: "stone_block",
    8: "concrete",
    9: "roller_compacted_concrete",
}
HEADER = [
    "Ham yol",
    "Tesviye",
    "Stabilize",
    "Asfalt",
    "",
    "Parke Taşı",
    "Beton",
    "",
    "Toplam",
]
SUBHEADER = ["", "", "", "Sathi", "BSK", "", "Klasik", "SSB", ""]


def rows(path: Path) -> list[list]:
    from python_calamine import CalamineWorkbook

    book = CalamineWorkbook.from_path(path)
    if book.sheet_names != ["1-2-KÖY-İÇİ"]:
        raise ValueError(f"ÇŞB köy yolları {path.name}: sayfalar {book.sheet_names}")
    return book.get_sheet_by_name("1-2-KÖY-İÇİ").to_python()


def read_year(year: int) -> list[dict]:
    table = rows(FILES / f"koy_yollari_{year}.xlsx")
    if [str(c).strip() for c in table[0][2:11]] != HEADER or [
        str(c).strip() for c in table[1][2:11]
    ] != SUBHEADER:
        raise ValueError(f"ÇŞB köy yolları {year}: başlık değişmiş")
    out, totals, sums, seen = [], {}, {}, set()
    for r in table[2:]:
        name, cls = str(r[0]).strip(), CLASSES[str(r[1]).strip()]
        values = {s: float(r[j] or 0) for j, s in SURFACES.items()}
        total = float(r[10])
        if abs(sum(values.values()) - total) > 0.01:
            raise ValueError(
                f"ÇŞB köy yolları {year} {name} {cls}: kaplamalar ≠ toplam"
            )
        if name == "TOPLAM":
            totals[cls] = total
            continue
        area = province_id(name)
        if (area, cls) in seen:
            raise ValueError(f"ÇŞB köy yolları {year}: {name} {cls} iki kez")
        seen.add((area, cls))
        sums[cls] = sums.get(cls, 0) + total
        for surface, km in {**values, "total": total}.items():
            out.append(
                {
                    "area_id": area,
                    "year": year,
                    "cls": cls,
                    "surface": surface,
                    "value": km,
                }
            )
    for cls, total in totals.items():
        if abs(sums[cls] - total) > 0.5:
            raise ValueError(
                f"ÇŞB köy yolları {year} {cls}: iller {sums[cls]:.1f} ≠ TOPLAM {total:.1f}"
            )
    if len({a for a, _ in seen}) != 51:
        raise ValueError(
            f"ÇŞB köy yolları {year}: {len({a for a, _ in seen})} il, 51 bekleniyor"
        )
    return out


class CsbVillageRoads:
    source_id = "csb_yerel"
    indicator_id = "village_road_length"

    def fetch(self) -> Path:
        return FILES

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "area_id": r["area_id"],
                "period_start": dt.date(r["year"], 1, 1),
                "dims": f"surface={r['surface']};village_road_class={r['cls']}",
                "value": r["value"],
            }
            for year in YEARS
            for r in read_year(year)
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("km").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-03").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 27)).alias("retrieved_at"),
        )


CSB_VILLAGE_ROADS_ADAPTERS = {CsbVillageRoads.indicator_id: CsbVillageRoads}
