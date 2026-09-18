"""TESK: the tradesmen and craftsmen registry, by province.

The Confederation of Turkish Tradesmen and Craftsmen (TESK) keeps the registry every
tradesman must be entered in, and publishes two province tables from it:

* a snapshot — registered tradesmen, their workplaces and the number of chambers, next to
  the province population TESK itself quotes (we keep the counts, not their population);
* one table per year of what the registry gazette announced: registrations (`TESCİL`),
  amendments (`TADİL`), removal from the registry (`SİCİL TERKİN`) and removal of a trade
  from an entry that stays (`MESLEK TERKİN`).

The stock is not the flow's cumulative sum: a tradesman who moves province is registered
again, and the snapshot counts people while the gazette counts announcements.

**The tables are read line by line, not with `extract_table`.** pdfplumber's table finder
silently drops one province per file — Karabük from 2025, Kırklareli from the snapshot —
while both rows are plainly there in the text layer. A missing province would not look
like an error anywhere downstream, so the parser reads text and asserts all 81.

2005-2007 are scans with no text layer; 2008-2011 are unusable, `YEARS` says why.
"""

from __future__ import annotations

import datetime as dt
import re
from functools import cache
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import pdf_lines, province_id, provinces

RAW_DIR = RAW / "tesk"
SNAPSHOT = RAW_DIR / "kayitli-esnaf.pdf"

#: Years that can be read. 2008-2011 print two provinces side by side and their text layer
#: has holes — `BİNGÖL 468 4 478` carries three numbers for four columns and `HAKKARİ 9`
#: one, with no way to tell which column is which. Left out rather than guessed at.
YEARS = tuple(range(2012, 2026))

#: The snapshot is dated 31.08.2026 on the listing page; it is stored under that year.
SNAPSHOT_YEAR = 2026
SNAPSHOT_VINTAGE = "2026-08"

RETRIEVED = dt.date(2026, 9, 17)
SOURCE = "tesk"

#: `ADANA 8846 1373 2526 203`, twice on a line in the two-column years.
FLOW = re.compile(
    r"([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ.\s]+?)\s+(\d[\d.]*)\s+(\d[\d.]*)\s+(\d[\d.]*)\s+(\d[\d.]*)"
)
#: `ADANA 59266 62953 2283609 2.60% 77` — population and share are read past, not kept.
STOCK = re.compile(
    r"([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ.\s]+?)\s+(\d[\d.]*)\s+(\d[\d.]*)\s+(\d[\d.]*)\s+[\d,.]+%\s+(\d+)"
)

#: Column -> the group of its pattern that holds it. Written out rather than zipped over
#: `match.groups()`: the stock line has a population column we do not keep, and a zip that
#: runs short drops the last column silently — it stored the population as the chamber
#: count until a province with 15 million "chambers" gave it away.
FLOW_COLUMNS = {
    "registrations": 2,
    "amendments": 3,
    "deregistrations": 4,
    "trade_removals": 5,
}
STOCK_COLUMNS = {"tradesmen": 2, "workplaces": 3, "chambers": 5}


def count(text: str) -> int:
    return int(text.replace(".", ""))


def _rows(
    path: Path, pattern: re.Pattern[str], columns: tuple[str, ...]
) -> dict[str, dict]:
    """Province id -> the row's counts. Every province exactly once, or it raises."""
    found: dict[str, dict] = {}
    for line in pdf_lines(path):
        if "TOPLAM" in line.upper():
            continue
        for match in pattern.finditer(line):
            name = match.group(1).strip()
            if not name or name.upper() != name:
                continue
            area = province_id(name)
            if area in found:
                raise ValueError(f"TESK {path.name}: {name} iki kez")
            found[area] = {name: count(match.group(g)) for name, g in columns.items()}
    missing = sorted(set(provinces().values()) - set(found))
    if missing:
        raise ValueError(f"TESK {path.name}: eksik il {missing}")
    return found


@cache
def flow(year: int) -> dict[str, dict]:
    return _rows(RAW_DIR / f"sicil-{year}.pdf", FLOW, FLOW_COLUMNS)


@cache
def stock() -> dict[str, dict]:
    return _rows(SNAPSHOT, STOCK, STOCK_COLUMNS)


class TeskAdapter:
    source_id = SOURCE
    column: str
    #: The dictionary's unit for this indicator; people for the stock of tradesmen, plain
    #: items for workplaces, chambers and gazette announcements.
    unit = "item"

    def parse(self, raw: Path) -> pl.DataFrame:
        raise NotImplementedError


class TeskFlow(TeskAdapter):
    """One gazette measure across 2008-2025."""

    def fetch(self) -> Path:
        return RAW_DIR

    def parse(self, raw: Path) -> pl.DataFrame:
        areas: list[str] = []
        periods: list[dt.date] = []
        values: list[float] = []
        for year in YEARS:
            for area, row in sorted(flow(year).items()):
                areas.append(area)
                periods.append(dt.date(year, 1, 1))
                values.append(float(row[self.column]))
        return pl.DataFrame(
            {
                "indicator_id": self.indicator_id,
                "area_id": areas,
                "area_level": "province",
                "period_start": periods,
                "frequency": "annual",
                "dims": "",
                "value": values,
                "unit": self.unit,
                "quality_flag": "measured",
                "vintage": "2026-09",
                "source_id": self.source_id,
                "retrieved_at": RETRIEVED,
            }
        )


class TeskStock(TeskAdapter):
    """One snapshot measure, 31.08.2026."""

    def fetch(self) -> Path:
        return SNAPSHOT

    def parse(self, raw: Path) -> pl.DataFrame:
        rows = sorted(stock().items())
        return pl.DataFrame(
            {
                "indicator_id": self.indicator_id,
                "area_id": [a for a, _ in rows],
                "area_level": "province",
                "period_start": dt.date(SNAPSHOT_YEAR, 1, 1),
                "frequency": "annual",
                "dims": "",
                "value": [float(r[self.column]) for _, r in rows],
                "unit": self.unit,
                "quality_flag": "measured",
                "vintage": SNAPSHOT_VINTAGE,
                "source_id": self.source_id,
                "retrieved_at": RETRIEVED,
            }
        )


class TradesmenRegistrations(TeskFlow):
    indicator_id = "tradesmen_registrations"
    column = "registrations"


class TradesmenAmendments(TeskFlow):
    indicator_id = "tradesmen_amendments"
    column = "amendments"


class TradesmenDeregistrations(TeskFlow):
    indicator_id = "tradesmen_deregistrations"
    column = "deregistrations"


class TradesmenTradeRemovals(TeskFlow):
    indicator_id = "tradesmen_trade_removals"
    column = "trade_removals"


class RegisteredTradesmen(TeskStock):
    indicator_id = "registered_tradesmen"
    column = "tradesmen"
    unit = "person"


class TradesmenWorkplaces(TeskStock):
    indicator_id = "tradesmen_workplaces"
    column = "workplaces"


class TradesmenChambers(TeskStock):
    indicator_id = "tradesmen_chambers"
    column = "chambers"


TESK_ADAPTERS = {
    "tradesmen_registrations": TradesmenRegistrations,
    "tradesmen_amendments": TradesmenAmendments,
    "tradesmen_deregistrations": TradesmenDeregistrations,
    "tradesmen_trade_removals": TradesmenTradeRemovals,
    "registered_tradesmen": RegisteredTradesmen,
    "tradesmen_workplaces": TradesmenWorkplaces,
    "tradesmen_chambers": TradesmenChambers,
}
