r"""TİM (Türkiye İhracatçılar Meclisi) exports by province and destination country, 2013-2025.

`scripts/fetch_tim.py` keeps the monthly "İller Bazında Ülke" workbooks in
`C:\veri-ham\tim\<year>\<month>`. Years, columns and gaps are those of the sector files
(`tim_sectors`): the December year-to-date column; 2017 and 2018 are January-November plus
December's month from the next January file.

Layouts: 2013-2014 rows are country × province, each province opening with an unnamed total row,
and a GENEL TOPLAM; 2015-2025 rows are country × province, each country closing with a
"<country> TOPLAM" row, and one Türkiye TOPLAM. Every province is listed in every year.

Countries: the names changed in 2019 (ÇİN HALK CUMHURİYETİ → ÇİN, BİRLEŞİK DEVLETLER → ABD,
truncated names written out). The 2019-2025 names are the codes; `ALIASES` sends each older name to
one of them. Parts printed separately before 2019 are added to the country they belong to
(Dubai, Abu Dabi, Şarja → BAE; Kanarya Adaları, Melilla → İspanya; Hawaii, Porto Riko → ABD;
Kuzey İrlanda → Birleşik Krallık; Çeçenistan, Dağıstan, Tataristan, Yakutistan → Rusya; Zanzibar →
Tanzanya …); names with no later counterpart keep their own code. Free zones (serbest bölge) are
destinations of their own, as TİM prints them.

Checks: the provinces' rows add up to the printed Türkiye total (2013-2014 also each province's
total), within the rounding of the file (the per-country TOPLAM rows are not used: 2021-2024 leave
some out or print them short); per year, each province's
countries add up to `tim_exports` (the separate province file), as the sectors do.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from pathlib import Path

import polars as pl

from .kgm import fold
from .tim import FOLDER, NUMBER, area_of, read_year, sheet_rows
from .tim_sectors import DECEMBER_MONTH, NOVEMBER, YEAR_TO_DATE, columns, files

FIRST_YEAR = 2013
#: folded pre-2019 name -> the 2019-2025 printed name it is written under
ALIASES = {
    "abudabi": "BAE",
    "dubai": "BAE",
    "sarjasharjah": "BAE",
    "birlesikarapemirli": "BAE",
    "birlesikarapemirlikleri": "BAE",
    "adanayumurtserbol": "YUMURTALIK SERBEST BÖLGESİ",
    "ahlserbestbolge": "AHL SERBEST BÖLGESİ",
    "antalyaserbestbol": "ANTALYA SERBEST BÖLGESİ",
    "antiguavebermuda": "ANTİGUA VE BARBUDA",
    "avrupaserbestbolg": "ÇORLU AVRUPA SERBEST BÖLGESİ",
    "azerbaycannahcivan": "AZERBAYCAN",
    "azerbeycannahcivan": "AZERBAYCAN",
    "belcikaluksemburg": "BELÇİKA",
    "belckaluksemburg": "BELÇİKA",  # 2015-2016 print a "?" for İ
    "beyazrusya": "BELARUS",
    "bilinmeyenulke": "BELİRLENEMEYEN ÜLKE VE BÖLGELER",
    "birdevminoroutly": "ABD KÜÇÜK OUT.ADL.",
    "birlesikdevletler": "ABD",
    "havai": "ABD",
    "portoriko": "ABD",
    "bostvana": "BOTSVANA",
    "brunei": "BRUNEY",
    "buhutan": "BUTAN",
    "bursaserbestbolg": "BURSA SERBEST BÖLGESİ",
    "capeverde": "CABO VERDE",
    "cecencumhuriyeti": "RUSYA FEDERASYONU",
    "dagistancumhuriyeti": "RUSYA FEDERASYONU",
    "tataristan": "RUSYA FEDERASYONU",
    "yakutistan": "RUSYA FEDERASYONU",
    "cekcumhuriyeti": "ÇEKYA",
    "cinhalkcumhuriyeti": "ÇİN",
    "curacaoadasi": "CURAÇAO",
    "hollandaantilleri": "CURAÇAO",
    "denizliserbestbolg": "DENİZLİ SERBEST BÖLGESİ",
    "dogutimor": "DOĞU TİMUR",
    "dominika": "DOMİNİK",
    "egeserbestbolge": "EGE SERBEST BÖLGESİ",
    "fildisisahili": "KOTDİVUAR",
    "fransizguneytoprak": "FRANSA GÜNEY BÖLGESİ",
    "gaziantepserbbolg": "GAZİANTEP SERBEST BÖLGESİ",
    "guadeloupe": "FRANSA",
    "reunion": "FRANSA",
    "guneyafrikacumhuri": "GÜNEY AFRİKA CUMHURİYETİ",
    "guneykorecumhuriye": "GÜNEY KORE",
    "cebelitarik": "CEBELİTARIK",
    "gungeorgvesandad": "GÜNEY GEORGIA VE GÜNEY SANDWICH ADALARI",
    "ingilizhintokytop": "BRİTANYA HİNT OKYANUSU TOPRAKLARI",
    "ingilizvirjinadala": "BRİTANYA VİRJİN AD.",
    "iranislamcum": "İRAN",
    "isgalaltfilistint": "FİLİSTİN DEVLETİ",
    "kanaryaadalari": "İSPANYA",
    "melilla": "İSPANYA",
    "kayseriserbestblg": "KAYSERİ SERBEST BÖLGESİ",
    "kibris": "GÜNEY KIBRIS RUM YÖNETİMİ",
    "kktc": "KUZEY KIBRIS TÜRK CUM.",
    "kuzeykibristurkcu": "KUZEY KIBRIS TÜRK CUM.",
    "kocaeliserbestblg": "KOCAELİ SERBEST BÖLGESİ",
    "komoradalari": "KOMORLAR BİRLİĞİ",
    "kongodemcmezaire": "KONGO DEMOKRATİK CUMHURİYETİ",
    "kongodemczaire": "KONGO DEMOKRATİK CUMHURİYETİ",
    "kongohalkcumhur": "KONGO",
    "kuzeyirlanda": "BİRLEŞİK KRALLIK",
    "kuzeykoredemokrati": "KUZEY KORE",
    "kuzeymarianaadalar": "KUZEY MARİANA ADALARI",
    "laoshalkcum": "LAOS",
    "lihtenstayn": "LİECHTENSTEİN",
    "maheadasi": "SEYŞELLER",
    "seyseladalariveba": "SEYŞELLER",
    "maldivadalari": "MALDİVLER",
    "marshalladalari": "MARŞAL ADALARI",
    "mersinserbestbolge": "MERSİN SERBEST BÖLGESİ",
    "moldavya": "MOLDOVA",
    "monaco": "FRANSA",
    "myanmarburma": "MYANMAR",
    "ortaafrikacumhuriy": "ORTA AFRİKA CUMHURİYETİ",
    "samoabatisamoa": "SAMOA",
    "samsunserbestbolg": "SAMSUN SERBEST BÖLGESİ",
    "saotomeveprincipe": "SAO TOME VE PRİNSİPE",
    "stpierrevemiquelo": "ST. PİERRE VE MİQUELON",
    "stvincentvegrenad": "ST. VİNCENT VE GRENADİNES",
    "suriyearapcumsur": "SURİYE",
    "tanzanyabirlescum": "TANZANYA",
    "zanzibar": "TANZANYA",
    "trabzonserbestblg": "TRABZON SERBEST BÖLGESİ",
    "trakyaserbestbolge": "TRAKYA SERBEST BÖLGESİ",
    "tubitakmamteknsb": "TÜBİTAK MAM TEKNOLOJİ SERBEST BÖLGESİ",
    "turksvecaicosadas": "TÜRK VE CAİCOS AD.",
    "vallisvefutunaada": "VALLİS VE FUTUNA",
    "venezuella": "VENEZUELA",
    "venuatu": "VANUATU",
    "vietnamguney": "VİETNAM",
    "vietnamkuzey": "VİETNAM",
    "yenikalodenyaveba": "YENİ KALEDONYA",
    "yugoslavya": "SIRBİSTAN",
}
Values = dict[tuple[str, str], float]  # (country code, province) -> thousand dollars


def country_code(name: str) -> str:
    """The code of a printed name: its 2019-2025 name, lower-case ASCII words joined by `_`."""
    key = fold(name)
    printed = ALIASES.get(key, name)
    words = [fold(w) for w in re.split(r"[\s.\-/()]+", printed)]
    return "_".join(w for w in words if w)


def label(name: str) -> str:
    """ABD KÜÇÜK OUT.ADL. -> Abd Küçük Out.adl.; kept close to print, only the case lowered."""
    lower = name.replace("İ", "i").replace("I", "ı").lower()
    return re.sub(
        r"(^|[\s\-(])(\w)",
        lambda m: m.group(1) + m.group(2).replace("i", "İ").replace("ı", "I").upper(),
        lower,
    )


def read(path: Path, pattern: re.Pattern, year: int) -> tuple[Values, dict[str, str]]:
    """One year of a country file, checked; also {code: printed 2019+ name or old name}."""
    rows = sheet_rows(path)
    years, start = columns(rows, pattern)
    j = years[year]
    out: Values = defaultdict(float)
    names: dict[str, str] = {}
    province_totals: dict[str, float] = {}
    grand = None
    for row in rows[start:]:
        country, province = ([*row, "", ""])[:2]
        value = float(row[j]) if j < len(row) and NUMBER.fullmatch(row[j]) else 0.0
        c, p = fold(country), fold(province)
        if c in ("toplam", "geneltoplam") or (not c and p == "toplam"):
            if value and grand is None:
                grand = value
            continue
        if not c and not p:
            continue
        if not c:
            area = area_of(province)
            if area is None:
                raise ValueError(f"TİM ülke {path.name}: tanınmayan il {province}")
            province_totals[area] = value
            continue
        code = country_code(country)
        names.setdefault(code, ALIASES.get(c, country))
        if p == "toplam":
            continue  # 2021-2024 leave some out or print them short: not a check
        area = area_of(province)
        if area is None:
            raise ValueError(f"TİM ülke {path.name}: tanınmayan il {province}")
        out[code, area] += value

    if grand is None:
        raise ValueError(f"TİM ülke {path.name}: Türkiye toplamı yok")
    total = sum(out.values())
    if abs(total - grand) > max(50.0, grand * 1e-6):
        raise ValueError(
            f"TİM ülke {path.name} {year}: iller {total:,.0f}, toplam {grand:,.0f}"
        )
    for area, printed in province_totals.items():
        read_sum = sum(v for (_, a), v in out.items() if a == area)
        if abs(read_sum - printed) > max(50.0, printed * 1e-4):
            raise ValueError(
                f"TİM ülke {path.name} {year} {area}: ülkeler {read_sum:,.0f}, il {printed:,.0f}"
            )
    return dict(out), names


def by_year() -> tuple[dict[int, Values], dict[str, str]]:
    found = files("ulke")
    out: dict[int, Values] = {}
    names: dict[str, str] = {}
    for year in range(FIRST_YEAR, 2026):
        if year in (2017, 2018):
            november, n1 = read(found[year, 11], NOVEMBER, year)
            december, n2 = read(found[year + 1, 1], DECEMBER_MONTH, year)
            keys = november.keys() | december.keys()
            out[year] = {k: november.get(k, 0.0) + december.get(k, 0.0) for k in keys}
            parts = [n1, n2]
        else:
            out[year], n = read(found[year, 12], YEAR_TO_DATE, year)
            parts = [n]
        for part in parts:
            for code, name in part.items():
                # the latest year's printing wins, so a code carries its 2019+ name
                names[code] = name
    # Two spellings that differ only in spaces or dots ("CEBELİ TARIK", "CEBELİTARIK") would
    # become two codes and split one country's series without a word.
    seen: dict[str, str] = {}
    for code in names:
        other = seen.setdefault(code.replace("_", ""), code)
        if other != code:
            raise ValueError(f"TİM ülke: {other} ve {code} aynı ülke, ALIASES'a ekle")
    return out, names


def check_against_provinces(data: dict[int, Values]) -> None:
    from .tim import december_files

    province_files = december_files()
    for year, values in data.items():
        provinces = read_year(year, province_files[year])  # dollars
        sums: dict[str, float] = defaultdict(float)
        for (_, p), v in values.items():
            sums[p] += v
        for p, v in provinces.items():
            if abs(sums[p] - v / 1000) > max(50.0, v / 1000 * 0.02):
                raise ValueError(
                    f"TİM ülke {year} {p}: ülkeler {sums[p]:,.0f}, il {v / 1000:,.0f}"
                )


class TimCountryExports:
    source_id = "tim"
    indicator_id = "tim_exports_by_country"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        data, _ = by_year()
        check_against_provinces(data)
        records = [
            {
                "area_id": area,
                "period_start": dt.date(year, 1, 1),
                "dims": "export_country=" + country,
                "value": value,
            }
            for year, values in sorted(data.items())
            for (country, area), value in sorted(values.items())
            if abs(value) >= 0.0005
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("thousand_usd").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
        )


TIM_COUNTRY_ADAPTERS = {"tim_exports_by_country": TimCountryExports}
