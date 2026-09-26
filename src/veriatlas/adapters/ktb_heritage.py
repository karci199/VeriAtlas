"""Immovable cultural assets under protection by province and type — Ministry of Culture.

The General Directorate of Cultural Assets and Museums publishes "İllere Göre Korunması
Gerekli Taşınmaz Kültür Varlığı İstatistiği" as one HTML page (kvmgm.ktb.gov.tr/TR-44799),
a small table per province: asset types and a TOPLAM row, as of year end (the page says
"2025 Yıl Sonu"). Only the current year is published; each pull adds a year. Saved as
`ktb_kultur_varligi/<year>.html`. The types must add up to TOPLAM in every province and all
81 provinces must be there, or the load stops. Types a province does not list are absent,
not zero.
"""

from __future__ import annotations

import datetime as dt
import html
import re
from pathlib import Path

import polars as pl

from ..config import DATA, RAW
from ..indicators import get
from ..schema import format_dims

DOWNLOADS = RAW / "ktb_kultur_varligi"
TYPES = {
    "Korunmaya Alınan Sokaklar": "protected_streets",
    "Anıt ve Abideler": "monuments",
    "İdari Yapılar": "administrative",
    "Kültürel Yapılar": "cultural",
    "Şehitlikler": "martyrs_cemeteries",
    "Askeri Yapılar": "military",
    "Endüstriyel ve Ticari Yapılar": "industrial_commercial",
    "Dinsel Yapılar": "religious",
    "Mezarlıklar": "cemeteries",
    "Sivil Mimarlık Örneği": "civil_architecture",
    "Kalıntılar": "ruins",
}


def turkish_upper(text: str) -> str:
    return text.replace("i", "İ").replace("ı", "I").upper()


def read_page(path: Path) -> list[tuple[str, str, float]]:
    page = path.read_text(encoding="utf-8")
    rows = []
    for tr in re.findall(r"<tr.*?</tr>", page, flags=re.DOTALL):
        cells = [
            html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.DOTALL)
        ]
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)
    provinces = pl.read_csv(DATA / "areas_tr.csv").filter(
        pl.col("area_level") == "province"
    )
    ids = {
        turkish_upper(n): a
        for a, n in provinces.select("area_id", "name_tr").iter_rows()
    }
    out, area, seen, total = [], None, {}, {}
    for cells in rows:
        if len(cells) == 1 and cells[0] in ids:
            area = ids[cells[0]]
            seen[area] = 0.0
        elif len(cells) == 2 and area:
            name, value = cells[0], float(cells[1].replace(".", ""))
            if name == "TOPLAM":
                total[area] = value
            elif name in TYPES:
                out.append((area, TYPES[name], value))
                seen[area] += value
            else:
                raise KeyError("ktb: taninmayan tur: " + name)
    if len(seen) != 81:
        raise ValueError(f"ktb: {len(seen)} il, 81 bekleniyordu")
    bad = [a for a in seen if abs(seen[a] - total.get(a, -1)) > 0.5]
    if bad:
        raise ValueError("ktb: turler toplami tutmuyor: " + ", ".join(bad))
    return out


class KtbHeritage:
    source_id = "ktb_kvmgm"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 26)
    indicator_id = "immovable_cultural_assets"

    def fetch(self) -> Path:
        if not any(DOWNLOADS.glob("*.html")):
            raise FileNotFoundError("KTB kultur varligi dokumu yok: " + str(DOWNLOADS))
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        records = []
        for path in sorted(raw.glob("*.html")):
            year = int(path.stem)
            for area, kind, value in read_page(path):
                records.append(
                    (
                        area,
                        dt.date(year, 1, 1),
                        format_dims({"heritage_type": kind}),
                        value,
                    )
                )
        frame = pl.DataFrame(
            records, schema=["area_id", "period_start", "dims", "value"], orient="row"
        )
        tr = frame.group_by("period_start", "dims").agg(pl.col("value").sum())
        frame = pl.concat(
            [
                frame.with_columns(pl.lit("province").alias("area_level")),
                tr.with_columns(
                    pl.lit("TR").alias("area_id"), pl.lit("country").alias("area_level")
                ),
            ],
            how="diagonal",
        )
        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
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
