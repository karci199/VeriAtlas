r"""BTK "Yıllık İl İstatistikleri": telecom figures by province, 2007-2025.

btk.gov.tr/yillik-il-istatistikleri publishes one workbook per rolling six-year window
(2007-2012 … 2020-2025), kept in `C:\veri-ham\btk\il`. Sheet "İl Bazlı Veri": a TOPLAM
block then one block per province; each metric is a Turkish label row followed by an
English label row carrying the six yearly values.

BTK revises back years silently, so every year is taken from the newest window printing it.
Population is not loaded (TÜİK ADNKS is in the warehouse). TOPLAM is not the sum of the
provinces for fixed lines (~300 thousand unallocated lines a year) and "Diğer" broadband
(~24 thousand): the provinces are loaded as printed, and TOPLAM as the country row.
Values are sometimes fractional (BTK's own allocation); they are kept.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import province_id

FOLDER = RAW / "btk" / "il"

# label -> (indicator, dims)
METRICS = {
    "Sabit Telefon Erişim Hat Sayısı": ("btk_province_fixed_lines", ""),
    "Sabit Telefon Santral Kapasitesi": ("btk_province_exchange_capacity", ""),
    "Ankesörlü Telefon Sayısı": ("btk_province_payphones", ""),
    "Mobil Telefon Abone Sayısı - Toplam": ("btk_province_mobile_subscribers", ""),
    "Mobil Telefon Abone Sayısı - 2N": (
        "btk_province_mobile_by_generation",
        "mobile_generation=2g",
    ),
    "Mobil Telefon Abone Sayısı - 3N": (
        "btk_province_mobile_by_generation",
        "mobile_generation=3g_plus",
    ),
    "Mobil Telefon Abone Sayısı 3N+4.5N": (
        "btk_province_mobile_by_generation",
        "mobile_generation=3g_plus",
    ),
    "Fiber": ("btk_province_broadband", "internet_technology=fiber"),
    "xDSL": ("btk_province_broadband", "internet_technology=xdsl"),
    "Kablo": ("btk_province_broadband", "internet_technology=cable"),
    "Diğer": ("btk_province_broadband", "internet_technology=other"),
    "Mobil Bilgisayardan İnternet": (
        "btk_province_broadband",
        "internet_technology=mobile_computer",
    ),
    "Mobil Cepten İnternet": (
        "btk_province_broadband",
        "internet_technology=mobile_handset",
    ),
    "Kablo TV Abone Sayısı": ("btk_province_cable_tv", ""),
    "Fiber-Optik Kablo Uzunluğu-km": ("btk_province_fiber_km", ""),
    "4.5 Mobil Kapsama Oranları": ("btk_province_4g_coverage", ""),
}
TOTALS = {  # printed totals checked against their parts, not loaded
    "Genişbant İnternet Abone Sayısı - Toplam": (
        "fiber",
        "xdsl",
        "cable",
        "other",
        "mobile_computer",
        "mobile_handset",
    ),
    "Sabit Genişbant İnternet Abone Sayısı - Toplam": (
        "fiber",
        "xdsl",
        "cable",
        "other",
    ),
    "Mobil Genişbant İnternet Abone Sayısı - Toplam": (
        "mobile_computer",
        "mobile_handset",
    ),
}
SKIP = {"Nüfus"}
UNITS = {
    "btk_province_exchange_capacity": "item",
    "btk_province_payphones": "item",
    "btk_province_fiber_km": "km",
    "btk_province_4g_coverage": "percent",
}
ALIASES = {"İÇEL": "Mersin"}


def read_window(path: Path) -> dict[tuple[str, str, int], float]:
    import openpyxl

    sheet = openpyxl.load_workbook(path, read_only=True, data_only=True)[
        "İl Bazlı Veri"
    ]
    rows = list(sheet.iter_rows(values_only=True))
    years = [int(str(v).strip()) for v in rows[0] if v is not None and str(v).strip()]
    if len(years) != 6 or years != list(range(years[0], years[0] + 6)):
        raise ValueError(f"{path.name}: yıl başlığı {years}")
    out: dict[tuple[str, str, int], float] = {}
    area = label = None
    for r in rows[3:]:
        if r[0] is not None and str(r[0]).strip():
            name = str(r[0]).strip()
            if name.startswith("Genel Toplam"):
                break
            area = "TR" if name == "TOPLAM" else province_id(ALIASES.get(name, name))
            continue
        if len(r) > 1 and r[1] is not None:
            label = " ".join(str(r[1]).split())
            if label not in METRICS and label not in TOTALS and label not in SKIP:
                raise ValueError(f"{path.name}: tanınmayan kalem {label!r}")
            continue
        if len(r) > 2 and r[2] is not None:
            for year, v in zip(years, r[3:9], strict=False):
                if v is None or label in SKIP:
                    continue
                key = (area, label, year)
                if key in out:
                    raise ValueError(f"{path.name}: {key} iki kez")
                out[key] = float(v)
    areas = {k[0] for k in out}
    if len(areas) != 82:
        raise ValueError(f"{path.name}: {len(areas)} alan, beklenen 81 il + TR")
    return out


def check_parts(data: dict, name: str) -> None:
    """BTK's own printed totals miss their parts in a handful of cells per window (e.g.
    İstanbul 2011 fixed broadband +15 thousand, Tunceli 2020 +2 thousand; country mobile
    broadband 2009-2010 printed without parts). Up to 10 such province-years pass; more means the
    layout was misread."""
    misses = []
    code = {
        dims.split("=")[1]: label
        for label, (ind, dims) in METRICS.items()
        if ind == "btk_province_broadband"
    }
    for (area, label, year), printed in data.items():
        if label not in TOTALS:
            continue
        parts = sum(data.get((area, code[c], year), 0.0) for c in TOTALS[label])
        if parts and abs(parts - printed) > 1.0:
            misses.append((area, year, label, parts, printed))
    if len({(m[0], m[1]) for m in misses}) > 10:
        raise ValueError(
            f"BTK il {name}: {len(misses)} toplam tutmuyor, ilk {misses[0]}"
        )


def load_all() -> dict[tuple[str, str, int], float]:
    newest: dict[tuple[str, str, int], float] = {}
    paths = sorted(
        FOLDER.glob("*.xlsx"), key=lambda p: int(re.match(r"\d{4}", p.name).group())
    )
    if len(paths) < 14:
        raise FileNotFoundError(f"{FOLDER}: {len(paths)} dosya")
    for path in paths:
        window = read_window(path)
        check_parts(window, path.name)
        years = {k[2] for k in window}
        newest = {
            k: v for k, v in newest.items() if k[2] not in years
        }  # a window replaces its years whole
        newest.update(window)
    return newest


class BtkProvince:
    source_id = "btk"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        records = []
        for (area, label, year), v in load_all().items():
            indicator, dims = METRICS.get(label, (None, None))
            if indicator != self.indicator_id:
                continue
            records.append(
                {
                    "area_id": area,
                    "area_level": "country" if area == "TR" else "province",
                    "period_start": dt.date(year, 1, 1),
                    "dims": dims,
                    "value": v,
                }
            )
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("annual").alias("frequency"),
            pl.lit(UNITS.get(self.indicator_id, "subscriber")).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-05").alias("vintage"),
            pl.lit("btk").alias("source_id"),
            pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
        )


BTK_PROVINCE_ADAPTERS = {
    ind: type(f"BtkProvince_{ind}", (BtkProvince,), {"indicator_id": ind})
    for ind in dict.fromkeys(i for i, _ in METRICS.values())
}
