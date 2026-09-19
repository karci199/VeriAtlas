r"""Cargo and containers handled at Türkiye's ports, by province and year.

The Ministry of Transport publishes one workbook per month at
`denizcilikistatistikleri.uab.gov.tr` (`scripts/fetch_uab_denizcilik.py`), broken down by
liman başkanlığı — port authority, which is a place, so it carries to a province. Nothing
else in the store measures sea freight; KGM covers roads and DHMİ the airports.

Three things about the source, each of which quietly produces a wrong number:

* **The monthly files are cumulative, not monthly.** January says 97,3 mn tonnes,
  February 178,0, March 276,3: each is the year to date. Adding the twelve gives 3.575 mn
  tonnes, six and a half times the truth. Only December is read, and a year without a
  twelfth file is left out rather than under-counted.
* **The sheet carries its own grand total row.** `Toplam / Total` sits among the ports and
  doubles the country if it is summed with them.
* **The name is spelled four ways across the years.** 2020 writes the ports in Turkish
  capitals (`İSKENDERUN`, `KARADENİZ EREĞLİSİ`), later years in title case, and a footnote
  line sits in the same column ("Not:", "Düzeltme Tarihi: 08.07.2020"). Names are matched
  on an ASCII-folded skeleton, and rows that are plainly prose are skipped.
* **`Bandıma` is the source's spelling of Bandırma.** It is mapped as written; correcting
  the name in the file is not our business, but dropping the port would lose Balıkesir's
  largest harbour.

Ports are mapped to provinces by hand because a port authority is not a district: Ambarlı
and Tuzla are both İstanbul, Karadeniz Ereğli is Zonguldak, Taşucu is Mersin. An unknown
port name stops the run — the list changes when a new authority is founded, and a silent
drop would take its whole province's tonnage with it.
"""

from __future__ import annotations

import datetime as dt
import glob
import re
from pathlib import Path

import polars as pl
import xlrd

from ..config import RAW
from ..schema import format_dims
from .kgm import province_id

FOLDER = RAW / "uab"
VINTAGE = "2026-09"
RETRIEVED = dt.date(2026, 9, 19)

#: Port authority → province. The ministry's own list, read 2026-09-19.
PORT_PROVINCE = {
    "Alanya": "Antalya",
    "Aliağa": "İzmir",
    "Ambarlı": "İstanbul",
    "Antalya": "Antalya",
    "Ayvalık": "Balıkesir",
    "Bandıma": "Balıkesir",
    "Bandırma": "Balıkesir",
    "Bartın": "Bartın",
    "Ceyhan": "Adana",
    "Çanakkale": "Çanakkale",
    "Çeşme": "İzmir",
    "Dikili": "İzmir",
    "Enez": "Edirne",
    "Erdek": "Balıkesir",
    "Fatsa": "Ordu",
    "Gemlik": "Bursa",
    "Giresun": "Giresun",
    "Göcek": "Muğla",
    "Güllük": "Muğla",
    "Hopa": "Artvin",
    "İnebolu": "Kastamonu",
    "İskenderun": "Hatay",
    "İstanbul": "İstanbul",
    "İzmir": "İzmir",
    "Karabiga": "Çanakkale",
    "Karadeniz Ereğli": "Zonguldak",
    "Karasu": "Sakarya",
    "Kocaeli": "Kocaeli",
    "Marmara Adası": "Balıkesir",
    "Marmaris": "Muğla",
    "Mersin": "Mersin",
    "Mudanya": "Bursa",
    "Rize": "Rize",
    "Samsun": "Samsun",
    "Sürmene": "Trabzon",
    "Taşucu": "Mersin",
    "Tekirdağ": "Tekirdağ",
    "Tirebolu": "Giresun",
    "Trabzon": "Trabzon",
    "Tuzla": "İstanbul",
    "Ünye": "Ordu",
    "Yalova": "Yalova",
    "Zonguldak": "Zonguldak",
    "Sinop": "Sinop",
    "Bodrum": "Muğla",
    "Kuşadası": "Aydın",
    "Botaş": "Adana",
    "Nemrut": "İzmir",
    "Derince": "Kocaeli",
    "Bozcaada": "Çanakkale",
    "Gökçeada": "Çanakkale",
    "Ordu": "Ordu",
    "Amasra": "Bartın",
    "Akçakoca": "Düzce",
    "İzmit": "Kocaeli",
    "Finike": "Antalya",
    "Kaş": "Antalya",
    "Datça": "Muğla",
    "Fethiye": "Muğla",
    "Didim": "Aydın",
    "Silifke": "Mersin",
    "Anamur": "Mersin",
}

#: Two more the source itself writes: `Kefken` (Kocaeli), `Silivri` and `İğneada`. And
#: one oddity kept as published — a single tonne filed under `ANKARA` in May 2020, a
#: landlocked province. It is the source's own row, so it is loaded rather than judged.
PORT_PROVINCE |= {
    "Kefken": "Kocaeli",
    "Silivri": "İstanbul",
    "İğneada": "Kırklareli",
    "Ankara": "Ankara",
    "Karadeniz Ereğlisi": "Zonguldak",
}
BY_SKELETON = {}

#: Column of the December sheet → (direction, trade). The sheet is three blocks of six:
#: loading, unloading, and their total; inside each, foreign trade (split by flag),
#: cabotage, transit and the block's own total.
COLUMNS = {
    3: ("loading", "foreign"),
    4: ("loading", "cabotage"),
    5: ("loading", "transit"),
    6: ("loading", "total"),
    9: ("unloading", "foreign"),
    10: ("unloading", "cabotage"),
    11: ("unloading", "transit"),
    12: ("unloading", "total"),
    15: ("total", "foreign"),
    16: ("total", "cabotage"),
    17: ("total", "transit"),
    18: ("total", "total"),
}
FIRST_ROW = 6
#: Rows that are not a port: the sheet's own total, the ministry's signature, and the
#: footnotes it leaves in the same column as the port names.
NOT_A_PORT = (
    "toplam",
    "total",
    "genel",
    "denizcilik genel",
    "not",
    "duzeltme",
    "a)",
    "b)",
)

ASCII = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def skeleton(name: str) -> str:
    """`KARADENİZ EREĞLİSİ` and `Karadeniz Ereğli` fold to the same key."""
    folded = re.sub(r"[^a-z]", "", name.translate(ASCII).lower())
    return folded.removesuffix("si") if folded.startswith("karadenizeregli") else folded


BY_SKELETON.update(
    {skeleton(port): province for port, province in PORT_PROVINCE.items()}
)


#: The two statistics that come by port authority, and the folder each one sits in.
#: Containers are counted in TEU, cargo in tonnes; same sheet shape, same traps.
SUBJECTS = {
    "port_cargo_handled": ("yuk", "tonne"),
    "port_containers_handled": ("konteyner", "teu"),
}


def december(year: int, subject: str = "yuk") -> Path | None:
    """The year-to-date file for December, or None for a year still running."""
    files = sorted(
        glob.glob(str(FOLDER / f"{subject}-{year}" / "liman-baskanliklari*.xls"))
    )
    return Path(files[-1]) if len(files) == 12 else None


def read_year(path: Path) -> dict[tuple[str, str, str], float]:
    """(province, direction, trade) → tonnes, summed over the year's ports."""
    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    totals: dict[tuple[str, str, str], float] = {}
    for row in range(FIRST_ROW, sheet.nrows):
        name = str(sheet.cell_value(row, 0)).strip()
        lowered = name.lower()
        if not name or name.startswith("*") or lowered.startswith(NOT_A_PORT):
            continue
        key = skeleton(name)
        if key not in BY_SKELETON:
            raise KeyError(f"tanınmayan liman başkanlığı: {name}")
        province = BY_SKELETON[key]
        for column, (direction, trade) in COLUMNS.items():
            value = sheet.cell_value(row, column)
            if not isinstance(value, float):
                continue
            key = (province, direction, trade)
            totals[key] = totals.get(key, 0.0) + value
    return totals


class PortCargo:
    source_id = "uab_denizcilik"
    indicator_id = "port_cargo_handled"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        subject, unit = SUBJECTS[self.indicator_id]
        records = []
        for year in range(2020, dt.datetime.now(tz=dt.UTC).year + 1):
            path = december(year, subject)
            if path is None:
                continue
            for (province, direction, trade), amount in read_year(path).items():
                records.append(
                    {
                        "indicator_id": self.indicator_id,
                        "area_id": province_id(province),
                        "area_level": "province",
                        "period_start": dt.date(year, 1, 1),
                        "frequency": "annual",
                        "dims": format_dims(
                            {"cargo_direction": direction, "trade_type": trade}
                        ),
                        "value": amount,
                        "unit": unit,
                        "quality_flag": "measured",
                        "vintage": VINTAGE,
                        "source_id": self.source_id,
                        "retrieved_at": RETRIEVED,
                    }
                )
        if not records:
            raise ValueError(f"{self.indicator_id}: liman verisi bulunamadi")
        return pl.DataFrame(records)


class PortContainers(PortCargo):
    """Containers, counted in TEU. Same sheet, same ports, a different unit — and never
    added to the tonnes: a container's weight is already inside the cargo table."""

    indicator_id = "port_containers_handled"


UAB_ADAPTERS = {
    "port_cargo_handled": PortCargo,
    "port_containers_handled": PortContainers,
}
