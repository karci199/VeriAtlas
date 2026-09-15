"""University entrance: applicants and placements (YÖK İstatistik, "Yükseköğretime Geçiş").

Two sources on istatistik.yok.gov.tr, static files under `/images/ykgi/` (downloaded into
`raw/yok_istatistik/gecis/`):

* "Yıllara göre üniversitelere başvuran ve yerleşen aday sayıları", 1980-2025, national;
* per exam year 2015-2025 (ÖSYS, then YKS) "okul türü ve öğrenim durumuna göre başvuran ve
  yerleşen": rows are school types (Anadolu lisesi, fen lisesi, meslek liseleri ...), columns
  the candidate status (final-year, graduate not placed before, enrolled elsewhere, placed
  before, total) × applied / placed on a bachelor's, associate or open-education programme.

Share columns (%) are dropped. Checks: the school types of a group add up to its printed
subtotal ("LİSE ÇIKIŞLILAR", "MESLEK LİSELERİ"), and the groups plus the stand-alone rows add
up to GENEL TOPLAM, column by column.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import fold

FOLDER = RAW / "yok_istatistik" / "gecis"
ARCHIVE = FOLDER / "YILLARA_GORE_UNIVERSITELERE_BASVURAN_YERLESEN_ADAY_SAYILARI.xlsx"
STATUS = {
    "sonsinif": "final_year",
    "mezun": "graduate_not_placed",
    "biryuksek": "enrolled_elsewhere",
    "dahaonce": "placed_before",
    "toplam": "total",
}
OUTCOME = {
    "basvuran": "applied",
    "lisans": "placed_bachelor",
    "onlisans": "placed_associate",
    "ao": "placed_open",
}


def rows_of(path: Path) -> list[list[str]]:
    if path.suffix == ".xlsx":
        import openpyxl

        sheet = openpyxl.load_workbook(path, data_only=True).worksheets[0]
        return [
            ["" if v is None else str(v) for v in r]
            for r in sheet.iter_rows(values_only=True)
        ]
    import xlrd

    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    return [[str(v) for v in sheet.row_values(r)] for r in range(sheet.nrows)]


def number(cell: str) -> float:
    cell = cell.strip()
    if cell in ("", "---", "--", "-"):
        return 0.0
    return float(cell)


def status_of(text: str) -> str | None:
    key = fold(text)
    for prefix, name in STATUS.items():
        if key.startswith(prefix):
            return name
    return None


def read_year(path: Path) -> dict[tuple[str, str, str], float]:
    """{(school type, status, outcome): count} for one exam year, checked."""
    rows = rows_of(path)
    status_row = next(
        i for i, r in enumerate(rows) if sum(bool(status_of(c)) for c in r) >= 4
    )
    # 2015 leaves two empty rows between the status row and "BAŞVURAN".
    applied_row = next(
        i
        for i in range(status_row + 1, status_row + 5)
        if any(fold(c) == "basvuran" for c in rows[i])
    )
    kind_row = applied_row + 1
    columns: dict[int, tuple[str, str]] = {}
    status = None
    for j in range(1, max(len(rows[status_row]), len(rows[kind_row]))):
        top = rows[status_row][j] if j < len(rows[status_row]) else ""
        if top.strip():
            status = status_of(top)
            if status is None:
                raise ValueError(f"{path.name}: tanınmayan aday durumu {top!r}")
        middle = fold(rows[applied_row][j]) if j < len(rows[applied_row]) else ""
        bottom = fold(rows[kind_row][j]) if j < len(rows[kind_row]) else ""
        if middle == "basvuran":
            columns[j] = (status, "applied")
        elif bottom in OUTCOME and bottom != "basvuran":
            columns[j] = (status, OUTCOME[bottom])
    if len(columns) != 20:
        raise ValueError(
            f"{path.name}: {len(columns)} sütun, beklenen 20 (5 durum × 4)"
        )
    leaves: dict[str, dict] = {}
    group: list[str] = []
    grand = None
    for r in rows[kind_row + 1 :]:
        label = r[0] if r else ""
        if not label.strip() or label.strip().startswith(("Not", "*")):
            continue
        values = {k: number(r[j]) if j < len(r) else 0.0 for j, k in columns.items()}
        key = fold(label)
        if key.startswith("geneltoplam"):
            grand = values
            continue
        has_numbers = any(re.search(r"\d", r[j]) for j in columns if j < len(r))
        # A leading space marks a group row: a header (no numbers), the subtotal closing a
        # group, or a school type with no group of its own ("ÖĞRETMEN LİSELERİ").
        if label.startswith(" ") and not (has_numbers and not group):
            if not has_numbers:
                group = []
                continue
            for k, printed in values.items():
                parts = sum(leaves[name][k] for name in group)
                if abs(parts - printed) > 0.5:
                    raise ValueError(
                        f"{path.name} {label.strip()} {k}: türler {parts:,.0f}, ara toplam {printed:,.0f}"
                    )
            group = []
            continue
        name = re.sub(r"\s+", " ", label.strip())
        if name in leaves:
            raise ValueError(f"{path.name}: {name} iki kez")
        leaves[name] = values
        if not label.startswith(" "):  # a stand-alone type belongs to no group
            group.append(name)
    if grand is None:
        raise ValueError(f"{path.name}: GENEL TOPLAM yok")
    for k, printed in grand.items():
        parts = sum(v[k] for v in leaves.values())
        if abs(parts - printed) > 0.5:
            raise ValueError(
                f"{path.name} {k}: türler {parts:,.0f}, genel toplam {printed:,.0f}"
            )
    return {
        (name, s, o): v
        for name, values in leaves.items()
        for (s, o), v in values.items()
    }


def school_code(name: str) -> str:
    table = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return re.sub(r"[^a-z0-9]+", "_", name.translate(table).lower()).strip("_")


def frame(records: list[dict], indicator: str, vintage: str) -> pl.DataFrame:
    return pl.DataFrame(records, schema_overrides={"value": pl.Float64}).with_columns(
        pl.lit("TR").alias("area_id"),
        pl.lit("country").alias("area_level"),
        pl.lit(indicator).alias("indicator_id"),
        pl.lit("annual").alias("frequency"),
        pl.lit("person").alias("unit"),
        pl.lit("measured").alias("quality_flag"),
        pl.lit(vintage).alias("vintage"),
        pl.lit("yok_istatistik").alias("source_id"),
        pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
    )


class YksBySchool:
    indicator_id = "yks_applicants_by_school"
    source_id = "yok_istatistik"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        records = []
        for path in sorted(FOLDER.glob("20*")):
            year = int(path.name[:4])
            for (school, status, outcome), value in read_year(path).items():
                if value:
                    records.append(
                        {
                            "period_start": dt.date(year, 1, 1),
                            "dims": f"candidate_status={status};exam_outcome={outcome};school_type={school_code(school)}",
                            "value": value,
                        }
                    )
        return frame(records, self.indicator_id, "2025-09")


class YksArchive:
    indicator_id = "yks_applicants_placed"
    source_id = "yok_istatistik"

    def fetch(self) -> Path:
        return ARCHIVE

    def parse(self, raw: Path) -> pl.DataFrame:
        rows = rows_of(ARCHIVE)
        records = []
        for r in rows:
            cells = [c.strip() for c in r if c.strip()]
            if len(cells) >= 3 and re.fullmatch(r"(19|20)\d\d(\.0)?", cells[0]):
                year = int(float(cells[0]))
                records += [
                    {
                        "period_start": dt.date(year, 1, 1),
                        "dims": "exam_outcome=applied",
                        "value": number(cells[1]),
                    },
                    {
                        "period_start": dt.date(year, 1, 1),
                        "dims": "exam_outcome=placed",
                        "value": number(cells[2]),
                    },
                ]
        years = sorted({r["period_start"].year for r in records})
        if years != list(range(years[0], years[-1] + 1)) or years[0] != 1980:
            raise ValueError(f"YKS arşiv: yıllar kesintili {years[:3]}…{years[-3:]}")
        return frame(records, self.indicator_id, "2025-09")


YKS_ADAPTERS = {
    "yks_applicants_by_school": YksBySchool,
    "yks_applicants_placed": YksArchive,
}
