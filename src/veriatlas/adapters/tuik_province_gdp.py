r"""Provincial GDP in liras: the level the store had every ratio of, but not the amount.

MEDAS publishes provincial GDP as shares, indices, growth rates and GDP per capita — nine
indicators, all of them derived. What it does not publish is the amount itself, so a
question as plain as "how many lira of value added does Bolu produce" had no answer. The
data portal's two tables carry it (`C:\veri-ham\tuik_portal\dosya\tablo`, downloaded
2026-09-19):

    T1  cari fiyatlarla, bin TL        → province_gdp_current
    T2  zincirlenmiş hacim, bin TL     → province_gdp_chained

T2 also prints the 2009=100 index and the change ratio next to each volume; those two are
already in the store from MEDAS (`province_gdp_index_sector`, `province_gdp_growth_sector`)
and are skipped rather than loaded twice under a second name.

Three things the file does quietly:

* **The area code is İBBS-3, and the eastern provinces use letters** — `TRA11`, `TRC33`.
  As everywhere else here the code is ignored and the province name decides, so a
  `TR\d+` pattern cannot drop the east.
* **Manufacturing sits inside industry.** `İmalat sanayi` (C) is a part of `Sanayi` (B-E),
  not a sibling; adding the columns double-counts it. The dimension keeps the source's own
  set and the definition says so.
* **The sector columns do not sum to GDP.** `Sektörler toplamı` is value added; GDP adds
  `Vergi-sübvansiyon` on top. All three are stored, so nobody has to reconstruct them.

The country row (`TR`) is kept: it is the source's own total, and a reader checking that
the provinces add up needs it.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl
import xlrd

from ..config import RAW
from ..schema import format_dims
from .kgm import province_id

FOLDER = RAW / "tuik_portal" / "dosya" / "tablo"
CURRENT = "gsyh_il_0_İl bazında gayrisafi yurt içi hasıla iktisadi faaliyet kollarına A10 g.xls"
CHAINED = "gsyh_il_1_İl bazında gayrisafi yurt içi hasıla iktisadi faaliyet kollarına A10 g.xls"

#: T1 has one header row; T2 spends an extra row on the sector name above its three
#: columns, so both the header and the first data row sit one lower.
HEADER_ROW, FIRST_ROW = 3, 4
CHAINED_HEADER_ROW, CHAINED_FIRST_ROW = 4, 5

#: The source's Turkish column head → the dimension value. Matched on the first line of
#: the cell, because every head carries its English translation underneath.
SECTORS = {
    "Tarım, ormancılık ve balıkçılık": "a",
    "Sanayi": "b_e",
    "İmalat sanayi": "c",
    "İnşaat": "f",
    "Ticaret, ulaştırma, konaklama ve yiyecek hizmetleri": "g_i",
    "Bilgi ve iletişim": "j",
    "Finans ve sigorta faaliyetleri": "k",
    "Gayrimenkul faaliyetleri": "l",
    "Mesleki, idari ve destek hizmet faaliyetleri": "m_n",
    "Kamu yönetimi, eğitim, insan sağlığı ve sosyal hizmet faaliyetleri": "o_q",
    "Diğer hizmet faaliyetleri": "r_u",
    "Sektörler toplamı": "total_sectors",
    "Vergi-sübvansiyon": "taxes_subsidies",
    "GSYH": "gdp",
    # T2 spells the same three differently — a capital S in the tax row, and GDP written
    # out at purchasers' prices. Left unmapped they are not an error the file reports;
    # the totals simply go missing while the eleven sectors load fine.
    "Vergi-Sübvansiyon": "taxes_subsidies",
    "Gayrisafi yurtiçi hasıla (alıcı fiyatlarıyla)": "gdp",
}
#: T2 repeats every sector three times — volume, index, change ratio. Only the volume is
#: read; the other two are already in the store from MEDAS.
VOLUME = "Hacim"

CODE = re.compile(r"^TR[0-9A-Z]*$")


#: The English translation of a column head is not always on its own line: in T1 most
#: heads run `Imalat sanayi<...spaces...>Manufacturing<...spaces...>C` on one line.
#: Splitting on the newline alone matched three columns of fourteen and silently
#: loaded a fifth of the table, so the cut is made at the first run of two or more
#: spaces as well.
GAP = re.compile(r"\s{2,}")


def head(cell: object) -> str:
    first_line = str(cell).split(chr(10))[0].strip()
    return GAP.split(first_line)[0].strip()


def read(path: Path, chained: bool) -> list[tuple[str, str, int, str, float]]:
    """(area code, province name, year, sector, value) for every filled cell."""
    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    header = CHAINED_HEADER_ROW if chained else HEADER_ROW
    first = CHAINED_FIRST_ROW if chained else FIRST_ROW
    columns: dict[int, str] = {}
    current = ""
    for column in range(3, sheet.ncols):
        label = head(sheet.cell_value(header, column))
        if chained:
            # T2's sector name sits one row higher, above the first of its three columns.
            above = head(sheet.cell_value(header - 1, column))
            if above in SECTORS:
                current = SECTORS[above]
            if label.startswith(VOLUME) and current:
                # Consumed: xlrd reports a merged sector head only over its first cell,
                # so a sector left standing would claim the next group's volume too and
                # the same value would arrive twice under two sector names.
                columns[column] = current
                current = ""
        elif label in SECTORS:
            columns[column] = SECTORS[label]
    if not columns:
        raise ValueError(f"{path.name}: sutun basligi taninmadi")

    rows: list[tuple[str, str, int, str, float]] = []
    code = name = ""
    for row in range(first, sheet.nrows):
        label = str(sheet.cell_value(row, 0)).strip()
        if label and CODE.match(label):
            code, name = label, str(sheet.cell_value(row, 1)).strip()
        elif label:
            break  # the source note at the foot of the sheet
        if not code:
            continue
        year_cell = str(sheet.cell_value(row, 2)).strip()
        if not year_cell:
            continue
        year = int(float(year_cell))
        for column, sector in columns.items():
            text = str(sheet.cell_value(row, column)).strip().replace(",", ".")
            if not text or text == "-":
                continue
            rows.append((code, name, year, sector, float(text)))
    return rows


class ProvinceGdp:
    source_id = "tuik_portal"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 19)
    indicator_id = ""
    filename = ""
    chained = False

    def fetch(self) -> Path:
        return FOLDER / self.filename

    def parse(self, raw: Path) -> pl.DataFrame:
        records = []
        for code, name, year, sector, value in read(raw, self.chained):
            if code == "TR":
                area_id, level = "TR", "country"
            else:
                area_id, level = province_id(name), "province"
            records.append(
                {
                    "indicator_id": self.indicator_id,
                    "area_id": area_id,
                    "area_level": level,
                    "period_start": dt.date(year, 1, 1),
                    "frequency": "annual",
                    "dims": format_dims({"gdp_sector": sector}),
                    "value": value,
                    "unit": "thousand_try",
                    "quality_flag": "measured",
                    "vintage": self.vintage,
                    "source_id": self.source_id,
                    "retrieved_at": self.retrieved_at,
                }
            )
        frame = pl.DataFrame(records)
        provinces = frame.filter(pl.col("area_level") == "province")[
            "area_id"
        ].n_unique()
        if provinces != 81:
            raise ValueError(f"{self.indicator_id}: 81 il olmali, {provinces} bulundu")
        return frame


class ProvinceGdpCurrent(ProvinceGdp):
    indicator_id = "province_gdp_current"
    filename = CURRENT


class ProvinceGdpChained(ProvinceGdp):
    indicator_id = "province_gdp_chained"
    filename = CHAINED
    chained = True


PROVINCE_GDP_ADAPTERS = {
    "province_gdp_current": ProvinceGdpCurrent,
    "province_gdp_chained": ProvinceGdpChained,
}
