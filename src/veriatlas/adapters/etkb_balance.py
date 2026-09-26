r"""National energy balance of Türkiye, 1972 onwards (Ministry of Energy, EİGM).

`enerji.gov.tr/eigm-raporlari` publishes one workbook per year ("Ulusal Enerji Denge
Tabloları"), kept in `C:\veri-ham\etkb\denge\<year>[_R1].xls[x]`. Rows are flows (production,
imports, transformation, final consumption by sector), columns are energy products. The
thousand-toe (bin TEP) table is read: a sheet of its own from 1990 ("BİN TEP", "Bin Ton
Eşdeğer Petrol"), the lower half of the single sheet before ("Bin Ton Petrol Eşdeğeri").

The layout changes three times (1972-1989, 1990-2014, 2015-2020, 2021-), so rows and
columns are matched by their printed labels, not their positions:

- Columns fold into ten product groups (`PRODUCTS`). Subtotal columns — derived gases,
  petroleum products, bioenergy and waste, total solid fuels — are dropped when their
  parts are printed beside them, so nothing is counted twice.
- Rows fold into the flows listed in `FLOWS`; industry sub-branches other than iron and
  steel and cement are not kept (their breakdown changes with the layout). From 2015 the
  table splits households from commerce and services; `residential_services` is their sum
  there, so the series runs through.

Check: in every row read, the product groups add up to the printed total column
(0.5 %, at least 1 ktoe) — a missed subtotal column or a shifted header fails here.
Values are as printed: exports, bunkers and transformation inputs keep the table's sign.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW

FOLDER = (
    RAW / "etkb" / "denge"
    if (RAW / "etkb" / "denge").exists()
    else Path("C:/veri-ham/etkb/denge")
)
#: product group -> pattern on the lower-cased column label (first match wins)
PRODUCTS = (
    ("total", r"^toplam$"),
    ("electricity", r"^elektrik$"),
    ("heat", r"^(diğer )?ısı$"),
    ("geothermal", r"^jeo"),
    ("hydro", r"^hidrolik"),
    ("wind", r"^rüzgar"),
    ("solar", r"^güneş"),
    ("natural_gas", r"^(d\.gaz|doğal ?gaz)"),
    ("bioenergy_waste", r"odun|bit\.? ?art|^hay\.|bi[oy]o?yakıt|^atıklar|^biyoenerji"),
    (
        "oil",
        (
            r"^petro|^ham petrol|^p\. ?kok|^lpg|^benzin|^nafta|^motorin|^fuel|^gaz yağı|havacılık"
            r"|^deniz|rafineri gazı|^bitümen|^ara ürün|baz yağ|beyaz ispirto|^diğer$"
        ),
    ),
    (
        "coal",
        (
            r"^t\.? ?köm|^taş kömür|^linyit|^asfaltit|^kok|^türetilmiş|yüksek fırın|çelikhane"
            r"|kömür katranı|^ikincil kömür|^briket|^top\. ?katı|^(şehir|hava) ?gazı?$"
        ),
    ),
)
#: subtotal column -> patterns of its parts; dropped when any part is in the same table
SUBTOTALS = {
    r"^türetilmiş": (r"yüksek fırın", r"kok fırın", r"çelikhane"),
    r"^petrol ürünleri": (r"^motorin", r"^benzin", r"^fuel"),
    r"^biyoenerji": (r"odun", r"bit\.? ?art", r"bi[oy]o?yakıt"),
    r"^top\. ?katı|^k\.yak": (r"linyit",),
}
#: flow -> pattern on the lower-cased row label (first match wins, first row wins)
FLOWS = (
    ("production", r"^yerli üretim"),
    ("imports", r"^ithalat"),
    ("exports", r"^ihracat"),
    ("bunkers", r"^ihrakiye"),
    ("stock_change", r"^stok değişimi"),
    ("statistical_difference", r"istatisti"),
    (
        "primary_supply",
        r"^birincil enerji arzı|^(toplam )?enerji ürünleri arzı",
    ),
    ("transformation", r"^çevrim ve enerji"),
    ("power_plants", r"^elektrik santralları|^elektrik ve ısı üretimi"),
    ("refineries", r"^petrol rafinerileri"),
    ("own_use_losses", r"^iç tüketim ve kayıp"),
    ("final_consumption", r"nihai enerji tüketimi"),
    ("sectors_total", r"^sektörler toplamı"),
    ("industry", r"^sanayi tüketimi"),
    ("iron_steel", r"^demir ?-?çelik"),
    ("cement", r"^çimento"),
    ("transport", r"^ulaştırma"),
    ("rail", r"^demiryolları"),
    ("sea", r"^denizyolları"),
    ("air", r"^havayolları"),
    ("road", r"^karayolları"),
    ("pipeline", r"^boru hatları"),
    ("other_sectors", r"^diğer +sektörler"),
    ("residential_services", r"^konut ve hizmetler"),
    ("residential", r"^konut$"),
    ("commercial_services", r"^ticaret ve hizmetler"),
    ("agriculture", r"^tarım"),
    ("non_energy", r"^enerji dışı"),
)


def clean(label: str) -> str:
    """Lower-case label without footnote digits and repeated spaces."""
    text = re.sub(r"\s+", " ", str(label)).strip()
    text = re.sub(r"(?<=[a-zçğıöşü])\d+$", "", text)  # "Doğalgaz3" -> "doğalgaz"
    return text.replace("I", "ı").replace("İ", "i").lower()


def number(cell) -> float | None:
    if cell is None or isinstance(cell, bool):
        return None
    if isinstance(cell, (int, float)):
        return float(cell)
    text = str(cell).strip().replace(",", ".")
    return float(text) if re.fullmatch(r"-?\d+(\.\d+)?(e-?\d+)?", text) else None


def toe_rows(path: Path) -> list[list]:
    """The thousand-toe table of one workbook, header row first."""
    import fastexcel

    book = fastexcel.read_excel(path)
    names = book.sheet_names
    toe = [n for n in names if re.search(r"TEP|Petrol", n, re.IGNORECASE)]
    sheet = toe[0] if toe else names[0]
    rows = [
        list(r)
        for r in book.load_sheet_by_name(sheet, header_row=None).to_polars().rows()
    ]
    if not toe:  # 1972-1989: original units on top, thousand toe below
        marks = [
            i
            for i, r in enumerate(rows)
            if any(re.search(r"Petrol E[şs]", str(c or "")) for c in r)
        ]
        if not marks:
            raise ValueError(f"{path.name}: bin TEP bloğu yok")
        rows = rows[marks[-1] :]
    heads = [
        i for i, r in enumerate(rows) if any(clean(c or "") == "linyit" for c in r)
    ]
    if not heads:
        raise ValueError(f"{path.name}: yakıt başlığı yok")
    return rows[heads[0] :]


def product_columns(header: list) -> dict[int, str]:
    labels = {i: clean(c) for i, c in enumerate(header) if i and c and clean(c)}
    drop = {
        i
        for i, label in labels.items()
        for sub, parts in SUBTOTALS.items()
        if re.search(sub, label)
        and any(re.search(p, other) for p in parts for other in labels.values())
    }
    columns: dict[int, str] = {}
    for i, label in labels.items():
        if i in drop:
            continue
        group = next((g for g, pattern in PRODUCTS if re.search(pattern, label)), None)
        if group is None:
            raise ValueError(f"tanınmayan yakıt sütunu: {header[i]!r}")
        columns[i] = group
    if "total" not in columns.values():
        raise ValueError("TOPLAM sütunu yok")
    return columns


def read_year(path: Path) -> dict[tuple[str, str], float]:
    rows = toe_rows(path)
    columns = product_columns(rows[0])
    out: dict[tuple[str, str], float] = {}
    for row in rows[1:]:
        label = clean(row[0] or "")
        flow = next((f for f, pattern in FLOWS if re.search(pattern, label)), None)
        if flow is None or any(k[0] == flow for k in out):
            continue
        sums: dict[str, float] = {}
        for i, group in columns.items():
            value = number(row[i]) if i < len(row) else None
            if value is not None:
                sums[group] = sums.get(group, 0.0) + value
        if not sums:
            continue
        total = sums.get("total")
        parts = sum(v for g, v in sums.items() if g != "total")
        if total is not None and abs(parts - total) > max(1.0, abs(total) * 0.005):
            raise ValueError(
                f"{path.name} {flow}: yakıtlar {parts:,.1f}, TOPLAM {total:,.1f}"
            )
        for group, value in sums.items():
            out[(flow, group)] = value
    if ("final_consumption", "total") not in out:
        raise ValueError(f"{path.name}: nihai tüketim satırı okunamadı")
    if ("residential", "total") in out:
        for group in {g for f, g in out if f in ("residential", "commercial_services")}:
            out[("residential_services", group)] = out.get(
                ("residential", group), 0.0
            ) + out.get(("commercial_services", group), 0.0)
    return out


_CACHE: dict[int, dict[tuple[str, str], float]] = {}


def read_all() -> dict[int, dict[tuple[str, str], float]]:
    if not _CACHE:
        paths = sorted(FOLDER.glob("*.xls*"))
        if len(paths) < 50:
            raise FileNotFoundError(f"{FOLDER}: {len(paths)} dosya")
        for path in paths:
            year = int(path.stem[:4])
            if year in _CACHE:
                raise ValueError(f"{year}: iki dosya")
            _CACHE[year] = read_year(path)
    return _CACHE


class EnergyBalance:
    source_id = "etkb"
    indicator_id = "energy_balance"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "period_start": dt.date(year, 1, 1),
                "dims": f"energy_flow={flow};energy_product={product}",
                "value": value,
            }
            for year, cells in read_all().items()
            for (flow, product), value in cells.items()
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("thousand_toe").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 27)).alias("retrieved_at"),
        )


ETKB_BALANCE_ADAPTERS = {"energy_balance": EnergyBalance}
