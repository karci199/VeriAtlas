"""Registered lawyers by province and sex — Union of Turkish Bar Associations (TBB).

TBB publishes the year-end count of lawyers per bar association as one news page a year
("<year> Avukat Sayıları (31.12.<year>)", barobirlik.org.tr/Haberler/...). Pages found for
1999, 2002-2010, 2012 and 2016-2024 are saved as `baro/<year>.html` (2001 gives only a
total and is skipped; 2000, 2011, 2013-2015 and 2025 were not found on the site). Columns
are read by header (ERKEK/BAY, KADIN/BAYAN) because their order changes between years.
A bar is placed in its province by name ("ANKARA 2 NOLU BAROSU" → Ankara); several bars of
one province are summed. The two regional bars of 2017 (Gümüşhane-Bayburt, Kars-Ardahan)
cannot be split and are counted in their seat, the first-named province. The bars must add up to the page's TOPLAM row, or the load stops.
"""

from __future__ import annotations

import datetime as dt
import html
import re
from pathlib import Path

import polars as pl

from ..config import DATA, RAW
from ..indicators import get
from ..schema import format_dims

DOWNLOADS = RAW / "baro"
SEX = {"ERKEK": "male", "BAY": "male", "KADIN": "female", "BAYAN": "female"}
FIXES = {"AFYON": "AFYONKARAHİSAR", "İÇEL": "MERSİN", "K.MARAŞ": "KAHRAMANMARAŞ"}


def turkish_upper(text: str) -> str:
    return text.replace("i", "İ").replace("ı", "I").upper()


def number(text: str) -> float:
    text = text.replace(".", "").replace(",", "").strip()
    return float(text) if text and text != "-" else 0.0


def read_year(path: Path, ids: dict[str, str]) -> list[tuple[str, str, float]]:
    page = path.read_text(encoding="utf-8")
    rows = [
        [
            html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c))).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.DOTALL)
        ]
        for tr in re.findall(r"<tr.*?</tr>", page, flags=re.DOTALL)
    ]
    rows = [r for r in rows if any(r)]
    head = [turkish_upper(h) for h in rows[0]]
    cols = {SEX[h]: i for i, h in enumerate(head) if h in SEX}
    if set(cols) != {"male", "female"}:
        return []
    out, total, unknown = [], None, set()
    for r in rows[1:]:
        if r[0].strip().startswith("*"):
            continue  # footnote rows ("* İzmir Barosu'nun düzeltme yazısı")
        name = turkish_upper(r[0]).replace("*", "").strip()
        values = {s: number(r[i]) for s, i in cols.items() if i < len(r)}
        if name == "TOPLAM":
            total = values
            continue
        key = re.sub(r"\s*\d+\s*(NOLU|NO'LU|NO.LU)?\s*", " ", name)
        key = re.sub(r"\s*BAROSU\s*$", "", key).strip()
        key = key.split("-")[0].replace(" BÖLGE", "").strip()  # regional bar → its seat
        key = FIXES.get(key, key)
        if key not in ids:
            unknown.add(r[0])
            continue
        out += [(ids[key], s, v) for s, v in values.items()]
    if unknown:
        raise KeyError(f"baro {path.stem}: taninmayan baro: {sorted(unknown)}")
    # 2008: İzmir's row was corrected afterwards (marked *), the TOPLAM row was not.
    if path.stem == "2008":
        return out
    for s in ("male", "female"):
        got = sum(v for _, k, v in out if k == s)
        # The page's own TOPLAM is off by a few in two years (2005: 1, 2024: 207 of 103,034);
        # the bars are kept and a gap above 0.5 % stops the load.
        if total is None or abs(got - total[s]) > 0.005 * total[s]:
            raise ValueError(f"baro {path.stem}: {s} toplami tutmuyor {got} {total}")
    return out


class TbbLawyers:
    source_id = "tbb_baro"
    vintage = "2025-01"
    retrieved_at = dt.date(2026, 9, 26)
    indicator_id = "lawyers"

    def fetch(self) -> Path:
        if not (DOWNLOADS / "liste.json").exists():
            raise FileNotFoundError("baro dokumu yok: " + str(DOWNLOADS))
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        provinces = pl.read_csv(DATA / "areas_tr.csv").filter(
            pl.col("area_level") == "province"
        )
        ids = {
            turkish_upper(n): a
            for a, n in provinces.select("area_id", "name_tr").iter_rows()
        }
        records = []
        for path in sorted(raw.glob("*.html")):
            year = int(path.stem)
            for area, sex, value in read_year(path, ids):
                records.append((area, year, sex, value))
        frame = (
            pl.DataFrame(
                records, schema=["area_id", "year", "sex", "value"], orient="row"
            )
            .group_by("area_id", "year", "sex")
            .agg(pl.col("value").sum())
        )
        tr = (
            frame.group_by("year", "sex")
            .agg(pl.col("value").sum())
            .with_columns(pl.lit("TR").alias("area_id"))
        )
        frame = pl.concat([frame, tr.select(frame.columns)])
        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.when(pl.col("area_id") == "TR")
            .then(pl.lit("country"))
            .otherwise(pl.lit("province"))
            .alias("area_level"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.col("sex")
            .map_elements(lambda s: format_dims({"sex": s}), return_dtype=pl.String)
            .alias("dims"),
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
