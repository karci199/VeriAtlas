"""Wages set by the state: the minimum wage and civil-servant salaries by title.

**Minimum wage** — the Ministry of Labour's own period table (`scripts/fetch_minimum_wage.py`),
1996-08 onwards, 16-and-over. The table is a list of validity periods of unequal length
(1998 has four, 2016-2021 one a year), so it is turned into one row per calendar month
holding the wage in force on the 15th. A month two periods claim is an error, not a
choice: it would mean the source overlaps and one of the two wages is wrong.

**Civil-servant salaries** — no institution publishes a net salary per title as a series.
memurlar.net's salary robot computes the itemised payslip from the official coefficients
for any month from 2014 (`scripts/fetch_memurlarnet_salary.py`); one payslip per half-year
(February, August — July carries one-off transition items) is filed under the half-year's
first day. Profiles are fixed: single, no children, not a union member. Until 2021 the
minimum living allowance (AGİ) was paid on top of the net and the robot prints it below
the net line; it is added back so the series does not break when AGİ became a tax
exemption in 2022. Overtime, extra lessons, revolving-fund pay and family allowance are
not in it. This is a calculation from official parameters by a third party, so the rows
are flagged `estimated`.

**Pay parameters** — the Ministry of Treasury and Finance's budget office (HMB BÜMKO,
"Maaş İstatistikleri") keeps the official history of what civil-servant pay is computed
from: the three coefficients, the highest civil-servant salary, family allowance, the
severance-pay ceiling and the pay ceilings of contract staff. Each table is a list of
effective dates, not of months; like the minimum wage, it becomes one row per month
holding the value in force on the 15th, and the list runs to the last half-year the file
covers. Before 2005 the tables are in old lira and are divided by a million; the first
month on either side of the redenomination is compared, so a table that already switched
to new lira earlier would show as a millionfold drop instead of passing silently.

**Average wages** — the Strategy and Budget Office's economic-indicators table 8.6:
yearly average labour cost and net wage of public-sector workers, private-sector workers,
civil servants and minimum-wage earners, 2000-2017, in thousand old lira (= lira / 1000).
"""

from __future__ import annotations

import datetime as dt
import json
import re
from itertools import pairwise
from pathlib import Path
from typing import ClassVar

import polars as pl
import xlrd

from ..config import RAW

WAGE_FILE = RAW / "ucret" / "asgari" / "asgari_ucret_donemler.json"
SALARY_FILE = RAW / "ucret" / "memur" / "memurlarnet" / "salaries.jsonl"
PAY_DIR = RAW / "ucret" / "memur"
#: The HMB statistics files were downloaded in 2026-09 but stop at the January 2025
#: decision; a series that nothing later extends is filed until that half-year ends.
PAY_LAST_MONTH = dt.date(2025, 6, 1)
#: The decisions after it come from the half-yearly 'Mali ve Sosyal Haklar' circulars,
#: scanned PDFs read by hand into this file with their URLs. They run to the current
#: month, like the minimum wage.
CIRCULAR_FILE = RAW / "ucret" / "memur" / "genelge" / "genelge_degerleri.json"
CIRCULAR_LAST_MONTH = dt.date(2026, 9, 1)
#: Index of the highest civil-servant salary: 1500 + 8000 additional (Law 657, art. 43).
HIGHEST_SALARY_INDEX = 9500
REDENOMINATION = dt.date(2005, 1, 1)
REVISED_WITHIN_MONTH = {dt.date(2012, 1, 1)}
TR_MONTHS = {
    "ocak": 1,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "eylül": 9,
    "ekim": 10,
    "kasım": 11,
    "aralık": 12,
}
MEASURES = {"net": "net", "brut": "gross", "maliyet": "employer_cost"}
#: The last month filed: the wage decided for the rest of the year is not yet paid.
LAST_MONTH = dt.date(2026, 9, 1)


def _date(text: str) -> dt.date:
    """'29.02.2011' is in the source for a non-leap year; the period ends on the 28th."""
    day, month, year = (int(x) for x in text.split("."))
    while True:
        try:
            return dt.date(year, month, day)
        except ValueError:
            day -= 1


def _months(first: dt.date, last: dt.date):
    m = first.replace(day=1)
    while m <= last:
        yield m
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)


def _frame(
    indicator_id, periods, dims, values, frequency, unit, quality, source_id, retrieved
):
    return pl.DataFrame(
        {
            "indicator_id": indicator_id,
            "area_id": "TR",
            "area_level": "country",
            "period_start": periods,
            "frequency": frequency,
            "dims": dims,
            "value": values,
            "unit": unit,
            "quality_flag": quality,
            "vintage": "2026-09",
            "source_id": source_id,
            "retrieved_at": retrieved,
        }
    )


class MinimumWage:
    indicator_id = "minimum_wage"
    source_id = "csgb"

    def fetch(self) -> Path:
        return WAGE_FILE

    def parse(self, raw: Path) -> pl.DataFrame:
        periods = json.loads(raw.read_text(encoding="utf-8"))
        in_force: dict[dt.date, dict] = {}
        for p in periods:
            start, end = _date(p["start"]), _date(p["end"])
            for month in _months(start, end):
                if not start <= month.replace(day=15) <= end or month > LAST_MONTH:
                    continue
                if month in in_force:
                    raise ValueError(f"asgari ücret: {month} iki dönemde birden")
                in_force[month] = p
        gap = [m for m in _months(min(in_force), max(in_force)) if m not in in_force]
        if gap:
            raise ValueError(f"asgari ücret: dönemi olmayan aylar {gap[:5]}")
        rows = [
            (m, MEASURES[k], float(p[k]))
            for m, p in sorted(in_force.items())
            for k in MEASURES
        ]
        return _frame(
            self.indicator_id,
            [r[0] for r in rows],
            [f"wage_measure={r[1]}" for r in rows],
            [r[2] for r in rows],
            "monthly",
            "try_per_month",
            "measured",
            self.source_id,
            dt.date(2026, 9, 24),
        )


class CivilServantSalary:
    indicator_id = "civil_servant_salary"
    source_id = "memurlar_net"

    def fetch(self) -> Path:
        return SALARY_FILE

    def parse(self, raw: Path) -> pl.DataFrame:
        periods, dims, values = [], [], []
        seen = set()
        for line in raw.open(encoding="utf-8"):
            r = json.loads(line)
            items = {name: value for name, _, value in r["items"]}
            pay = dt.date.fromisoformat(r["date"])
            half = dt.date(pay.year, 1 if pay.month <= 6 else 7, 1)
            if (r["profile"], half) in seen:
                raise ValueError(f"memur maaşı: {r['profile']} {half} iki kez")
            seen.add((r["profile"], half))
            net = r["net"] + (items.get("Asgari Geçim İndirimi") or 0)
            gross = items["İstihaklar Toplamı"]
            for item, value in (("net", net), ("gross", gross)):
                periods.append(half)
                dims.append(f"civil_servant_profile={r['profile']};salary_item={item}")
                values.append(float(value))
        return _frame(
            self.indicator_id,
            periods,
            dims,
            values,
            "semiannual",
            "try_per_month",
            "estimated",
            self.source_id,
            dt.date(2026, 9, 24),
        )


def _cell_date(value, datemode: int) -> dt.date:
    """An effective date as the HMB sheets write it: an Excel serial or '1 Mart 1970'."""
    if isinstance(value, float):
        return xlrd.xldate_as_datetime(value, datemode).date()
    text = value.strip().replace("İ", "i").replace("I", "ı").lower()
    m = re.fullmatch(r"(\d{1,2})\s+(\w+)\s+(\d{4})", text)
    if not m or m[2] not in TR_MONTHS:
        raise ValueError(f"maaş tablosu: tarih okunamadı {value!r}")
    return dt.date(int(m[3]), TR_MONTHS[m[2]], int(m[1]))


def _range(text: str) -> tuple[dt.date, dt.date]:
    """'1.1.1995-31.3.1995' → both ends."""
    ends = re.findall(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if len(ends) != 2:
        raise ValueError(f"maaş tablosu: dönem okunamadı {text!r}")
    return tuple(dt.date(int(y), int(m), int(d)) for d, m, y in ends)


def _lira(day: dt.date, value: float) -> float:
    return value / 1e6 if day < REDENOMINATION else value


def _in_force(
    changes: list[tuple[dt.date, float]], name: str, last: dt.date = PAY_LAST_MONTH
) -> dict[dt.date, float]:
    """Effective-date list → the value in force on the 15th of every month.

    Dates out of order, or two rows for one date, mean the sheet was read wrong and are
    raised — except January 2012, which the HMB tables list twice ('Ocak-1', 'Ocak-2'):
    the coefficient was raised again within the month for the inflation difference. The
    coefficient table itself keeps only the second, so the later row wins.
    """
    for (d1, v1), (d2, v2) in pairwise(changes):
        if d2 < d1 or (d2 == d1 and v1 != v2 and d1 not in REVISED_WITHIN_MONTH):
            raise ValueError(f"{name}: tarih sırası bozuk {d1} {d2}")
    out = {}
    for month in _months(changes[0][0], last):
        day = month.replace(day=15)
        current = [v for d, v in changes if d <= day]
        if current:
            out[month] = current[-1]
    _check_redenomination(out, name)
    return out


def _check_redenomination(series: dict[dt.date, float], name: str) -> None:
    before = series.get(dt.date(2004, 12, 1))
    after = series.get(REDENOMINATION)
    if before and after and not 0.8 <= after / before <= 1.6:
        raise ValueError(f"{name}: 2005 YTL geçişinde kırılma {before} → {after}")


def _sheet(file: str, index: int = 0):
    book = xlrd.open_workbook(PAY_DIR / file)
    return book.sheet_by_index(index), book.datemode


def _dated_rows(sheet, datemode, first_row: int):
    """Rows whose first cell is an effective date; footnotes and headers are skipped."""
    for i in range(first_row, sheet.nrows):
        row = sheet.row_values(i)
        if row[0] == "" or (
            isinstance(row[0], str) and not row[0].strip()[:1].isdigit()
        ):
            continue
        yield _cell_date(row[0], datemode), row


def _circulars() -> list[dict]:
    return json.loads(CIRCULAR_FILE.read_text(encoding="utf-8"))["circulars"]


def _extended(changes, key: str, scale: float = 1.0):
    """The HMB sheet's changes followed by the circulars' values for `key`.

    A circular dated on or before the sheet's last change would mean the sheet was newer
    than assumed; that is raised, not merged.
    """
    added = [
        (dt.date.fromisoformat(c["effective"]), c[key] * scale) for c in _circulars()
    ]
    if added[0][0] <= changes[-1][0]:
        raise ValueError(f"{key}: genelge {added[0][0]} tablodan yeni değil")
    return changes + added


def _monthly_rows(indicator_id, series: dict[str, dict[dt.date, float]], unit, source):
    rows = [(m, key, v) for key, s in series.items() for m, v in sorted(s.items())]
    return _frame(
        indicator_id,
        [r[0] for r in rows],
        [r[1] for r in rows],
        [float(r[2]) for r in rows],
        "monthly",
        unit,
        "measured",
        source,
        dt.date(2026, 9, 24),
    )


class _HmbPay:
    source_id = "hmb_bumko"
    file = ""

    def fetch(self) -> Path:
        return PAY_DIR / self.file


class CivilServantPayCoefficient(_HmbPay):
    indicator_id = "civil_servant_pay_coefficient"
    file = "hmb_Memur-Maas-Hesabinda-Kullanilan-Katsayilar.xls"
    #: Column → dim value. The base-salary coefficient starts in 1989.
    COLUMNS: ClassVar[dict] = {1: "monthly", 2: "side_payment", 3: "base_salary"}

    def parse(self, raw: Path) -> pl.DataFrame:
        sheet, datemode = _sheet(raw.name)
        series = {}
        for col, key in self.COLUMNS.items():
            changes = [
                (day, _lira(day, row[col]))
                for day, row in _dated_rows(sheet, datemode, 2)
                if row[col] != ""
            ]
            series[f"pay_coefficient={key}"] = _in_force(
                _extended(changes, key), f"katsayı {key}", CIRCULAR_LAST_MONTH
            )
        return _monthly_rows(self.indicator_id, series, "coefficient", self.source_id)


class HighestCivilServantSalary(_HmbPay):
    indicator_id = "highest_civil_servant_salary"
    file = "hmb_En-Yuksek-Devlet-Memuru-Ayligi.xls"

    def parse(self, raw: Path) -> pl.DataFrame:
        sheet, datemode = _sheet(raw.name)
        changes = [(d, _lira(d, row[4])) for d, row in _dated_rows(sheet, datemode, 2)]
        # The circulars give the coefficient, not this amount; it is the coefficient
        # times the index, which the sheet itself does for every row.
        changes = _extended(changes, "monthly", HIGHEST_SALARY_INDEX)
        series = {"": _in_force(changes, "en yüksek memur aylığı", CIRCULAR_LAST_MONTH)}
        return _monthly_rows(self.indicator_id, series, "try_per_month", self.source_id)


class FamilyAllowance(_HmbPay):
    """Spouse from 1978, one child from mid-1984.

    Before July 1984 the child amount depended on the child's school (primary, secondary,
    higher, other); that split is not kept, so the child series starts when a single
    amount does. The amount is the last filled cell: early spouse rows hold the amount
    alone, later rows coefficient, index and amount.

    The circulars do not state the allowance. It is the monthly coefficient times the
    index (2273 spouse, 250 child since 2020), which the sheet's own last row carries and
    is checked against; the amounts this gives for January 2026 (3.154,63 and 346,97)
    are the ones paid.
    """

    indicator_id = "civil_servant_family_allowance"
    file = "hmb_Aile-Yardimi-Odenegi.xls"
    CHILD_FROM = dt.date(1984, 7, 1)

    def parse(self, raw: Path) -> pl.DataFrame:
        series = {}
        for index, key in ((0, "spouse"), (1, "child")):
            sheet, datemode = _sheet(raw.name, index)
            changes = []
            for day, row in _dated_rows(sheet, datemode, 3):
                if key == "child" and day < self.CHILD_FROM:
                    continue
                filled = [v for v in row[1:] if v != ""]
                if key == "child" and len(filled) != 3:
                    raise ValueError(f"çocuk yardımı: {day} satırı beklenmedik {row}")
                changes.append((day, _lira(day, filled[-1])))
            coefficient, index_, amount = filled
            if abs(coefficient * index_ - amount) > 0.01:
                raise ValueError(
                    f"aile yardımı {key}: son satır katsayı × gösterge değil"
                )
            changes = _extended(changes, "monthly", index_)
            series[f"family_member={key}"] = _in_force(
                changes, f"aile yardımı {key}", CIRCULAR_LAST_MONTH
            )
        return _monthly_rows(self.indicator_id, series, "try_per_month", self.source_id)


class SeverancePayCeiling(_HmbPay):
    indicator_id = "severance_pay_ceiling"
    file = "hmb_Kidem-Tazminati-Tavanlari.xls"

    def parse(self, raw: Path) -> pl.DataFrame:
        sheet, datemode = _sheet(raw.name)
        changes = [(d, _lira(d, row[1])) for d, row in _dated_rows(sheet, datemode, 2)]
        changes = _extended(changes, "severance_pay_ceiling")
        series = {"": _in_force(changes, "kıdem tazminatı tavanı", CIRCULAR_LAST_MONTH)}
        return _monthly_rows(
            self.indicator_id, series, "try_per_service_year", self.source_id
        )


class ContractStaffPayCeiling(_HmbPay):
    """Validity periods, not effective dates, and they overlap on purpose: in 1997 the
    budget law set a ceiling for January-June and a cabinet decree raised it for the same
    months. The later row in the sheet is the later decision and wins."""

    indicator_id = "contract_staff_pay_ceiling"
    file = "hmb_Sozlesmeli-Personel-Ucret-Tavanlari.xls"
    SHEETS: ClassVar[dict] = {
        0: "soe_decree_399",
        1: "decree_7_15754",
        2: "position_based",
    }

    def parse(self, raw: Path) -> pl.DataFrame:
        series = {}
        for index, key in self.SHEETS.items():
            sheet, _ = _sheet(raw.name, index)
            months: dict[dt.date, float] = {}
            for i in range(2, sheet.nrows):
                row = sheet.row_values(i)
                if not isinstance(row[2], float) or not re.search(r"\d{4}", row[1]):
                    continue
                start, end = _range(row[1])
                for month in _months(start, end):
                    if start <= month.replace(day=15) <= end:
                        months[month] = _lira(start, row[2])
            # The circulars name the ceiling of two of the three types; the third
            # (position-based) is only raised by a percentage, so it stops with the sheet.
            for c in _circulars() if key in _circulars()[0] else []:
                start = dt.date.fromisoformat(c["effective"])
                end = min(dt.date.fromisoformat(c["end"]), CIRCULAR_LAST_MONTH)
                if start <= max(months):
                    raise ValueError(f"sözleşmeli tavanı {key}: genelge tablodan eski")
                for month in _months(start, end):
                    months[month] = c[key]
            gap = [m for m in _months(min(months), max(months)) if m not in months]
            if gap:
                raise ValueError(f"sözleşmeli tavanı {key}: boş aylar {gap[:5]}")
            _check_redenomination(months, f"sözleşmeli tavanı {key}")
            series[f"contract_staff_type={key}"] = months
        return _monthly_rows(self.indicator_id, series, "try_per_month", self.source_id)


class AverageWageBySector:
    """SBB table 8.6: two blocks of nine years, each with a labour-cost and a net part."""

    indicator_id = "average_wage_by_sector"
    source_id = "sbb"
    GROUPS: ClassVar[dict] = {
        "KAMU": "public_worker",
        "ÖZEL": "private_worker",
        "MEMUR": "civil_servant",
        "ASGARİ": "minimum_wage",
    }
    #: 18 years × 4 groups × 2 measures, less private-sector 2016-2017 which SBB marks '-'.
    EXPECTED = 18 * 4 * 2 - 4

    def fetch(self) -> Path:
        return PAY_DIR / "T-8.6.xls"

    def parse(self, raw: Path) -> pl.DataFrame:
        sheet = xlrd.open_workbook(raw).sheet_by_index(0)
        periods, dims, values = [], [], []
        years, measure = [], None
        for i in range(sheet.nrows):
            row = sheet.row_values(i)
            if isinstance(row[3], float) and row[3] > 1990 and row[1] == "":
                years = [int(v) for v in row[3:]]
            elif str(row[0]).startswith("A."):
                measure = "employer_cost"
            elif str(row[0]).startswith("B."):
                measure = "net"
            elif row[1]:
                group = [g for k, g in self.GROUPS.items() if row[1].startswith(k)]
                if len(group) != 1:
                    raise ValueError(f"SBB 8.6: tanınmayan satır {row[1]!r}")
                for year, value in zip(years, row[3:], strict=True):
                    if value == "-":
                        continue
                    periods.append(dt.date(year, 1, 1))
                    dims.append(f"wage_measure={measure};employee_group={group[0]}")
                    values.append(value / 1000)
        if len(values) != self.EXPECTED or len(set(zip(periods, dims))) != len(values):
            raise ValueError(
                f"SBB 8.6: {len(values)} değer, {self.EXPECTED} bekleniyordu"
            )
        return _frame(
            self.indicator_id,
            periods,
            dims,
            values,
            "annual",
            "try_per_month",
            "measured",
            self.source_id,
            dt.date(2026, 9, 24),
        )


WAGE_ADAPTERS = {
    "minimum_wage": MinimumWage,
    "civil_servant_salary": CivilServantSalary,
    "civil_servant_pay_coefficient": CivilServantPayCoefficient,
    "highest_civil_servant_salary": HighestCivilServantSalary,
    "civil_servant_family_allowance": FamilyAllowance,
    "severance_pay_ceiling": SeverancePayCeiling,
    "contract_staff_pay_ceiling": ContractStaffPayCeiling,
    "average_wage_by_sector": AverageWageBySector,
}
