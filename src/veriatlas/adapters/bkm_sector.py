r"""Card spending by merchant sector, monthly since 2017 — what BKM adds that TBB cannot.

The card numbers already in the store are geographic: TBB counts POS terminals, ATMs and
card-accepting merchants per province, and EVDS carries BKM's national index and its
weekly spending series. None of them says *what the money was spent on*. BKM's two
sectoral tables do, for 26 merchant groups, and `scripts/fetch_bkm.py` reads them.

BKM publishes nothing by province, so every row here sits at country level. That is the
honest place for it: a national total filed under a province would be an invention.

Four indicators, from two tables that do **not** share a shape:

* the domestic tables split by card — credit and debit;
* the e-commerce tables split by **where the card and the merchant are**, and they do it
  in two overlapping blocks. Only the three disjoint slices are kept — a domestic card
  used abroad, a domestic card used at a domestic merchant, a foreign card used at a
  domestic merchant. The two `Toplam` columns are sums of different things (one totals
  the first block, the other the second) and neither is written out: a stored total that
  is not the sum of its own rows is a trap for whoever joins them later.

**`TOPLAM` is not a sector.** The published table carries a total row beside the 26
groups. It is used here as a check — the sectors must add up to it — and then dropped, so
nothing downstream can sum the sectors and meet the total twice.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import polars as pl

from ..config import RAW
from ..schema import format_dims

FOLDER = RAW / "bkm"
SOURCE_ID = "bkm"
VINTAGE = "2026-09"
RETRIEVED = dt.date(2026, 9, 20)
#: The published total row, kept out of the sector dimension.
TOTAL_ROW = "TOPLAM"
#: How far the sectors may stray from the published total before the parse gives up.
#: They agree exactly in every month read so far; the tolerance is for rounding in the
#: million-lira figures, not for a missing sector.
TOTAL_TOLERANCE = 0.005

#: BKM's merchant group -> the id the warehouse uses. Written out one by one rather than
#: slugified: the source spells four of them without Turkish letters (`BIREYSEL
#: EMEKLILIK`, `KAMU/VERGI ODEMELERI`), and a slug function would file those as different
#: sectors from their accented neighbours the first time BKM fixes the spelling.
SECTORS = {
    "ARABA KİRALAMA": "car_rental",
    "ARAÇ KİRALAMA-SATIŞ/SERVİS/YEDEK PARÇA": "vehicle_trade_and_service",
    "BENZİN VE YAKIT İSTASYONLARI": "fuel_stations",
    "BIREYSEL EMEKLILIK": "private_pension",
    "DOĞRUDAN PAZARLAMA": "direct_marketing",
    "DİĞER": "other",
    "ELEKTRİK-ELEKTRONİK EŞYA, BİLGİSAYAR": "electronics_and_computers",
    "EĞİTİM / KIRTASİYE / OFİS MALZEMELERİ": "education_and_stationery",
    "GİYİM VE AKSESUAR": "clothing_and_accessories",
    "HAVAYOLLARI": "airlines",
    "HİZMET SEKTÖRLERİ": "services",
    "KAMU/VERGI ODEMELERI": "public_and_tax_payments",
    "KONAKLAMA": "accommodation",
    "KULÜP / DERNEK /SOSYAL HİZMETLER": "clubs_and_associations",
    "KUMARHANE/İÇKİLİ YERLER": "gambling_and_licensed_premises",
    "KUYUMCULAR": "jewellers",
    "MARKET VE ALIŞVERİŞ MERKEZLERİ": "markets_and_malls",
    "MOBİLYA VE DEKORASYON": "furniture_and_decoration",
    "MÜTEAHHİT İŞLERİ": "contracting",
    "SAĞLIK/SAĞLIK ÜRÜNLERİ/KOZMETİK": "health_and_cosmetics",
    "SEYAHAT ACENTELERİ/TAŞIMACILIK": "travel_and_transport",
    "SİGORTA": "insurance",
    "TELEKOMÜNİKASYON": "telecommunications",
    "YAPI MALZEMELERİ, HIRDAVAT, NALBURİYE": "building_materials_and_hardware",
    "YEMEK": "food_service",
    "ÇEŞİTLİ GIDA": "food_retail",
}

#: indicator -> (file, unit, {column: dimension value}). The e-commerce columns named
#: `*_toplam` are deliberately absent; see the module docstring.
MEASURES = {
    "card_transactions_by_sector": (
        "sektorel",
        "item",
        "card_type",
        {"adet_kredi": "credit", "adet_banka": "debit"},
    ),
    "card_spending_by_sector": (
        "sektorel",
        "try",
        "card_type",
        {"tutar_kredi": "credit", "tutar_banka": "debit"},
    ),
    "ecommerce_transactions_by_sector": (
        "sektorel_internet",
        "item",
        "card_usage",
        {
            "adet_yerli_yurtdisi": "domestic_card_abroad",
            "adet_yurtici_yerli_kart": "domestic_card_at_home",
            "adet_yurtici_yabanci_kart": "foreign_card_at_home",
        },
    ),
    "ecommerce_spending_by_sector": (
        "sektorel_internet",
        "try",
        "card_usage",
        {
            "tutar_yerli_yurtdisi": "domestic_card_abroad",
            "tutar_yurtici_yerli_kart": "domestic_card_at_home",
            "tutar_yurtici_yabanci_kart": "foreign_card_at_home",
        },
    ),
}


def dump(table: str) -> Path:
    # `sektorel_*.csv` also matches `sektorel_internet_*.csv`, and the internet file sorts
    # last — so the plain glob handed the domestic adapters the e-commerce dump and they
    # failed on a missing column. The date is what follows the name, so the pattern says
    # so: a digit, not anything.
    found = sorted(FOLDER.glob(f"{table}_2*.csv"))
    if not found:
        raise FileNotFoundError(f"BKM dökümü yok: {FOLDER / (table + '_2*.csv')}")
    return found[-1]


def month_start(label: str) -> dt.date:
    year, month = label.split("-")
    return dt.date(int(year), int(month), 1)


class BkmSector:
    source_id = SOURCE_ID
    indicator_id = ""

    def fetch(self) -> Path:
        return dump(MEASURES[self.indicator_id][0])

    def parse(self, raw: Path) -> pl.DataFrame:
        _, unit, dimension, columns = MEASURES[self.indicator_id]
        records: list[dict] = []
        # period -> column -> (sum of sectors, published total), so the check below is
        # made per month and per column rather than once over everything, where a sector
        # missing in one month could hide inside another month's slack.
        tally: dict[tuple[str, str], list[float]] = {}
        unknown: set[str] = set()

        with raw.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                group = row["isyeri_grubu"].strip()
                is_total = group == TOTAL_ROW
                sector = SECTORS.get(group)
                if sector is None and not is_total:
                    unknown.add(group)
                    continue
                for column, slice_id in columns.items():
                    text = row[column]
                    if text == "":
                        continue
                    value = float(text)
                    totals = tally.setdefault((row["donem"], column), [0.0, 0.0])
                    if is_total:
                        totals[1] = value
                        continue
                    totals[0] += value
                    records.append(
                        {
                            "indicator_id": self.indicator_id,
                            "area_id": "TR",
                            "area_level": "country",
                            "period_start": month_start(row["donem"]),
                            "frequency": "monthly",
                            "dims": format_dims(
                                {"merchant_sector": sector, dimension: slice_id}
                            ),
                            "value": value,
                            "unit": unit,
                            "quality_flag": "measured",
                            "vintage": VINTAGE,
                            "source_id": self.source_id,
                            "retrieved_at": RETRIEVED,
                        }
                    )

        if unknown:
            # A new merchant group must be named before it can be stored: dropping it
            # would shrink every total silently, and guessing an id would split one trade
            # across two of them.
            raise KeyError(
                f"{self.indicator_id}: tanınmayan işyeri grubu: {', '.join(sorted(unknown))}"
            )
        for (period, column), (summed, published) in tally.items():
            if published and abs(summed - published) / published > TOTAL_TOLERANCE:
                raise ValueError(
                    f"{self.indicator_id} {period} {column}: sektörler {summed:,.0f}, "
                    f"yayımlanan toplam {published:,.0f}"
                )
        if not records:
            raise ValueError(f"{self.indicator_id}: satır yok ({raw})")
        return pl.DataFrame(records)


BKM_ADAPTERS = {
    name: type(
        f"Bkm{name.title().replace('_', '')}", (BkmSector,), {"indicator_id": name}
    )
    for name in MEASURES
}
