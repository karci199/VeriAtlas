r"""Shopping-centre trade: the only monthly reading of mall turnover there is.

AYD (Alışveriş Merkezleri ve Yatırımcıları Derneği) and Akademetre publish an index of
turnover per rentable square metre — base 2010 = 100 — with the lira figure behind it and
a visitor-count index. TÜİK's retail series does not separate malls, so nothing else in
the store measures this part of trade.

Read from `C:\veri-ham\ayd\avm_endeks.csv`, which `scripts/fetch_ayd_avm.py` builds from
the association's monthly pages; that script explains where the numbers sit in the prose.

* **Türkiye, İstanbul and Anadolu are a dimension, not three areas.** "Anadolu" is the
  country minus İstanbul — the association's own cut, not a place in the registry — so
  filing it as an area would invent a geography. All three sit at country level and the
  dimension says which slice each one is.
* **Nominal, undeflated.** The pages quote TÜFE next to the index and work out the real
  change in prose; the store keeps the measurement and leaves deflating to the reader,
  who already has CPI here.
* **A month the source never published is absent, not zero.** May 2025 answers 404 on
  AYD's own site; the series simply has no row for it.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..config import RAW
from ..schema import format_dims

SOURCE = RAW / "ayd" / "avm_endeks.csv"
VINTAGE = "2026-09"
RETRIEVED = dt.date(2026, 9, 19)

#: indicator id → (column, unit, dimension value). The per-m² figures share an indicator
#: and differ by slice; the two indices are Türkiye-wide and carry the same dimension so
#: a reader joining them does not meet a null.
MEASURES = {
    "mall_turnover_index": [("index_points", "index", "tr")],
    "mall_visitor_index": [("visitor_points", "index", "tr")],
    "mall_turnover_per_sqm": [
        ("try_per_sqm_TR", "try_per_square_metre", "tr"),
        ("try_per_sqm_istanbul", "try_per_square_metre", "istanbul"),
        ("try_per_sqm_anadolu", "try_per_square_metre", "anadolu"),
    ],
}


def month_start(label: str) -> dt.date:
    year, month = label.split("-")
    return dt.date(int(year), int(month), 1)


class MallIndex:
    source_id = "ayd_akademetre"
    indicator_id = ""

    def fetch(self) -> Path:
        return SOURCE

    def parse(self, raw: Path) -> pl.DataFrame:
        table = pl.read_csv(raw)
        records = []
        for column, unit, slice_id in MEASURES[self.indicator_id]:
            for row in table.select("period", column).to_dicts():
                value = row[column]
                if value is None or value == "":
                    continue
                records.append(
                    {
                        "indicator_id": self.indicator_id,
                        "area_id": "TR",
                        "area_level": "country",
                        "period_start": month_start(row["period"]),
                        "frequency": "monthly",
                        "dims": format_dims({"mall_area": slice_id}),
                        "value": float(value),
                        "unit": unit,
                        "quality_flag": "measured",
                        "vintage": VINTAGE,
                        "source_id": self.source_id,
                        "retrieved_at": RETRIEVED,
                    }
                )
        if not records:
            raise ValueError(f"{self.indicator_id}: satır yok")
        return pl.DataFrame(records)


AYD_ADAPTERS = {
    name: type(
        f"Mall{name.title().replace('_', '')}", (MallIndex,), {"indicator_id": name}
    )
    for name in MEASURES
}
