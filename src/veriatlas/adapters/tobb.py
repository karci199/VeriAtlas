"""TOBB company establishment and closure statistics by province, 2009-2025.

Source: TOBB Bilgi Erişim Müdürlüğü, "Kurulan ve Kapanan Şirket İstatistikleri", one Excel
per month (`raw/tobb/<year>-12.xls`, December files only). The December file's sheet
"İLLER ( BİRİKİMLİ)" is the whole year by province, and the year before beside it: groups
KURULAN (company, cooperative, sole trader), TASFİYE (company, cooperative) and KAPANAN
(company, cooperative, sole trader). Source: Türkiye Ticaret Sicili Gazetesi.

Columns are read from the two header rows rather than fixed positions: 2010-2012 have no
NUTS code column. Every column must add up to the TOPLAM row. The previous-year block of
each file is compared with that year's own file; the newer file wins and revisions are
recorded (TOBB updates the registry counts after the year closes).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import fold, province_id, provinces

FILES = RAW / "tobb"
EVENTS = {"kurulan": "established", "tasfiye": "liquidation", "kapanan": "closed"}
ENTITIES = {"sirket": "company", "koop": "cooperative", "gerkisi": "sole_trader"}

#: (year, cells revised, largest relative revision) from the next year's file.
REVISIONS: list[tuple[int, int, float]] = []


def entity(label: str) -> str | None:
    key = fold(label)
    for prefix, name in ENTITIES.items():
        if key.startswith(prefix):
            return name
    return None


def read_year_file(path: Path) -> dict[int, dict[tuple[str, str, str], float]]:
    """{year: {(area, event, entity): count}} for both blocks of one December file."""
    import re

    import xlrd

    sheet = xlrd.open_workbook(path).sheet_by_name("İLLER ( BİRİKİMLİ)")
    rows = [[str(v).strip() for v in sheet.row_values(r)] for r in range(sheet.nrows)]
    ev_row = next(i for i, r in enumerate(rows) if any(fold(c) == "kurulan" for c in r))
    years_row = next(
        i for i, r in enumerate(rows) if any("OCAK" in c.upper() for c in r)
    )
    years = [
        (j, int(re.search(r"(20\d\d)", c).group(1)))
        for j, c in enumerate(rows[years_row])
        if re.search(r"20\d\d", c)
    ]
    sub_row = next(
        i for i in range(ev_row + 1, ev_row + 3) if any(entity(c) for c in rows[i])
    )
    columns: dict[int, tuple[int, str, str]] = {}
    event = None
    for j, cell in enumerate(rows[ev_row]):
        if fold(cell) in EVENTS:
            event = EVENTS[fold(cell)]
        kind = entity(rows[sub_row][j]) if j < len(rows[sub_row]) else None
        if kind and event:
            starts = [(start, y) for start, y in years if start <= j]
            year = max(starts)[1] if starts else years[0][1]
            columns[j] = (year, event, kind)
    out: dict[int, dict[tuple[str, str, str], float]] = {}
    total_row = None
    for r in rows[sub_row + 1 :]:
        label = next((c for c in r[:2] if c and not re.fullmatch(r"TR\w\d\d", c)), "")
        if fold(label) == "toplam":
            total_row = r
            break
        # From 2019 a note row ("22 ŞUBAT 2019 ...") sits among the provinces, no numbers.
        if not label or all(r[j] in ("", "-") for j in columns if j < len(r)):
            continue
        # From 2019 İstanbul's NUTS code cell reads "22 ŞUBAT 2019": the name is taken
        # from whichever of the first two cells is a province.
        area = None
        for cell in r[:2]:
            try:
                area = province_id(cell)
                break
            except KeyError:
                continue
        if area is None:
            raise KeyError(f"TOBB {path.name}: tanınmayan il {r[:2]}")
        for j, (year, event, kind) in columns.items():
            value = float(r[j]) if r[j] not in ("", "-") else 0.0
            key = (area, event, kind)
            if key in out.setdefault(year, {}):
                raise ValueError(f"TOBB {path.name}: {label} iki kez")
            out[year][key] = value
    if total_row is None:
        raise ValueError(f"TOBB {path.name}: TOPLAM satırı yok")

    # TOPLAM puts its label in the first cell, where provinces have a NUTS code and then
    # the name: its numbers then sit one column left of the provinces'.
    def first_number(r):
        return next(i for i, c in enumerate(r) if re.fullmatch(r"\d+(\.0)?", c))

    province_row = next(r for r in rows[sub_row + 1 :] if any(c for c in r[:2]))
    offset = first_number(total_row) - first_number(province_row)
    for j, (year, event, kind) in columns.items():
        cell = total_row[j + offset] if 0 <= j + offset < len(total_row) else ""
        printed = float(cell) if cell not in ("", "-") else 0.0
        parts = sum(v for (a, e, k), v in out[year].items() if e == event and k == kind)
        if abs(parts - printed) > 0.5:
            raise ValueError(
                f"TOBB {path.name} {year} {event} {kind}: iller {parts:,.0f}, TOPLAM {printed:,.0f}"
            )
    for year, table in out.items():
        if len({a for a, _, _ in table}) != 81:
            raise ValueError(
                f"TOBB {path.name} {year}: {len({a for a, _, _ in table})} il"
            )
    return out


class TobbCompanies:
    source_id = "tobb"
    indicator_id = "tobb_companies"

    def fetch(self) -> Path:
        return FILES

    def parse(self, raw: Path) -> pl.DataFrame:
        merged: dict[int, dict[tuple[str, str, str], float]] = {}
        for path in sorted(FILES.glob("20??-12.xls*")):
            file_year = int(path.name[:4])
            for year, table in read_year_file(path).items():
                if year == file_year or year not in merged:
                    if year in merged and year == file_year:
                        raise ValueError(f"TOBB {year}: iki dosya")
                    if year != file_year:
                        merged[year] = table
                        continue
                    merged[year] = table
                else:
                    # The next file's previous-year block: newer counts win.
                    old = merged[year]
                    changed = [
                        k for k in table if abs(table[k] - old.get(k, 0.0)) > 0.5
                    ]
                    worst = max(
                        (
                            abs(table[k] - old[k]) / old[k]
                            for k in changed
                            if old.get(k)
                        ),
                        default=0.0,
                    )
                    REVISIONS.append((year, len(changed), worst))
                    merged[year] = table
        records = [
            {
                "area_id": area,
                "period_start": dt.date(year, 1, 1),
                "dims": f"company_event={event};company_type={kind}",
                "value": value,
            }
            for year, table in merged.items()
            for (area, event, kind), value in table.items()
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("company").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-07").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
        )


TOBB_ADAPTERS = {"tobb_companies": TobbCompanies}


def read_capital(path: Path) -> dict[str, float]:
    """ "İLLER SERMAYE": capital of the companies established in the year, TL, by province.

    The year's block is the last "Sermaye" column (2015-2016 print December and the whole
    year side by side, the year second). The count column beside it must equal the company
    count read from "İLLER ( BİRİKİMLİ)", province by province: that is what ties the capital
    to the right column and the right year.
    """
    import re

    import xlrd

    book = xlrd.open_workbook(path)
    if "İLLER SERMAYE" not in book.sheet_names():
        return {}
    sheet = book.sheet_by_name("İLLER SERMAYE")
    rows = [[str(v).strip() for v in sheet.row_values(r)] for r in range(sheet.nrows)]
    year = int(path.name[:4])
    head = next(
        i for i, r in enumerate(rows) if any(c.startswith("Sermaye") for c in r)
    )
    # The year block starts at the last header cell naming the year (2015-2016: "2015
    # ARALIK" then "2015 OCAK-ARALIK"); its first "Sermaye" column is the companies'.
    year_row = max(
        i for i in range(head) if any(c.startswith(str(year)) for c in rows[i])
    )
    start = max(j for j, c in enumerate(rows[year_row]) if c.startswith(str(year)))
    col = min(
        j for j, c in enumerate(rows[head]) if c.startswith("Sermaye") and j >= start
    )
    counts = read_year_file(path)[year]
    # 2020 leaves one province name blank beside its NUTS code (TRA12): codes are resolved
    # through the same file's cumulative sheet, where every code has its name.
    cumulative = book.sheet_by_name("İLLER ( BİRİKİMLİ)")
    by_code: dict[str, str] = {}
    for r in range(cumulative.nrows):
        cells = [str(v).strip() for v in cumulative.row_values(r)[:3]]
        code = next((c for c in cells if re.fullmatch(r"TR\w\d\d", c)), None)
        if code:
            for c in cells:
                try:
                    by_code[code] = province_id(c)
                    break
                except KeyError:
                    continue
    out: dict[str, float] = {}
    total = None
    for r in rows[head + 1 :]:
        if any(fold(c) == "toplam" for c in r[:3]):
            total = r
            break
        area = None
        for cell in r[:3]:
            try:
                area = province_id(cell)
                break
            except KeyError:
                continue
        if area is None:
            code = next((c for c in r[:3] if c in by_code), None)
            if code is None:
                continue
            area = by_code[code]
        count = float(r[col - 1] or 0)
        expected = counts[(area, "established", "company")]
        if abs(count - expected) > 0.5:
            raise ValueError(
                f"TOBB sermaye {path.name} {area}: sayı {count:.0f}, birikimli tablo {expected:.0f}"
            )
        out[area] = float(r[col] or 0)
    if len(out) != 81:
        raise ValueError(f"TOBB sermaye {path.name}: {len(out)} il")
    if (
        total is None
    ):  # 2015-2016 print no TOPLAM row; the counts check above still holds
        return out
    printed = [float(c) for c in total if re.fullmatch(r"\d+(\.\d+)?(e\+\d+)?", c)]
    if not any(abs(p - sum(out.values())) <= max(1.0, p * 1e-9) for p in printed):
        raise ValueError(
            f"TOBB sermaye {path.name}: iller {sum(out.values()):,.0f} TOPLAM'da yok"
        )
    return out


class TobbCapital:
    source_id = "tobb"
    indicator_id = "tobb_company_capital"

    def fetch(self) -> Path:
        return FILES

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "area_id": area,
                "period_start": dt.date(int(path.name[:4]), 1, 1),
                "dims": "",
                "value": value,
            }
            for path in sorted(FILES.glob("20??-12.xls*"))
            for area, value in read_capital(path).items()
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("try").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-07").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
        )


TOBB_ADAPTERS["tobb_company_capital"] = TobbCapital


LEGAL_FORMS = {"anonimsirketler": "joint_stock", "limitedsirketler": "limited"}


def read_foreign(path: Path) -> dict[tuple[str, str, str], float]:
    """ "YABANCI SERMAYE ve İLLER": companies founded in the year with a foreign partner.

    {(area, legal form, measure): value}. One block per legal form (joint stock, limited),
    each listing only the provinces that had such a company; the others are written as 0,
    since the block's total is the sum of its rows. Measures: the number of companies, the
    capital of those companies and the foreign partners' share of it (TL). The block's
    printed total covers the foreign share only, and that is what is checked.
    """
    import re

    import xlrd

    book = xlrd.open_workbook(path)
    if "YABANCI SERMAYE ve İLLER" not in book.sheet_names():
        return {}
    sheet = book.sheet_by_name("YABANCI SERMAYE ve İLLER")
    rows = [[str(v).strip() for v in sheet.row_values(r)] for r in range(sheet.nrows)]
    out: dict[tuple[str, str, str], float] = {}
    form = None
    columns: dict[str, int] = {}
    for r in rows:
        title = next((fold(c) for c in r if fold(c) in LEGAL_FORMS), None)
        if title:
            form, columns = LEGAL_FORMS[title], {}
            continue
        if form is None:
            continue
        if "İller" in r:
            columns = {
                "companies": r.index("Şirket Sayısı"),
                # 2012: "Şirketlerin Sermayesi", "Yabancı ..."; later "Sermaye Toplamı",
                # "Ülkenin Sermayesi"
                "capital": next(
                    j
                    for j, c in enumerate(r)
                    if "Serma" in c and "Ülke" not in c and "Yab" not in c
                ),
                "foreign_capital": next(
                    j for j, c in enumerate(r) if "Ülke" in c or "Yab" in c
                ),
                "name": r.index("İller"),
            }
            continue
        if not columns or not any(r):
            continue
        if any(fold(c) == "toplam" for c in r):
            printed = float(r[columns["foreign_capital"]])
            read = sum(
                v
                for (a, f, m), v in out.items()
                if f == form and m == "foreign_capital"
            )
            if abs(read - printed) > 0.5:
                raise ValueError(
                    f"TOBB yabancı sermaye {path.name} {form}: iller {read:,.0f}, Toplam {printed:,.0f}"
                )
            form, columns = None, {}
            continue
        if not re.fullmatch(r"\d+(\.0)?", r[columns["companies"]]):
            continue
        area = province_id(r[columns["name"]])
        for measure in ("companies", "capital", "foreign_capital"):
            key = (area, form, measure)
            if key in out:
                raise ValueError(f"TOBB yabancı sermaye {path.name}: {key} iki kez")
            out[key] = float(r[columns[measure]] or 0)
    forms = {f for _, f, _ in out}
    check_foreign_summary(book, path, out)
    if forms != set(LEGAL_FORMS.values()):
        raise ValueError(f"TOBB yabancı sermaye {path.name}: bloklar {forms}")
    for area in set(provinces().values()):
        for f in forms:
            for measure in ("companies", "capital", "foreign_capital"):
                out.setdefault((area, f, measure), 0.0)
    return out


def check_foreign_summary(
    book, path: Path, out: dict[tuple[str, str, str], float]
) -> None:
    """The provincial blocks against "YABANCI SERMAYE GENEL GÖRÜNÜM", whole-year block.

    The two sheets are not always the same count: 2018's provinces add up to 13,401 companies,
    the summary prints 13,405 (joint stock 1,127 against 1,129, capital 0.15 % short). Up to five, or 0.5 %, is let
    through; more stops the load.
    """
    if "YABANCI SERMAYE GENEL GÖRÜNÜM" not in book.sheet_names():
        return
    sheet = book.sheet_by_name("YABANCI SERMAYE GENEL GÖRÜNÜM")
    rows = [[str(v).strip() for v in sheet.row_values(r)] for r in range(sheet.nrows)]
    start = next((i for i, r in enumerate(rows) if any("Ocak" in c for c in r)), None)
    if start is None:
        return
    labels = {"sayi": "companies", "ortakolunansirketlerintoplamser": "capital"}
    for r in rows[start:]:
        key = next((fold(c) for c in r if c), "")
        measure = next((m for k, m in labels.items() if key.startswith(k)), None)
        if measure is None and "yabanc" in key and "oran" not in key:
            measure = "foreign_capital"
        if measure is None:
            continue
        numbers = [float(c) for c in r if c.replace(".", "", 1).isdigit()]
        for form, printed in zip(("joint_stock", "limited"), numbers, strict=False):
            read = sum(v for (a, f, m), v in out.items() if f == form and m == measure)
            if abs(read - printed) > max(5.0, printed * 0.005):
                raise ValueError(
                    f"TOBB yabancı sermaye {path.name} {form} {measure}: "
                    f"iller {read:,.0f}, genel görünüm {printed:,.0f}"
                )


class TobbForeign:
    source_id = "tobb"
    indicator_id = ""
    measure = ""

    def fetch(self) -> Path:
        return FILES

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "area_id": area,
                "period_start": dt.date(int(path.name[:4]), 1, 1),
                "dims": f"legal_form={form}",
                "value": value,
            }
            for path in sorted(FILES.glob("20??-12.xls*"))
            for (area, form, measure), value in read_foreign(path).items()
            if measure == self.measure
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("company" if self.measure == "companies" else "try").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-07").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
        )


for _indicator, _measure in (
    ("tobb_foreign_companies", "companies"),
    ("tobb_foreign_company_capital", "capital"),
    ("tobb_foreign_partner_capital", "foreign_capital"),
):
    TOBB_ADAPTERS[_indicator] = type(
        f"TobbForeign_{_measure}",
        (TobbForeign,),
        {"indicator_id": _indicator, "measure": _measure},
    )
