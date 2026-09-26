"""Domestic industrial property applications and registrations by province — TÜRKPATENT.

TÜRKPATENT publishes one workbook per right and per stage ("… Başvurularının / Tescillerinin
İllere Göre Dağılımı"), province by year from 1995. The files are listed by the site's
gallery API (`/api/gallery?locale=tr&slug=<right>-yillik-istatistikler`, field `media[].slug`)
and served from `webim.turkpatent.gov.tr/file/<slug>?download`. Pulled 2026-09-26 into
`turkpatent/` with `manifest.json`; the latest year is as of the 5 January report date.

Rows are keyed by the two-digit plate code; the file's own TOPLAM row must equal the sum of
the 81 provinces for every year, or the load stops. Design files give two counts a year:
application files and the designs in them (one file may hold many designs) — stored as two
values of `ip_right`, which therefore must not be summed across.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get
from ..schema import format_dims

DOWNLOADS = RAW / "turkpatent"

FILES = {
    ("application", "patent"): "Patent_Başvurularının_İllere_Göre_Dağılımı.xls",
    ("registration", "patent"): "Patent_Tescillerinin_İllere_Göre_Dağılımı.xls",
    (
        "application",
        "utility_model",
    ): "Faydalı_Model_Başvurularının_İllere_Göre_Dağılımı.xls",
    (
        "registration",
        "utility_model",
    ): "Faydalı_Model_Tescillerinin_İllere_Göre_Dağılımı.xls",
    ("application", "trademark"): "Marka_Başvurularının_İllere_Göre_Dağılımı.xls",
    ("registration", "trademark"): "Marka_Tescillerinin_İllere_Göre_Dağılımı.xls",
    ("application", "design"): "Tasarım_Başvurularının_İllere_Göre_Dağılımı.xls",
    ("registration", "design"): "Tasarım_Tescillerinin_İllere_Göre_Dağılımı.xls",
}
INDICATORS = {
    "application": "ip_applications_by_province",
    "registration": "ip_registrations_by_province",
}


def read_file(path: Path, right: str) -> list[tuple[str, int, str, float]]:
    """(area_id, year, ip_right, value) rows, checked against the TOPLAM row."""
    import xlrd

    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    years = sheet.row_values(2)
    columns = []  # (column, year, ip_right)
    for i, y in enumerate(years):
        if isinstance(y, float) and y > 1900:
            if right == "design":
                columns += [(i, int(y), "design"), (i + 1, int(y), "design_items")]
            else:
                columns.append((i, int(y), right))
    if not columns:
        raise ValueError("turkpatent: yil satiri yok: " + path.name)
    rows, total = [], None
    for r in range(sheet.nrows):
        values = sheet.row_values(r)
        code, name = str(values[0]).strip(), str(values[1]).strip()
        if name.upper() == "TOPLAM":
            total = {(y, k): float(values[c] or 0) for c, y, k in columns}
        elif code.isdigit() and 1 <= int(code) <= 81:
            area = f"TR-{int(code):02d}"
            rows += [(area, y, k, float(values[c] or 0)) for c, y, k in columns]
    if total is None:
        raise ValueError("turkpatent: TOPLAM satiri yok: " + path.name)
    if len({a for a, *_ in rows}) != 81:
        raise ValueError("turkpatent: 81 il yok: " + path.name)
    sums: dict[tuple, float] = {}
    for _, y, k, v in rows:
        sums[(y, k)] = sums.get((y, k), 0) + v
    bad = [key for key, v in total.items() if abs(sums.get(key, 0) - v) > 0.5]
    if bad:
        raise ValueError(f"turkpatent: iller toplami tutmuyor {path.name} {bad[:3]}")
    return rows + [("TR", y, k, v) for (y, k), v in total.items()]


class TurkpatentBase:
    source_id = "turkpatent"
    vintage = "2026-01"
    retrieved_at = dt.date(2026, 9, 26)
    indicator_id = ""
    stage = ""

    def fetch(self) -> Path:
        if not (DOWNLOADS / "manifest.json").exists():
            raise FileNotFoundError("TURKPATENT dokumu yok: " + str(DOWNLOADS))
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        records = []
        for (stage, right), name in FILES.items():
            if stage != self.stage:
                continue
            for area, year, k, value in read_file(raw / name, right):
                records.append(
                    (
                        area,
                        "country" if area == "TR" else "province",
                        dt.date(year, 1, 1),
                        format_dims({"ip_right": k}),
                        value,
                    )
                )
        frame = pl.DataFrame(
            records,
            schema=["area_id", "area_level", "period_start", "dims", "value"],
            orient="row",
        )
        if frame.select("area_id", "period_start", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni alan-yil-tur iki kez")
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


class TurkpatentApplications(TurkpatentBase):
    indicator_id = "ip_applications_by_province"
    stage = "application"


class TurkpatentRegistrations(TurkpatentBase):
    indicator_id = "ip_registrations_by_province"
    stage = "registration"


TURKPATENT_ADAPTERS = {
    "turkpatent_applications": TurkpatentApplications,
    "turkpatent_registrations": TurkpatentRegistrations,
}
