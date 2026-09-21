r"""How many postal codes PTT gives a district — the semt layer, from the source.

`scripts/fetch_ptt_postal_codes.py` reads ptt.gov.tr's own query endpoint and writes one
row per address the post office knows: province, district, neighbourhood, street, code
(`C:\veri-ham\ptt\postakodu_<date>.csv`, 1,27 million rows on the 2026-09-18 snapshot).
This adapter keeps one number out of it: the count of distinct postal codes in a district.

**That count is the semt count.** `docs/semt.md` measured it on the 2022 file and the
2026 snapshot repeats it exactly: 325 districts hold one code, 301 two, 132 three, at most
21 (Osmangazi and Seyhan). Semt has no legal definition, no boundary and no registry; the
only country-wide list is the name PTT gives a postal code. So this indicator is not
"postal codes" as trivia — it is how finely the post office cuts a district up, and it is
the closest thing to a nationwide semt count that exists.

What is deliberately *not* made into an indicator:

* **Street counts.** The file has 1,27 million street rows, but they are delivery points,
  not a street census: 39.120 of the 72.640 settlements carry exactly one row, because in
  a village PTT lists the village itself rather than its streets. A "streets per district"
  indicator would read as though villages had one street each.
* **The neighbourhood list.** It is registry material, not a measurement. It belongs next
  to `areas_tr_neighbourhoods.csv` as an audit, not in the fact table.

Snapshot, not a series: PTT publishes today's numbering and keeps no history. Rows are
filed under the snapshot's year and replaced, not appended to, when it is taken again.

The district code PTT returns is the same `medas_code` the registry already carries —
Aladağ is 1757 in both — so the join needs no name matching. All 973 codes resolve; the
registry's remaining 23 are districts abolished before this snapshot.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections import defaultdict
from functools import cache
from pathlib import Path

import polars as pl

from ..areas import load_districts
from ..config import RAW

FOLDER = RAW / "ptt"
SOURCE = "ptt_postakodu"

#: Districts Türkiye has. A snapshot short of this is a rate-limited run, not a smaller
#: country — the first attempt lost 20 districts to HTTP 429 and looked complete.
EXPECTED_DISTRICTS = 973


def snapshot() -> Path:
    """The newest saved snapshot; the file name carries the day it was taken."""
    files = sorted(FOLDER.glob("postakodu_*.csv"))
    if not files:
        raise FileNotFoundError(
            f"PTT posta kodu dökümü yok: {FOLDER} (scripts/fetch_ptt_postal_codes.py)"
        )
    return files[-1]


@cache
def _registry() -> dict[int, str]:
    """PTT's district code -> our area id, via the registry's `medas_code`."""
    frame = load_districts().filter(pl.col("medas_code").is_not_null())
    return {
        int(code): area
        for code, area in zip(frame["medas_code"], frame["area_id"], strict=True)
    }


@cache
def codes_by_district() -> tuple[dt.date, dict[str, int]]:
    """(snapshot date, {area_id: distinct postal codes}), all 973 districts or it raises."""
    path = snapshot()
    taken = dt.date.fromisoformat(path.stem.rsplit("_", 1)[1])
    registry = _registry()
    found: dict[str, set[str]] = defaultdict(set)
    unknown: set[int] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            code = int(row["ilce_kodu"])
            area = registry.get(code)
            if area is None:
                unknown.add(code)
                continue
            found[area].add(row["posta_kodu"])
    if unknown:
        raise ValueError(f"PTT: kayıt defterinde olmayan ilçe kodu {sorted(unknown)}")
    if len(found) < EXPECTED_DISTRICTS:
        raise ValueError(
            f"PTT: {len(found)} ilçe var, {EXPECTED_DISTRICTS} bekleniyor — "
            "çekim yarım kalmış olabilir (429), --eksik ile tamamla"
        )
    return taken, {area: len(codes) for area, codes in found.items()}


class PostalCodes:
    """Distinct postal codes per district, and their province totals."""

    indicator_id = "postal_codes"
    source_id = SOURCE

    def fetch(self) -> Path:
        return snapshot()

    def parse(self, raw: Path) -> pl.DataFrame:
        taken, districts = codes_by_district()
        # A postal code belongs to one district, so a province's codes are the sum of its
        # districts' — no code is shared across a provincial boundary (the first two
        # digits of a Turkish postal code *are* the province's plate number).
        provinces: dict[str, int] = defaultdict(int)
        for area, count in districts.items():
            provinces[area[:5]] += count
        records = [
            {"area_id": area, "area_level": level, "value": float(count)}
            for level, rows in (("district", districts), ("province", provinces))
            for area, count in sorted(rows.items())
        ]
        return pl.DataFrame(records).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(dt.date(taken.year, 1, 1)).alias("period_start"),
            pl.lit("annual").alias("frequency"),
            pl.lit("").alias("dims"),
            pl.lit("item").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(taken.strftime("%Y-%m")).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(taken).alias("retrieved_at"),
        )


PTT_POSTAL_ADAPTERS = {"postal_codes": PostalCodes}
