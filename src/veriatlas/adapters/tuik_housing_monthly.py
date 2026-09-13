"""Housing sales published monthly only — by district, to foreigners, by nationality.

Pulled 2026-09-13 with `fetch_medas_simple.py konut-satis-02-ilce konut-satis-03
konut-satis-04 --aylik`, in 24-month slices. The export has two header rows: the area
(written once, over the first of its months) and under it the months (`04-Nisan`) — only
the months that carry a sale in that slice, so the columns differ from file to file.

Stored as **annual** sums of complete years. The page reads a year per row, and the monthly
detail answers no question the rest of the atlas asks; the partial current year is left
out rather than shown as a collapse. A year with no sale in any month has no row.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get, load
from ..schema import format_dims
from .tuik_median_age import area_of, single_province_regions
from .tuik_simple import LABEL, read_text
from .tuik_vital_district import area_at, districts_by_code

DOWNLOADS = RAW / "medas" / "basit"
MONTH = re.compile(r"^(\d{2})-")
NATION = re.compile(r"^(\d+)\.\s*\((.*)\)$")

#: stem → (indicator id, level of the files, dim or None)
MEASURES = {
    "konut-satis-02-ilce-aylik-district": ("housing_sales_district", "district", None),
    "konut-satis-03-aylik-country": ("housing_sales_foreigners", "country", None),
    "konut-satis-03-aylik-province": ("housing_sales_foreigners", "province", None),
    "konut-satis-04-aylik-country": (
        "housing_sales_by_nationality",
        "country",
        "nationality",
    ),
}


def columns(lines: list[str]) -> dict[int, tuple[str, int]]:
    """Column index → (area code, month), forward-filling the area over its months."""
    area_row = month_row = None
    for i, line in enumerate(lines[:8]):
        cells = line.split("|")
        if any(LABEL.match(c.strip()) for c in cells):
            area_row = i
        elif any(MONTH.match(c.strip()) for c in cells):
            month_row = i
            break
    if area_row is None or month_row is None:
        return {}
    areas = lines[area_row].split("|")
    months = lines[month_row].split("|")
    out, current = {}, None
    for index in range(3, max(len(areas), len(months))):
        label = LABEL.match(areas[index].strip()) if index < len(areas) else None
        if label:
            current = label.group("code")
        found = MONTH.match(months[index].strip()) if index < len(months) else None
        if found and current is not None:
            out[index] = (current, int(found.group(1)))
    return out


def read_export(path: Path, indicator_id: str, level: str, dim, context) -> list[dict]:
    lines = read_text(path).splitlines()
    cols = columns(lines)
    if not cols:
        raise KeyError(indicator_id + ": ay/alan basligi yok: " + path.name)
    rows, label, orphans, unknown = [], "", set(), set()
    for line in lines:
        cells = line.split("|")
        if len(cells) < 4 or not re.fullmatch(r"\d{4}", cells[2].strip()):
            continue
        year = int(cells[2])
        label = cells[1].strip() or label
        dims = ""
        if dim:
            found = NATION.match(label)
            if not found or found.group(1) not in load().dimensions[dim].values_tr:
                unknown.add(label)
                continue
            dims = format_dims({dim: found.group(1)})
        elif label != "Ölçüm bazında":
            unknown.add(label)
            continue
        for index, (code, month) in cols.items():
            cell = cells[index].strip() if index < len(cells) else ""
            if not cell:
                continue
            if level == "district":
                area = area_at(context.get(code, []), year)
            else:
                resolved = area_of(code, context)
                area = resolved[0] if resolved else None
            if area is None:
                orphans.add(code)
                continue
            rows.append(
                {
                    "area_id": area,
                    "area_level": level,
                    "year": year,
                    "month": month,
                    "dims": dims,
                    "value": float(cell),
                }
            )
    if unknown:
        raise KeyError(
            indicator_id + ": taninmayan etiket: " + ", ".join(sorted(unknown)[:10])
        )
    if orphans:
        raise KeyError(
            indicator_id
            + ": karsiligi olmayan alan kodu: "
            + ", ".join(sorted(orphans)[:10])
        )
    return rows


class MonthlyHousing:
    source_id = "tuik_medas"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 13)
    indicator_id = ""

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        records: list[dict] = []
        for stem, (indicator_id, level, dim) in MEASURES.items():
            if indicator_id != self.indicator_id:
                continue
            context = (
                districts_by_code()
                if level == "district"
                else single_province_regions()
            )
            for path in sorted(raw.glob("nufus-" + stem + "-*.csv")):
                records.extend(read_export(path, indicator_id, level, dim, context))
        if not records:
            raise ValueError("dosya yok: " + self.indicator_id)
        monthly = pl.DataFrame(records)
        # Slices overlap nowhere, so a repeated area-month means two files hold the same
        # month: summing it into the year would double it.
        if monthly.select("area_id", "year", "month", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni alan-ay iki kez")
        last = monthly["year"].max()
        complete = monthly.filter(pl.col("year") == last)["month"].max() == 12
        frame = monthly.group_by("area_id", "area_level", "year", "dims").agg(
            pl.col("value").sum()
        )
        if not complete:
            frame = frame.filter(pl.col("year") < last)
        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
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


MONTHLY_HOUSING_ADAPTERS = {
    "tuik_" + ident: type(
        "Tuik" + "".join(p.title() for p in ident.split("_")),
        (MonthlyHousing,),
        {"indicator_id": ident},
    )
    for ident in dict.fromkeys(spec[0] for spec in MEASURES.values())
}
