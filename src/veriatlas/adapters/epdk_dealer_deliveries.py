r"""EPDK petroleum: fuel delivered to dealers by province, 2012-2014 (tonnes).

The 2014 Petroleum Market Sector Report (`C:\veri-ham\epdk\files\petrol_yillik\dlC058Ircrk_.pdf`)
prints "Tablo 21: 2012, 2013 ve 2014 Yıllarında İllere Göre Bayiye Teslimler (ton)" over pages
69-72 (each page printed twice; pdfplumber indexes 68 and 70 are read). Only the last three
cells of a row, the product total for 2012, 2013 and 2014, are taken: the product columns
lose their empty cells in the text layer and cannot be told apart without column positions.

This is not the 2015+ `epdk_fuel_sales` series: that counts all domestic sales by
distributors, this counts what distributors delivered to their dealers.

Words are grouped into lines by a 2.5 pt tolerance, not by fixed bins: a fixed bin cut Düzce's
three totals onto a line of their own and the year totals came out short by exactly Düzce.
İstanbul is printed as two rows, Anadolu and Avrupa, and is added up.

Check: the provinces add up to the Genel Toplam row, every year.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import province_id

PDF = (
    RAW / "epdk" / "files" / "petrol_yillik" / "dlC058Ircrk_.pdf"
    if (RAW / "epdk").exists()
    else Path("C:/veri-ham/epdk/files/petrol_yillik/dlC058Ircrk_.pdf")
)
PAGES = (68, 70)
YEARS = (2012, 2013, 2014)
NUMBER = re.compile(r"\d{1,3}(\.\d{3})*$")


def read() -> dict[tuple[str, int], float]:
    import pdfplumber

    out: dict[str, list[float]] = {}
    grand = None
    pending = ""
    with pdfplumber.open(PDF) as pdf:
        for index in PAGES:
            words = sorted(
                pdf.pages[index].extract_words(x_tolerance=1.5, y_tolerance=2),
                key=lambda w: w["top"],
            )
            lines: list[list] = []
            for word in words:
                if lines and abs(lines[-1][0] - word["top"]) < 2.5:
                    lines[-1][1].append(word)
                else:
                    lines.append([word["top"], [word]])
            for _, group in lines:
                texts = [w["text"] for w in sorted(group, key=lambda w: w["x0"])]
                if "2710" in texts or "2012" in texts:
                    continue  # header: customs codes, year labels
                cells = [t for t in texts if NUMBER.match(t)]
                name = " ".join(t for t in texts if not NUMBER.match(t))
                if len(cells) < 10:
                    if name.startswith("İSTANBUL") and not cells:
                        pending = "İSTANBUL"
                    continue
                if pending:
                    name, pending = pending + " " + name, ""
                values = [float(c.replace(".", "")) for c in cells[-3:]]
                if name.startswith("Genel Toplam"):
                    grand = values
                    continue
                area = "TR-34" if name.startswith("İSTANBUL") else province_id(name)
                if area in out:
                    if area != "TR-34":
                        raise ValueError(f"EPDK bayiye teslim: {name} iki kez")
                    values = [a + b for a, b in zip(out[area], values, strict=True)]
                out[area] = values
    if len(out) != 81:
        raise ValueError(f"EPDK bayiye teslim: {len(out)} il")
    if grand is None:
        raise ValueError("EPDK bayiye teslim: Genel Toplam yok")
    for j, year in enumerate(YEARS):
        read_sum = sum(v[j] for v in out.values())
        if abs(read_sum - grand[j]) > 0.5:
            raise ValueError(
                f"EPDK bayiye teslim {year}: iller {read_sum:,.0f}, Genel Toplam {grand[j]:,.0f}"
            )
    rows = {
        (area, year): v[j] for area, v in out.items() for j, year in enumerate(YEARS)
    }
    rows.update({("TR", year): grand[j] for j, year in enumerate(YEARS)})
    return rows


class EpdkDealerDeliveries:
    source_id = "epdk"
    indicator_id = "epdk_fuel_dealer_deliveries"

    def fetch(self) -> Path:
        return PDF

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "area_id": area,
                "area_level": "country" if area == "TR" else "province",
                "period_start": dt.date(year, 1, 1),
                "dims": "",
                "value": value,
            }
            for (area, year), value in read().items()
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("annual").alias("frequency"),
            pl.lit("tonne").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2015-06").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
        )


EPDK_DEALER_ADAPTERS = {"epdk_fuel_dealer_deliveries": EpdkDealerDeliveries}
