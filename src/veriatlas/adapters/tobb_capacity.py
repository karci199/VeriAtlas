"""TOBB industrial capacity register: producers and capacity by province, product and sector.

Source: TOBB Sanayi Bilgi Sistemi (sanayi.org.tr), the capacity reports of the chambers,
fetched 2026-09-26/27 by `scripts/fetch_tobb_capacity.py` and `scripts/fetch_tobb_tables.py`
into `raw/tobb/kapasite/`. A snapshot of the register, not a yearly series: stored as the
year 2026.

- `urun/<code>.json`: per product code, one row per province and unit of the registered
  producers and their capacity. A province appears twice when its producers report the
  same product in different units (kg and pieces), so the unit is a breakdown. Capacity is
  hidden ("*") exactly where there are three producers or fewer — hidden, not zero, and
  left out. Province 0 is "BİLİNMEYEN" (no province on the certificate), left out.
- `tablo/anaFaaliyetlereGoreUreticiDagilimi/<il>.json`: producers by main activity (NACE
  division). -1 is Türkiye; İstanbul (34) is missing from the source's answer.
- `tablo/ilPersonelAraliklariDagilimByIlId/<il>.json`: producers by sector and staff band.
  The bands add up to less than the total in 170 rows (a producer with no staff figure),
  never to more; the total is kept as its own band.
- `tablo/ilGenelDurumuIlceDuzeyindeDagilim/<il>[-<sector>].json`: producers per district,
  all sectors and each sector. Only producers with a district on record are placed: the
  district total is 70-77% of the province. `MERKEZ` in a metropolitan province and
  `BELİRTİLMEMİŞ` name no district and are left out (counted in `UNPLACED`).

Personnel columns are not read: the staff totals add up to 41.5 million for Türkiye
against about 4 million manufacturing employees (a producer's staff is repeated on every
product and sector line).

Product codes are TOBB's own list: 2,421 of 4,673 are PRODTR codes, the rest TOBB's
extensions, so they are a breakdown of their own (`tobb_product`), not `industrial_product`.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl

from ..config import RAW
from ..labels import district_id

FILES = RAW / "tobb" / "kapasite"
SNAPSHOT = dt.date(2026, 1, 1)
RETRIEVED = dt.date(2026, 9, 27)
VINTAGE = "2026-09"
UNKNOWN_PROVINCE = 0
COUNTRY = -1

#: TOBB unit name (lower-cased) -> `tobb_unit` value.
UNITS = {
    "kilogram": "kilogram",
    "adet": "item",
    "metrekare": "square_metre",
    "litre": "litre",
    "metreküp": "cubic_metre",
    "çift": "pair",
    "kilowatt saat": "kilowatt_hour",
    "metre": "metre",
    "ton": "tonne",
    "joule": "joule",
    "dwt": "deadweight_tonne",
    "kilometre": "kilometre",
    "gram": "gram",
    "karat": "carat",
    "kutu": "box",
}

#: Staff band columns of the personnel table -> `producer_staff_band` value.
STAFF_BANDS = {
    "PERSONEL_1_10": "1-10",
    "PERSONEL_11_20": "11-20",
    "PERSONEL_21_50": "21-50",
    "PERSONEL_51_100": "51-100",
    "PERSONEL_101_250": "101-250",
    "PERSONEL_250_GT": "250+",
}

#: TOBB's spelling -> the register's, by plate. Abbreviations and old names.
DISTRICT_ALIASES = {
    (3, "S.PAŞA(SİN.)"): "Sinanpaşa",
    (6, "Ş.KOÇHİSAR"): "Şereflikoçhisar",
    (4, "DOĞUBEYAZIT"): "Doğubayazıt",
    (16, "M.KEMALPAŞA"): "Mustafakemalpaşa",
    (22, "SÜLEOĞLU"): "Süloğlu",
    (28, "Ş.KARAHİSAR"): "Şebinkarahisar",
    (31, "ANTAKYA(M)"): "Antakya",
    (31, "SAMANDAĞI"): "Samandağ",
    (46, "Ç.CERİT"): "Çağlayancerit",
    (70, "K.KARABEKİR"): "Kazımkarabekir",
    (37, "AĞILI"): "Ağlı",
    (41, "İZMİT(MRK)"): "İzmit",
    (44, "ARAPKİR"): "Arapgir",
    (54, "ADAPAZARI(M)"): "Adapazarı",
    # Aydınlar was renamed Tillo in 2011.
    (56, "AYDINLAR"): "Tillo",
    (59, "M.EREĞLİSİ"): "Marmaraereğlisi",
    (34, "G.OSMANPAŞA"): "Gaziosmanpaşa",
}
#: Names that are no district: left out, and the only names allowed to be.
NO_DISTRICT = {"MERKEZ", "BELİRTİLMEMİŞ"}

#: Producers left out because their district is not a district, by table and sector.
UNPLACED: dict[str, int] = {}


def load(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["content"] if isinstance(data, dict) else data


def area(plate: int) -> tuple[str, str]:
    if plate == COUNTRY:
        return "TR", "country"
    if not 1 <= plate <= 81:
        raise ValueError(f"TOBB: tanınmayan il kimliği {plate}")
    return f"TR-{plate:02d}", "province"


def province_names() -> dict[int, str]:
    """TOBB province id -> name; the id is the plate number, which is checked."""
    out = {}
    for row in json.loads((FILES / "iller.json").read_text(encoding="utf-8")):
        if row["id"] != row["ilNo"]:
            raise ValueError(f"TOBB iller.json: id {row['id']} ≠ plaka {row['ilNo']}")
        out[row["id"]] = row["adi"]
    return out


def products() -> dict[str, dict]:
    """{code: {name, unit}} from TOBB's product code list; a code listed twice fails."""
    out: dict[str, dict] = {}
    for row in json.loads((FILES / "prodcom-kodlari.json").read_text(encoding="utf-8")):
        code = row["kodu"]
        if code in out:
            raise ValueError("TOBB ürün kodu iki kez: " + code)
        out[code] = {
            "name": " ".join(row["adi"].split()),
            "unit": ((row.get("birimKodlari") or {}).get("birimAdi") or "").lower(),
        }
    return out


def unit_id(name: str) -> str:
    key = name.strip().lower()
    if key not in UNITS:
        raise KeyError("TOBB: tanınmayan birim " + repr(name))
    return UNITS[key]


def product_rows() -> list[dict]:
    """One record per (product, province, unit): producers and, where shown, capacity."""
    codes = products()
    out = []
    files = sorted((FILES / "urun").glob("*.json"))
    if len(files) != len(codes):
        raise ValueError(
            f"TOBB: {len(files)} ürün dosyası, kod listesinde {len(codes)}"
        )
    for path in files:
        code = path.stem
        if code not in codes:
            raise KeyError("TOBB: kod listesinde olmayan ürün dosyası " + code)
        seen: set[tuple[int, str]] = set()
        for row in load(path):
            plate, unit = row["IL_ID"], unit_id(row["BIRIM_ADI"])
            if (plate, unit) in seen:
                raise ValueError(f"TOBB {code}: il {plate} birim {unit} iki kez")
            seen.add((plate, unit))
            producers, capacity = row["KAYITLI_URETICI"], row["URETIM_MIKTARI"]
            # The rule the source follows, checked because a break in it would mean a
            # hidden cell read as a number or a number read as hidden.
            if (capacity == "*") != (producers <= 3):
                raise ValueError(
                    f"TOBB {code} il {plate}: {producers} üretici, kapasite {capacity!r}"
                )
            if plate == UNKNOWN_PROVINCE:
                UNPLACED["urun"] = UNPLACED.get("urun", 0) + producers
                continue
            out.append(
                {
                    "code": code,
                    "plate": plate,
                    "unit": unit,
                    "producers": producers,
                    "capacity": None if capacity == "*" else float(capacity),
                }
            )
    return out


def activity_rows() -> list[dict]:
    """Producers by main activity: Türkiye and 80 provinces (İstanbul is not published)."""
    out = []
    for path in sorted(
        (FILES / "tablo" / "anaFaaliyetlereGoreUreticiDagilimi").glob("*.json")
    ):
        plate = int(path.stem)
        if plate == UNKNOWN_PROVINCE:
            continue
        seen = set()
        for row in load(path):
            sector = row["SEKTOR_KODU"]
            if sector in seen:
                raise ValueError(f"TOBB ana faaliyet il {plate}: {sector} iki kez")
            seen.add(sector)
            out.append(
                {"plate": plate, "sector": sector, "value": row["KAYITLI_URETICI"]}
            )
    return out


def staff_rows() -> list[dict]:
    """Producers by sector and staff band, with the sector total as band `total`."""
    out = []
    for path in sorted(
        (FILES / "tablo" / "ilPersonelAraliklariDagilimByIlId").glob("*.json")
    ):
        plate = int(path.stem)
        if plate == UNKNOWN_PROVINCE:
            continue
        seen = set()
        for row in load(path):
            sector = row["KOD"]
            if sector in seen:
                raise ValueError(f"TOBB personel il {plate}: {sector} iki kez")
            seen.add(sector)
            if set(row) - {"KOD", "AD", "SAYI"} != set(STAFF_BANDS):
                raise ValueError(f"TOBB personel il {plate}: sütunlar {sorted(row)}")
            bands = {STAFF_BANDS[k]: row[k] for k in STAFF_BANDS}
            if sum(bands.values()) > row["SAYI"]:
                raise ValueError(
                    f"TOBB personel il {plate} {sector}: aralıklar {sum(bands.values())} "
                    f"> toplam {row['SAYI']}"
                )
            for band, value in {**bands, "total": row["SAYI"]}.items():
                out.append(
                    {"plate": plate, "sector": sector, "band": band, "value": value}
                )
    return out


def district_rows(table: str = "ilGenelDurumuIlceDuzeyindeDagilim") -> list[dict]:
    """Producers per district, sector `total` for all activities."""
    names = province_names()
    out = []
    for path in sorted((FILES / "tablo" / table).glob("*.json")):
        plate_text, _, sector = path.stem.partition("-")
        plate, sector = int(plate_text), sector or "total"
        # district -> (TOBB name, producers). TOBB keeps two ids for Çarşamba (Samsun
        # 5504 and 5516, same name, the province's other 16 districts all present):
        # the same name twice is one district in two records and is summed. Two
        # different names landing on one district would be a wrong alias, and fails.
        placed: dict[str, tuple[str, int]] = {}
        for row in load(path):
            name = row["ADI"]
            wanted = DISTRICT_ALIASES.get((plate, name), name)
            found = district_id(names[plate], wanted)
            if found is None:
                if name not in NO_DISTRICT:
                    raise KeyError(f"TOBB ilçe: tanınmayan ad {names[plate]} / {name}")
                UNPLACED[table] = UNPLACED.get(table, 0) + row["SAYI"]
                continue
            if found in placed:
                if placed[found][0] != name:
                    raise ValueError(
                        f"TOBB ilçe {path.stem}: {placed[found][0]} ve {name} → {found}"
                    )
                placed[found] = (name, placed[found][1] + row["SAYI"])
            else:
                placed[found] = (name, row["SAYI"])
        out += [
            {"area_id": found, "sector": sector, "value": value}
            for found, (_, value) in placed.items()
        ]
    return out


def frame(records: list[dict], indicator: str, unit: str) -> pl.DataFrame:
    return pl.DataFrame(records, schema_overrides={"value": pl.Float64}).with_columns(
        pl.lit(indicator).alias("indicator_id"),
        pl.lit(SNAPSHOT).alias("period_start"),
        pl.lit("annual").alias("frequency"),
        pl.lit(unit).alias("unit"),
        pl.lit("measured").alias("quality_flag"),
        pl.lit(VINTAGE).alias("vintage"),
        pl.lit("tobb").alias("source_id"),
        pl.lit(RETRIEVED).alias("retrieved_at"),
    )


def with_area(plate: int, record: dict) -> dict:
    area_id, level = area(plate)
    return {"area_id": area_id, "area_level": level, **record}


class TobbCapacity:
    source_id = "tobb"
    indicator_id = ""

    def fetch(self) -> Path:
        return FILES


class TobbProductProducers(TobbCapacity):
    indicator_id = "tobb_product_producers"

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            with_area(
                r["plate"],
                {
                    "dims": f"tobb_product={r['code']};tobb_unit={r['unit']}",
                    "value": r["producers"],
                },
            )
            for r in product_rows()
        ]
        return frame(records, self.indicator_id, "company")


class TobbProductCapacity(TobbCapacity):
    indicator_id = "tobb_product_capacity"

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            with_area(
                r["plate"],
                {
                    "dims": f"tobb_product={r['code']};tobb_unit={r['unit']}",
                    "value": r["capacity"],
                },
            )
            for r in product_rows()
            if r["capacity"] is not None
        ]
        return frame(records, self.indicator_id, "source_unit")


class TobbProducersByActivity(TobbCapacity):
    indicator_id = "tobb_producers_by_activity"

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            with_area(
                r["plate"],
                {"dims": f"nace_division={r['sector']}", "value": r["value"]},
            )
            for r in activity_rows()
        ]
        return frame(records, self.indicator_id, "company")


class TobbProducersByStaff(TobbCapacity):
    indicator_id = "tobb_producers_by_staff"

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            with_area(
                r["plate"],
                {
                    "dims": f"nace_division={r['sector']};producer_staff_band={r['band']}",
                    "value": r["value"],
                },
            )
            for r in staff_rows()
        ]
        return frame(records, self.indicator_id, "company")


class TobbProducersDistrict(TobbCapacity):
    indicator_id = "tobb_producers_district"
    table = "ilGenelDurumuIlceDuzeyindeDagilim"

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "area_id": r["area_id"],
                "area_level": "district",
                "dims": f"nace_division={r['sector']}",
                "value": r["value"],
            }
            for r in district_rows(self.table)
        ]
        return frame(records, self.indicator_id, "company")


class TobbForeignProducersDistrict(TobbProducersDistrict):
    indicator_id = "tobb_foreign_producers_district"
    table = "yabanciSermayeIlGenelDurumuIlceDuzeyindeDagilim"


def foreign_product_rows() -> list[dict]:
    """Foreign-capital producers per product: Türkiye (-1) and each province.

    Read from `yabanciSermayeIlceGenelDurumuKodlananUrun`, the foreign-capital twin of
    the table whose counts match the product files. Its sibling
    `yabanciSermayeGenelDurumuKodlananUrun` (product x province in one list) gives
    smaller counts for the same cells (Adana 11.07.11.50.01: 1 against 8) and lists some
    products twice under two spellings of the name; it is not read. Codes missing from
    the code list are left out, their Türkiye producers counted in `UNPLACED`.
    """
    codes = products()
    out = []
    table = FILES / "tablo" / "yabanciSermayeIlceGenelDurumuKodlananUrun"
    for path in sorted(table.glob("*.json")):
        plate = int(path.stem)
        if plate == UNKNOWN_PROVINCE:
            if load(path):
                raise ValueError("TOBB yabancı sermaye: BİLİNMEYEN il dolu")
            continue
        seen = set()
        for row in load(path):
            code = row["URUN_KODU"]
            if code not in codes:
                # Ten codes (23 producers of 6,854 in the Türkiye row) are not on TOBB's
                # current code list, so they have no name: left out, counted.
                if plate == COUNTRY:
                    UNPLACED["old_code"] = UNPLACED.get("old_code", 0) + row["KR_COUNT"]
                continue
            if code in seen:
                raise ValueError(f"TOBB yabancı sermaye il {plate}: {code} iki kez")
            seen.add(code)
            out.append({"plate": plate, "code": code, "value": row["KR_COUNT"]})
    return out


class TobbForeignProductProducers(TobbCapacity):
    indicator_id = "tobb_foreign_product_producers"

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            with_area(
                r["plate"], {"dims": f"tobb_product={r['code']}", "value": r["value"]}
            )
            for r in foreign_product_rows()
        ]
        return frame(records, self.indicator_id, "company")


TOBB_CAPACITY_ADAPTERS = {
    cls.indicator_id: cls
    for cls in (
        TobbProductProducers,
        TobbProductCapacity,
        TobbProducersByActivity,
        TobbProducersByStaff,
        TobbProducersDistrict,
        TobbForeignProductProducers,
        TobbForeignProducersDistrict,
    )
}
