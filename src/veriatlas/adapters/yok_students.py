"""Higher education enrollment: YÖK's own yearly summary tables, 1982-2026.

Türkiye toplamı only — YÖK publishes the province breakdown as a *different* table
("İllere Göre Öğrenci ve Öğretim Elemanı Sayıları"), not downloaded yet. So this
adapter's rows are all `area_id="TR"`, `area_level="country"`.

Two source shapes, both hand-downloaded from istatistik.yok.gov.tr into the desktop
folder:

* **1982-2013** — one file, `1982-2013_OGRENCI-MEZUN_OZET.xlsx`. Every academic year is
  a nine-row block repeated down the sheet, two years shown side by side: the left six
  columns (yeni kayıt E/K/T, toplam öğrenci E/K/T) belong to the *current* year in the
  block's own header; the right three (mezun E/K/T) belong to the *previous* year, since
  a year's graduates are only known once it has ended. Only the left block is read here
  — graduate counts are a separate indicator, not yet modelled.
* **2014-2026** — one file per academic year, `TABLO 1. ÖĞRENCİ SAYILARI ÖZET TABLOSU`.
  Same two measures, but the sex order in the header varies by file (2014 alone writes
  T/E/K; every later file writes E/K/T) — read from the header row itself rather than
  assumed, so a reordering elsewhere does not silently swap two sexes' numbers. From
  2015 the sheet widens with DEVLET / VAKIF / VAKIF MYO column groups; only the leading
  TOPLAM group is read.

Both a level row ("ÖNLİSANS") and its sub-rows ("ÖRGÜN ÖĞRETİM", "İKİNCİ ÖĞRETİM", ...)
appear in the newer files. Only the four top-level rows are read — summing the
sub-rows too would double every count. `"T"` (both sexes) columns are not stored either:
they are the sum of the two the sex breakdown already carries, and the screen sums them
back on request rather than holding a third, redundant row (same choice as `population`
and `deaths`).

`YILLARA_GORE_UNIVERSITELERE_BASVURAN_YERLESEN_ADAY_SAYILARI.xlsx` is a third, unrelated
file — the yearly applicant/admitted count, 1980-2025, no breakdown at all — read by a
third, much smaller class in this module.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl
import xlrd

from ..config import RAW
from ..schema import format_dims
from .base import cached_copy

DESKTOP = Path(r"C:\Users\katan\OneDrive\Desktop\demografi")

OLD_SUMMARY = DESKTOP / "1982-2013_OGRENCI-MEZUN_OZET.xlsx"

#: One file per academic year, 2014-2026. Named by hand at download time, so matched by
#: a loose pattern rather than an exact list — a year added later needs no code change.
YEARLY_FILES = re.compile(r"^20\d{2}_T?0*1(_v\d+)?\.xls$", re.IGNORECASE)

APPLICANTS_FILE = (
    DESKTOP / "YILLARA_GORE_UNIVERSITELERE_BASVURAN_YERLESEN_ADAY_SAYILARI.xlsx"
)

#: Row label (first line only, upper-cased) -> the level it names. Matched by prefix so
#: that "ÖNLİSANS" and "ÖNLİSANS\nVOCATIONAL TRAINING SCH" both hit, and ordered so the
#: parenthetical old-file variant ("ÖNLİSANS (AÇIK HARİÇ)") is skipped rather than
#: mistaken for the level itself — it is a sub-total, one of the things this adapter
#: deliberately does not read.
LEVELS = [
    (
        re.compile(r"^(ÜNİVERSİTELER TOPLAMI|TOPLAM)\b"),
        None,
    ),  # the whole-file total row
    (re.compile(r"^ÖNLİSANS\b(?!.*HARİÇ)"), "assoc"),
    (re.compile(r"^LİSANS\b"), "bachelor"),
    (re.compile(r"^YÜKSEK LİSANS\b"), "masters"),
    (re.compile(r"^DOKTORA\b"), "doctorate"),
]

SEXES = {"E": "male", "K": "female"}


def level_of(label: str) -> tuple[bool, str | None]:
    """(matched, level) — level is None for the all-levels total row, which is skipped."""
    head = label.split("\n")[0].strip().upper()
    for pattern, level in LEVELS:
        if pattern.match(head):
            return True, level
    return False, None


def read_new_and_total_block(sheet, header_row: int, year: int) -> list[dict]:
    """One year's TOPLAM column group, from a header row naming E/K/T underneath it.

    The header row carries the sex letters; the row above it names the two measure
    blocks ("YENİ KAYIT" / "TOPLAM ÖĞRENCİ SAYISI"). Only the first six sex-lettered
    columns are taken — DEVLET/VAKIF/VAKIF MYO groups repeat the same letters further
    right and are not this adapter's business.
    """
    # "T" (both sexes) is not in SEXES and is skipped on purpose (see module docstring),
    # so only two letters match per measure block — the first two collected are always
    # "yeni kayıt", the next two "toplam öğrenci", since that block order is the one
    # thing every year's layout agrees on. Bounded to four matches so the scan stops
    # before it ever reaches DEVLET/VAKIF's own E/K columns further right.
    cols = []
    for c in range(1, sheet.ncols):
        v = str(sheet.cell_value(header_row, c)).strip()
        if v in SEXES:
            cols.append((c, SEXES[v]))
        if len(cols) == 4:
            break
    if len(cols) < 4:
        raise ValueError("cinsiyet sütunları bulunamadı, satır " + str(header_row))

    records = []
    seen_levels: set[str] = set()
    for r in range(header_row + 1, sheet.nrows):
        label = str(sheet.cell_value(r, 0))
        matched, level = level_of(label)
        if not matched or level is None or level in seen_levels:
            continue
        seen_levels.add(level)
        for index, (c, sex) in enumerate(cols):
            value = sheet.cell_value(r, c)
            if value == "" or value is None:
                continue
            measure = "student_new_admissions" if index < 2 else "student_total"
            records.append(
                {
                    "indicator_id": measure,
                    "area_id": "TR",
                    "area_level": "country",
                    "year": year,
                    "dims": format_dims({"edu_level": level, "sex": sex}),
                    "value": float(value),
                }
            )
    return records


def parse_yearly_files() -> list[dict]:
    """The 2014-2026 files: one header row, one TOPLAM block, per file."""
    records: list[dict] = []
    for path in sorted(DESKTOP.glob("*.xls")):
        if not YEARLY_FILES.match(path.name):
            continue
        book = xlrd.open_workbook(str(path))
        sheet = book.sheet_by_index(0)

        # The academic year sits in the title on most files, but 2014's carries no
        # year there at all — it is one row down, in its own cell instead. Searched
        # across the first few rows/columns rather than one fixed cell for that reason.
        found = None
        for r in range(4):
            for c in range(3):
                text = str(sheet.cell_value(r, c))
                found = re.search(r"(?P<start>\d{4})\s*-\s*\d{4}", text)
                if found:
                    break
            if found:
                break
        if not found:
            raise ValueError(path.name + ": başlıkta akademik yıl bulunamadı")
        year = int(found.group("start"))

        header_row = None
        for r in range(sheet.nrows):
            letters = {str(sheet.cell_value(r, c)).strip() for c in range(sheet.ncols)}
            if letters >= {"E", "K", "T"} or letters >= {"E", "K"}:
                header_row = r
                break
        if header_row is None:
            raise ValueError(path.name + ": E/K/T başlık satırı bulunamadı")

        records.extend(read_new_and_total_block(sheet, header_row, year))
    return records


def parse_old_summary() -> list[dict]:
    """The 1982-2013 file: nine-row blocks repeated down one sheet. Real .xlsx, so
    read with openpyxl rather than the xlrd path the yearly .xls files use."""
    import openpyxl

    wb = openpyxl.load_workbook(str(OLD_SUMMARY), data_only=True)
    sheet = wb[wb.sheetnames[0]]
    rows = [[cell for cell in row] for row in sheet.iter_rows(values_only=True)]
    nrows = len(rows)

    def cell(r: int, c: int):
        if r >= nrows or c >= len(rows[r]):
            return None
        return rows[r][c]

    records: list[dict] = []
    r = 0
    while r < nrows:
        header = str(cell(r, 1) or "")
        found = re.match(r"^(?P<start>\d{4})\s*-\s*\d{4}$", header.strip())
        if not found:
            r += 1
            continue
        year = int(found.group("start"))

        # The sex row, one below the block's two title rows. "T" is skipped (see
        # `read_new_and_total_block`'s comment) so only two letters match per measure
        # block: first two collected are "yeni kayıt", next two "toplam öğrenci" —
        # true whether the row writes E,K,T (2015-2026) or T,E,K (2014 alone).
        sex_row = r + 2
        cols = []
        for c in range(1, 8):
            letter = str(cell(sex_row, c) or "").strip()
            if letter in SEXES:
                cols.append((c, SEXES[letter]))
            if len(cols) == 4:
                break
        if len(cols) != 4:
            raise ValueError(OLD_SUMMARY.name + f": satır {sex_row} beklenmedik başlık")

        seen_levels: set[str] = set()
        for data_row in range(sex_row + 1, sex_row + 7):
            label = str(cell(data_row, 0) or "")
            matched, level = level_of(label)
            if not matched or level is None or level in seen_levels:
                continue
            seen_levels.add(level)
            for index, (c, sex) in enumerate(cols):
                value = cell(data_row, c)
                if value in (None, ""):
                    continue
                measure = "student_new_admissions" if index < 2 else "student_total"
                records.append(
                    {
                        "indicator_id": measure,
                        "area_id": "TR",
                        "area_level": "country",
                        "year": year,
                        "dims": format_dims({"edu_level": level, "sex": sex}),
                        "value": float(value),
                    }
                )
        r = sex_row + 7

    return records


class YokStudents:
    """Yeni kayıt veya toplam öğrenci sayısı, Türkiye toplamı, 1982-2026.

    Both measures live in the same files and are read together, then split by
    `indicator_id` before returning — `ingest()` expects one adapter to produce rows
    for exactly one indicator, and this source's two measures share every row's
    provenance, so parsing them apart would mean opening and walking the files twice.
    """

    source_id = "yok_istatistik"
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 21)

    #: Filled in by the two subclasses below.
    indicator_id = ""

    def fetch(self) -> Path:
        cached_copy(OLD_SUMMARY, RAW / "yok" / OLD_SUMMARY.name)
        for path in DESKTOP.glob("*.xls"):
            if YEARLY_FILES.match(path.name):
                cached_copy(path, RAW / "yok" / path.name)
        return RAW / "yok"

    def parse(self, raw: Path) -> pl.DataFrame:
        records = parse_old_summary() + parse_yearly_files()
        if not records:
            raise ValueError("YÖK öğrenci dosyalarından satır okunamadı")

        frame = pl.DataFrame(records)
        # One (indicator, year, dims) pair must be unique; the old and new files overlap
        # nowhere (1982-2013 vs 2014-2026) so a collision here means a parsing bug, not
        # a real duplicate reading.
        dup = frame.filter(
            frame.select(["indicator_id", "year", "dims"]).is_duplicated()
        )
        if not dup.is_empty():
            raise ValueError("aynı yıl-kırılım iki kere okundu: " + str(dup))

        frame = frame.filter(pl.col("indicator_id") == self.indicator_id)
        if frame.is_empty():
            raise ValueError(self.indicator_id + ": okunan dosyalarda satır yok")

        return frame.with_columns(
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit("annual").alias("frequency"),
            pl.lit("person").alias("unit"),
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


class YokStudentsNewAdmissions(YokStudents):
    indicator_id = "student_new_admissions"


class YokStudentsTotal(YokStudents):
    indicator_id = "student_total"


class YokApplicants:
    """One measure, one file, one column: applicants or admitted, Türkiye, 1980-2025."""

    source_id = "yok_istatistik"
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 21)

    #: Filled in by the two subclasses below.
    indicator_id = ""
    column = 0  # 3 = başvuran, 4 = yerleşen

    def fetch(self) -> Path:
        return cached_copy(APPLICANTS_FILE, RAW / "yok" / APPLICANTS_FILE.name)

    def parse(self, raw: Path) -> pl.DataFrame:
        import openpyxl

        wb = openpyxl.load_workbook(raw, data_only=True)
        sheet = wb[wb.sheetnames[0]]

        records = []
        for row in sheet.iter_rows(min_row=3, values_only=True):
            year, value = row[2], row[self.column]
            if not isinstance(year, int) or value is None:
                continue
            records.append({"year": year, "value": float(value)})

        frame = pl.DataFrame(records)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit("annual").alias("frequency"),
            pl.lit("").alias("dims"),
            pl.lit("person").alias("unit"),
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


class YokUniversityApplicants(YokApplicants):
    indicator_id = "university_applicants"
    column = 3


class YokUniversityAdmitted(YokApplicants):
    indicator_id = "university_admitted"
    column = 4
