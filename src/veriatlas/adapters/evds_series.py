"""EVDS groups stored at their published frequency: price indices, monthly property sales by
province, monthly construction and occupancy permits, the 26-region house price archive.

Downloaded by `scripts/fetch_evds_housing.py <group>` into `raw/evds/`. Four shapes:

- **price index trees** (CPI 2025 items, PPI, services PPI, ...): Türkiye only, one
  dimension whose values are the EVDS series codes, labelled with the source's own
  numbered names. Aggregates are stored next to their items — an index does not add up.
- **property sales** (`bie_akonutsat1..4`): "Adana_Konut_İpotekli Satışlar". Provinces
  only; each province sum is checked against the source's Türkiye row, month by month.
  Seasonally adjusted copies (Türkiye only) are not stored.
- **permits** (`bie_inyprh2`, `bie_inypkl2`): owner × building use × measure. Only leaves
  are stored — public / cooperative / private × nine uses and "other" — and their sum is
  checked against the published grand total. The value measure (C) is empty at source.
- **house price index 2017=100** (`bie_hkfe`): Türkiye and all 26 İBBS-2 regions.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import polars as pl

from ..areas import load_areas
from ..config import RAW
from ..indicators import get, load
from ..schema import format_dims

DOWNLOADS = RAW / "evds"


def rows_of(payload: dict):
    """(series, period date, value) for every filled cell, periods monthly or quarterly."""
    for series in payload["series"]:
        column = series["SERIE_CODE"].replace(".", "_")
        for item in payload["items"]:
            cell = item.get(column)
            if cell in (None, ""):
                continue
            label = str(item["Tarih"])
            if label.count("-") == 2:
                day, month, year = label.split("-")
                date = dt.date(int(year), int(month), int(day))
            elif "-Q" in label:
                year, quarter = label.split("-Q")
                date = dt.date(int(year), 3 * int(quarter) - 2, 1)
            elif "-" in label:
                year, month = label.split("-")
                date = dt.date(int(year), int(month), 1)
            else:
                date = dt.date(int(label), 1, 1)
            yield series, date, float(cell)


def item_value(code: str) -> str:
    """Dimension value id from an EVDS series code: its last segments, lower-case."""
    return re.sub(r"[^a-z0-9]+", "_", code.split(".", 1)[1].lower()).strip("_")


# region Price index trees

#: indicator id → (group, dimension)
INDEX_TREES = {
    "cpi_2025_items": ("bie_tukfiy2025", "cpi_2025_item"),
    "cpi_2025_special": ("bie_oktug2025", "cpi_2025_special_item"),
    "ppi_domestic": ("bie_tufe1yi", "ppi_domestic_item"),
    "ppi_export": ("bie_ufeyd", "ppi_export_item"),
    "services_ppi": ("bie_hufe", "services_ppi_item"),
    "agricultural_ppi": ("bie_tarimufe", "agricultural_ppi_item"),
    "agricultural_input_pi": ("bie_tarimgfe", "agricultural_input_item"),
    "istanbul_cpi_ito": ("bie_itouge2023", "istanbul_cpi_item"),
    # Not a price index, but the same shape: one Türkiye series per vehicle type (OSD).
    "vehicle_production": ("bie_uroto", "vehicle_type_produced"),
    # Real sector, credit and rates. A third element keeps only the series whose code
    # matches it: where one group mixes units (company counts and capital in lira; survey
    # shares and the count of firms answering), each unit becomes its own indicator.
    "companies_opened_closed": ("bie_ackap2", "company_count_item", r"\.A$"),
    "companies_opened_capital": ("bie_ackap2", "company_capital_item", r"\.S$"),
    "industrial_production_index": ("bie_tsanay2021", "industry_item"),
    "capacity_utilisation": ("bie_kko2", "capacity_item"),
    "real_sector_confidence": ("bie_rkgey2", "real_sector_confidence_item"),
    "economic_tendency_survey": ("bie_iyaw2", "tendency_item", r"\.[A-F]$"),
    "bank_credit_volume": ("bie_krehacbs", "credit_volume_item"),
    "loan_interest_rates": ("bie_kt210a", "loan_rate_item"),
    "loan_profit_share_rates": ("bie_kt210aks", "profit_share_rate_item"),
    "deposit_interest_rates": ("bie_mt210ags", "deposit_rate_item"),
    "loan_interest_rates_weekly": ("bie_kt100h", "loan_rate_weekly_item"),
    "real_effective_exchange_rate_cpi": ("bie_rktufey", "reer_cpi_item"),
    "real_effective_exchange_rate_ppi": ("bie_rkufey", "reer_ppi_item"),
    "trade_trucks": ("bie_undnakliyeroro", "trade_truck_item"),
    "credit_participation_banks": ("bie_kbkmkre", "credit_participation_item"),
    "card_payment_index": ("bie_kartmetre", "card_payment_index_item"),
    # GDP. Current and chained-volume levels are thousand TRY (volume at 2009 prices);
    # the index groups are 2009=100. Aggregates sit next to their components.
    "gdp_expenditure_current": ("bie_gsyhhrccar", "gdp_expenditure_item"),
    "gdp_expenditure_current_sa": ("bie_gsyhcrarnd", "gdp_expenditure_sa_item"),
    "gdp_expenditure_chained": ("bie_gsyhhrczinc", "gdp_expenditure_chained_item"),
    "gdp_expenditure_index": ("bie_gsyhendex", "gdp_expenditure_index_item"),
    "gdp_expenditure_index_sca": ("bie_gsyzhend", "gdp_expenditure_index_sca_item"),
    "gdp_expenditure_index_sa": ("bie_gsyhmevset", "gdp_expenditure_index_sa_item"),
    "gdp_expenditure_index_ca": ("bie_gsyzhtaken", "gdp_expenditure_index_ca_item"),
    "gfcf_current": ("bie_gayrfsermol", "gfcf_item"),
    "gfcf_index": ("bie_gaysafserzinc", "gfcf_index_item"),
    "household_consumption_durability": (
        "bie_nihaitukh",
        "consumption_durability_item",
    ),
    "household_consumption_purpose": ("bie_gsyhnihayilcr", "consumption_purpose_item"),
    "household_consumption_purpose_index": (
        "bie_gsyhnihayil",
        "consumption_purpose_index_item",
    ),
    "gdp_income_current": ("bie_gsyhgelrcar", "gdp_income_item"),
    "gdp_income_current_sa": ("bie_gelirmea", "gdp_income_sa_item"),
    "gdp_production_current": ("bie_gsyhuretcar", "gdp_production_item"),
    "gdp_production_current_sa": ("bie_uretmeacari", "gdp_production_sa_item"),
    "gdp_production_chained": ("bie_gsyhuretzinc", "gdp_production_chained_item"),
    "gdp_production_index_sca": ("bie_uretmtazincr", "gdp_production_index_sca_item"),
    "gdp_production_annual_current": ("bie_uretcryil", "gdp_production_annual_item"),
    "gdp_production_annual_chained": (
        "bie_uretzincyil",
        "gdp_production_annual_chained_item",
    ),
    "gdp_per_capita_try": ("bie_uretmkb", "gdp_per_capita_try_item", r"\.TL$"),
    "gdp_per_capita_usd": ("bie_uretmkb", "gdp_per_capita_usd_item", r"\.USD$"),
    "gnp_1987_current_archive": ("bie_urgsmhc", "gnp_1987_current_item"),
    "gnp_1987_constant_archive": ("bie_urgsmhq", "gnp_1987_constant_item"),
    "gdp_1998_expenditure_current_archive": (
        "bie_gsyihhy",
        "gdp_1998_exp_current_item",
        r"\.C$",
    ),
    "gdp_1998_expenditure_constant_archive": (
        "bie_gsyihhy",
        "gdp_1998_exp_constant_item",
        r"\.S$",
    ),
    "gdp_1998_production_current_archive": (
        "bie_gsyihtf",
        "gdp_1998_prod_current_item",
        r"\.C$",
    ),
    "gdp_1998_production_constant_archive": (
        "bie_gsyihtf",
        "gdp_1998_prod_constant_item",
        r"\.S$",
    ),
    "card_spending_weekly": ("bie_kkhartut", "card_sector_amount_item"),
    "card_transactions_weekly": ("bie_kkislade", "card_sector_count_item"),
    "cheques_count": ("bie_btocek", "cheque_count_item", r"TP\.BTO[135]$"),
    "cheques_amount": ("bie_btocek", "cheque_amount_item", r"TP\.BTO[246]$"),
    "bills_collected_count": ("bie_tsenetler", "bill_count_item", r"ADET$"),
    "bills_collected_amount": ("bie_tsenetler", "bill_amount_item", r"TUTAR$"),
    "credit_development_banks": ("bie_kmkykre", "credit_development_item"),
    "credit_deposit_banks": ("bie_kmmbkre", "credit_deposit_bank_item"),
    "bank_credit_volume_weekly": ("bie_hpbitablo6", "credit_weekly_item"),
    "tendency_survey_small_firms": ("bie_iyabgs2s", "tendency_small_item", r"\.[A-F]$"),
    "tendency_survey_medium_firms": (
        "bie_iyabgs3s",
        "tendency_medium_item",
        r"\.[A-F]$",
    ),
    "tendency_survey_large_firms": ("bie_iyabgs4s", "tendency_large_item", r"\.[A-F]$"),
}


def index_tree(indicator_id: str) -> list[dict]:
    group, dim, *keep = INDEX_TREES[indicator_id]
    payload = json.loads((DOWNLOADS / f"{group}.json").read_text(encoding="utf-8"))
    declared = load().dimensions[dim].values_tr
    seen: set[str] = set()
    records = []
    for series, date, value in rows_of(payload):
        if keep and not re.search(keep[0], series["SERIE_CODE"]):
            continue
        key = item_value(series["SERIE_CODE"])
        if key not in declared:
            raise KeyError(
                f"{indicator_id}: sozlukte olmayan kalem {series['SERIE_CODE']}"
            )
        seen.add(key)
        records.append(
            {
                "area_id": "TR",
                "area_level": "country",
                "period_start": date,
                "dims": format_dims({dim: key}),
                "value": value,
            }
        )
    return records


# endregion

# region Property sales by province

SALES_GROUPS = {
    "bie_akonutsat1": "total",
    "bie_akonutsat2": "mortgaged",
    "bie_akonutsat3": "first_hand",
    "bie_akonutsat4": "second_hand",
}
PROPERTY = {"Konut": "dwelling", "İş Yeri": "workplace"}


def property_sales() -> list[dict]:
    provinces = {
        row["name_tr"]: row["area_id"]
        for row in load_areas().filter(pl.col("area_level") == "province").to_dicts()
    }
    records = []
    for group, sale in SALES_GROUPS.items():
        payload = json.loads((DOWNLOADS / f"{group}.json").read_text(encoding="utf-8"))
        country: dict[tuple, float] = {}
        summed: dict[tuple, float] = {}
        for series, date, value in rows_of(payload):
            name = series["SERIE_NAME"]
            if "Mevsim" in name:
                continue
            place, kind, _ = name.split("_")
            key = (PROPERTY[kind], date)
            if place == "Türkiye":
                country[key] = value
                continue
            if place not in provinces:
                raise KeyError("il eslesmedi: " + name)
            summed[key] = summed.get(key, 0.0) + value
            records.append(
                {
                    "area_id": provinces[place],
                    "area_level": "province",
                    "period_start": date,
                    "dims": format_dims({"property_type": key[0], "sale_type": sale}),
                    "value": value,
                }
            )
        off = [k for k, v in country.items() if abs(summed.get(k, 0.0) - v) > 1]
        if off:
            raise ValueError(
                f"{group}: il toplami Turkiye'yi tutmuyor, ornek {off[:3]}"
            )
    return records


# endregion

# region Permits

PERMIT_GROUPS = {"bie_inyprh2": "construction", "bie_inypkl2": "occupancy"}
OWNERS = {"DEV": "public", "KOP": "cooperative", "OZE": "private"}
USES = {
    "EV": "residential_single",
    "APT": "residential_multi",
    "HALK": "residential_communal",
    "OTEL": "hotel",
    "OFIS": "office",
    "TOPTAN": "retail",
    "TRAFIK": "transport_communication",
    "SANAYI": "industrial_storage",
    "KAMU": "public_education_health",
    "DIGER": "other_non_residential",
}
#: measure letter → indicator suffix
MEASURES = {"A": "buildings", "B": "floor_area", "D": "dwellings"}


def permits(indicator_id: str) -> list[dict]:
    kind, _, measure = indicator_id.removesuffix("_monthly").partition("_permit_")
    group = next(g for g, k in PERMIT_GROUPS.items() if k == kind)
    letter = next(k for k, v in MEASURES.items() if v == measure)
    payload = json.loads((DOWNLOADS / f"{group}.json").read_text(encoding="utf-8"))
    totals: dict[dt.date, float] = {}
    summed: dict[dt.date, float] = {}
    records = []
    for series, date, value in rows_of(payload):
        parts = series["SERIE_CODE"].split(".")
        use, owner, code = parts[3], parts[4], parts[5]
        if code != letter:
            continue
        if use == "TOPLAM" and owner == "TOP":
            totals[date] = value
        if use not in USES or owner not in OWNERS:
            continue
        summed[date] = summed.get(date, 0.0) + value
        records.append(
            {
                "area_id": "TR",
                "area_level": "country",
                "period_start": date,
                "dims": format_dims(
                    {"building_use": USES[use], "permit_owner": OWNERS[owner]}
                ),
                "value": value,
            }
        )
    off = [
        d for d, v in totals.items() if abs(summed.get(d, 0.0) - v) > max(2, v * 1e-4)
    ]
    if off:
        raise ValueError(f"{indicator_id}: kalemler toplami tutmuyor, ornek {off[:3]}")
    return records


# endregion

# region House price index 2017=100, 26 regions

REGION = re.compile(r"^TR ?([0-9A-C]\d) \(")


def house_price_regions() -> list[dict]:
    payload = json.loads((DOWNLOADS / "bie_hkfe.json").read_text(encoding="utf-8"))
    records = []
    for series, date, value in rows_of(payload):
        found = REGION.match(series["SERIE_NAME"])
        if found:
            area, level = "TR" + found.group(1), "nuts2"
        elif series["SERIE_NAME"].startswith("Konut Fiyat Endeksi"):
            area, level = "TR", "country"
        else:
            raise KeyError("taninmayan seri: " + series["SERIE_NAME"])
        records.append(
            {
                "area_id": area,
                "area_level": level,
                "period_start": date,
                "dims": "",
                "value": value,
            }
        )
    if len({r["area_id"] for r in records}) != 27:
        raise ValueError("26 bolge + Turkiye beklenirdi")
    return records


# endregion

# region Province GDP 1987-2001 (archive)

PRICE_BASIS = {"CAR": "current", "SAB": "constant_1987"}
#: Known source label errors, code is authoritative (see province_gdp_archive).
MISLABELLED = {"TP.UR.ERZINCAN.CAR", "TP.UR.ERZINCAN.SAB"}
OLD_GEO_REGIONS = {
    "AKDENIZ",
    "DANADOLU",
    "EGE",
    "GANADOLU",
    "IANADOLU",
    "KARADENIZ",
    "MARMARA",
}
ASCII_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def skeleton(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.translate(ASCII_TR).lower())


def province_gdp_archive() -> list[dict]:
    """`bie_urgsyih`: "(Cari) ADANA (Arşiv)", lira (new TRY), 79-81 provinces as they
    existed each year. The seven geographic regions of the old table are not ours."""
    payload = json.loads((DOWNLOADS / "bie_urgsyih.json").read_text(encoding="utf-8"))
    ids = {
        skeleton(row["name_tr"]): row["area_id"]
        for row in load_areas().filter(pl.col("area_level") == "province").to_dicts()
    }
    aliases = {"afyon": "afyonkarahisar", "icel": "mersin", "kmaras": "kahramanmaras"}
    records = []
    for series, date, value in rows_of(payload):
        _, _, place, basis = series["SERIE_CODE"].split(".")
        if place in OLD_GEO_REGIONS:
            continue
        # Matched by the code, checked against the name. The names are not reliable:
        # TP.UR.ERZINCAN.* is labelled "DENİZLİ" at source, and its values are
        # Erzincan's (2001: 445 m TRY, the same as the correctly named 2001 table).
        key = aliases.get(place.lower(), place.lower())
        name = skeleton(re.sub(r"\(.*?\)", "", series["SERIE_NAME"]))
        if key not in ids:
            raise KeyError("il eslesmedi: " + series["SERIE_CODE"])
        if aliases.get(name, name) != key and series["SERIE_CODE"] not in MISLABELLED:
            raise KeyError(
                "kod ve ad farkli il: "
                + series["SERIE_CODE"]
                + " "
                + series["SERIE_NAME"]
            )
        records.append(
            {
                "area_id": ids[key],
                "area_level": "province",
                "period_start": date,
                "dims": format_dims({"price_basis": PRICE_BASIS[basis]}),
                "value": value,
            }
        )
    return records


# endregion

BUILDERS = {
    "gdp_province_1987_archive": province_gdp_archive,
    **{ident: (lambda i=ident: index_tree(i)) for ident in INDEX_TREES},
    "property_sales_monthly": property_sales,
    **{
        f"{kind}_permit_{measure}_monthly": (
            lambda i=f"{kind}_permit_{measure}_monthly": permits(i)
        )
        for kind in PERMIT_GROUPS.values()
        for measure in MEASURES.values()
    },
    "house_price_index_2017": house_price_regions,
}


class EvdsSeries:
    source_id = "cbrt_evds"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 14)
    indicator_id = ""

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        frame = pl.DataFrame(BUILDERS[self.indicator_id]())
        if frame.select("area_id", "period_start", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni anahtar iki kez")
        indicator = get(self.indicator_id)
        return frame.with_columns(
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


EVDS_SERIES_ADAPTERS = {
    "evds_" + ident: type(
        "Evds" + "".join(p.title() for p in ident.split("_")),
        (EvdsSeries,),
        {"indicator_id": ident},
    )
    for ident in BUILDERS
}
