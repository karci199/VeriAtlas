r"""EPDK petroleum: fuel delivered to dealers by province, 2011-2014 (tonnes).

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

2011 comes from the 2011 report (`WuVmeFaaXBw_.pdf`), "Tablo 3.18 - İllere Göre Akaryakıt
Satışları (ton)", pages 41-43 (pdfium indexes 51-53). The page before it closes the distributors'
deliveries to licensed stations, and the table is their province split: the same measure under
another title (Türkiye 15.8 million tonnes in 2011, 17.0 in 2012). Its text layer keeps every cell,
so the ten numbers of a row are nine products and the province total; only the total is taken,
and each row's products must add up to it. The 2010 report prints no provincial table.

Check: the provinces add up to the Genel Toplam row (2011: Ürün Toplamı), every year.
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
PDF_2011 = PDF.with_name("WuVmeFaaXBw_.pdf")
PAGES_2011 = (51, 52, 53)
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


def read_2011() -> dict[tuple[str, int], float]:
    import pypdfium2

    doc = pypdfium2.PdfDocument(PDF_2011)
    text = "\n".join(doc[i].get_textpage().get_text_range() for i in PAGES_2011)
    out: dict[str, float] = {}
    grand = None
    for line in text.splitlines():
        parts = line.split()
        cells = [p for p in parts if NUMBER.match(p)]
        name = " ".join(p for p in parts if not NUMBER.match(p))
        if len(cells) != 10 or not name:
            continue
        values = [float(c.replace(".", "")) for c in cells]
        if abs(sum(values[:9]) - values[9]) > 9:  # rounded to the tonne per product
            raise ValueError(
                f"EPDK bayiye teslim 2011: {name} ürünleri toplamı tutmuyor"
            )
        if name.startswith("Ürün Toplamı"):
            grand = values[9]
            continue
        area = "TR-34" if name.startswith("İSTANBUL") else province_id(name)
        if area in out and area != "TR-34":
            raise ValueError(f"EPDK bayiye teslim 2011: {name} iki kez")
        out[area] = out.get(area, 0.0) + values[9]
    if len(out) != 81 or grand is None:
        raise ValueError(f"EPDK bayiye teslim 2011: {len(out)} il, toplam {grand}")
    if abs(sum(out.values()) - grand) > 2:  # tonne rounding
        raise ValueError(
            f"EPDK bayiye teslim 2011: iller {sum(out.values()):,.0f}, toplam {grand:,.0f}"
        )
    return {**{(a, 2011): v for a, v in out.items()}, ("TR", 2011): grand}


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
            for (area, year), value in {**read_2011(), **read()}.items()
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
