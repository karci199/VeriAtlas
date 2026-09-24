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
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl

from ..config import RAW

WAGE_FILE = RAW / "ucret" / "asgari" / "asgari_ucret_donemler.json"
SALARY_FILE = RAW / "ucret" / "memur" / "memurlarnet" / "salaries.jsonl"
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


WAGE_ADAPTERS = {
    "minimum_wage": MinimumWage,
    "civil_servant_salary": CivilServantSalary,
}
