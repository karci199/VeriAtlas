r"""TİM (Türkiye İhracatçılar Meclisi) exports by province and sector, 2013-2025.

`scripts/fetch_tim.py` keeps the monthly "İller Bazında Sektör" workbooks in
`C:\veri-ham\tim\<year>\<month>`. Each December file prints the year to date ("1 Ocak-31.12.2014",
"1 OCAK - 31 ARALIK") for this year and the one before; this year's column is read.

Layouts: 2013-2014 open each province with an unnamed total row; 2015-2025 print it as TOPLAM in
the sector column. The sectors never add up to the province: exports under no printed sector
(a second unnamed row in 2013-2014, and more) are written as `unclassified`, 1-4 % a year.

Gaps: the 2017 December file is November's, and there is no 2018 December file; both years are
January-November plus December's month from the next January file. The following year's
previous-year column is not used: it drops sectors that are zero in the new year, and restates the
old year by the exporters' new seats (2018 in the 2019 file: Bursa +19 %, İstanbul -3.7 %). For
the same reason 2012 is not loaded: its own file leaves out sector rows (Eskişehir 31 %).

Sectors: TİM renamed some in 2015 and 2021 (Taşıt Araçları → Otomotiv Endüstrisi, Değerli Maden
→ Mücevher, Elektrik - Elektronik → Elektrik Elektronik ve Hizmet → Elektrik ve Elektronik …);
`SECTORS` maps every printed name to one code. "Diğer Sanayi Ürünleri" is not printed in 2025.

Checks: per file, the provinces add up to the printed Türkiye total; per year, the sectors add up
to `tim_exports` (the separate province file) in every province: to the rounding in 2013-2016 and
2019-2025, within 2 % in 2017-2018, where the months come from files revised a month apart.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable
from pathlib import Path

import polars as pl

from .kgm import fold
from .tim import FOLDER, NUMBER, area_of, read_year, sheet_rows

FIRST_YEAR = 2013
#: folded printed name prefix -> code, first match wins
SECTORS = (
    ("agacmamulleri", "furniture_paper_forestry"),
    ("mobilya", "furniture_paper_forestry"),
    ("celik", "steel"),
    ("cimento", "cement_glass_ceramics"),
    ("degerlimaden", "jewellery"),
    ("mucevher", "jewellery"),
    ("demirvedemirdisi", "ferrous_nonferrous_metals"),
    ("deri", "leather"),
    ("digersanayi", "other_industrial"),
    ("elektrik", "electrical_electronics"),
    ("findik", "hazelnuts"),
    ("gemi", "ships_yachts"),
    ("hali", "carpets"),
    ("hazirgiyim", "apparel"),
    ("hububat", "cereals_pulses_oilseeds"),
    ("iklimlendirme", "air_conditioning"),
    ("kimyevi", "chemicals"),
    ("kurumeyve", "dried_fruits"),
    ("madenvemetaller", "mining"),
    ("madencilik", "mining"),
    ("makine", "machinery"),
    ("meyvesebzemamulleri", "fruit_vegetable_products"),
    ("suurunleri", "fishery_animal_products"),
    ("susbitkileri", "ornamental_plants"),
    ("tasitaraclari", "automotive"),
    ("otomotiv", "automotive"),
    ("tekstil", "textiles"),
    ("tutun", "tobacco"),
    ("yasmeyve", "fresh_fruit_vegetables"),
    ("zeytin", "olive_oil"),
)
UNCLASSIFIED = "unclassified"
TOTALS = ("geneltoplam", "toplam")
Values = dict[tuple[str, str], float]  # (sector, province) -> thousand dollars


def sector_code(name: str) -> str:
    key = fold(name)
    code = next((c for prefix, c in SECTORS if key.startswith(prefix)), None)
    if code is None:
        raise ValueError(f"TİM sektör: tanınmayan sektör {name}")
    return code


def files(kind: str = "sektor") -> dict[tuple[int, int], Path]:
    out: dict[tuple[int, int], Path] = {}
    for line in (FOLDER / "index.tsv").read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) < 2 or kind not in parts[1].lower():
            continue
        year, month = parts[1].split("/")[:2]
        path = FOLDER / parts[1].strip()
        if path.exists():
            out[int(year), int(month)] = path  # a repeated month: the later entry
    return out


def columns(rows: list[list[str]], label: re.Pattern) -> tuple[dict[int, int], int]:
    """{year: column} under the first label matching `label`, and the first data row."""
    for i, row in enumerate(rows[:6]):
        hits = [j for j, c in enumerate(row) if label.search(c)]
        if not hits:
            continue
        years = {}
        for j in hits:  # 2012-2014: one label per year, the year inside it
            found = re.search(r"(20\d\d)\s*$", rows[i][j])
            if found:
                years[int(found.group(1))] = j
        if years:
            return years, i + 1
        below = rows[i + 1]  # 2015+: the years in the row under the label
        for j in range(hits[0], len(below)):
            if re.fullmatch(r"20\d\d(\.0)?", below[j]):
                years[int(float(below[j]))] = j
            elif years:
                break
        return years, i + 2
    raise ValueError("TİM sektör: sütun yok")


def read(
    path: Path, label: re.Pattern, year: int, code: Callable[[str], str] = sector_code
) -> Values:
    """One year of a file under `label`, checked against its printed totals.

    Only the wanted year is checked: the previous-year column of 2012 does not add up.
    """
    rows = sheet_rows(path)
    years, start = columns(rows, label)
    if year not in years:
        raise ValueError(f"TİM sektör {path.name}: {year} sütunu yok")
    years = {year: years[year]}
    (first,) = years.values()
    out: dict[int, Values] = {y: {} for y in years}
    # province -> year -> unnamed rows (2012-2014: its total, and any unclassified exports)
    unnamed: dict[str, dict[int, list[float]]] = {}
    printed: dict[int, float] = {}

    def number(row: list[str], j: int) -> float:
        return float(row[j]) if j < len(row) and NUMBER.fullmatch(row[j]) else 0.0

    for row in rows[start:]:
        texts = [c for c in row[:first] if c and not NUMBER.fullmatch(c)]
        if not texts:
            continue
        values = {y: number(row, j) for y, j in years.items()}
        named = [t for t in texts if area_of(t) is not None]
        sectors = [t for t in texts if area_of(t) is None and fold(t) not in TOTALS]
        if not named and any(fold(t) in TOTALS for t in texts):
            if all(abs(v) < 1 for v in values.values()):
                # 2015-2020 repeat TOPLAM as an empty row; 2017 prints 702 dollars with no
                # province under the last one, with a TOPLAM of its own
                continue
            if printed:
                raise ValueError(f"TİM sektör {path.name}: iki toplam satırı")
            printed = values
            continue
        # a province's own total: unnamed (2012-2014) or "TOPLAM" in the sector column
        if len(named) > 1 or len(sectors) > 1:
            raise ValueError(f"TİM sektör {path.name}: çözülemeyen satır {texts}")
        if not named:
            if all(abs(v) < 1 for v in values.values()):
                continue  # see TOPLAM above
            raise ValueError(f"TİM sektör {path.name}: il yok {texts}")
        province = area_of(named[0])
        if not sectors:
            slot = unnamed.setdefault(province, {y: [] for y in years})
            for y, v in values.items():
                slot[y].append(v)
            continue
        name = code(sectors[0])
        for y, v in values.items():
            key = (name, province)
            if key in out[y]:
                raise ValueError(f"TİM sektör {path.name}: {key} iki kez")
            out[y][key] = v

    for y in years:
        for province, slot in unnamed.items():
            sectors = sum(v for (_, p), v in out[y].items() if p == province)
            rows_ = slot[y]
            # The largest unnamed row is the province total. The sectors do not add up to it:
            # the rest (a second unnamed row, and exports under no printed sector) is kept as
            # unclassified, so the sectors add up to the province.
            total = max(rows_)
            rest = total - sectors
            if rest < -3.0:
                raise ValueError(
                    f"TİM sektör {path.name} {y} {province}: sektörler "
                    f"{sectors:,.0f}, il toplamı {total:,.0f}"
                )
            rest = rest if rest > 3.0 else 0.0
            if rest:
                out[y][(UNCLASSIFIED, province)] = rest
        if y in printed:
            read_sum = sum(out[y].values())
            if abs(read_sum - printed[y]) > max(3.0, printed[y] * 1e-6):
                raise ValueError(
                    f"TİM sektör {path.name} {y}: iller {read_sum:,.0f}, "
                    f"TOPLAM {printed[y]:,.0f}"
                )
    return out[year]


YEAR_TO_DATE = re.compile(r"(?i)ocak\s*-\s*31[.\s]*(12|aral)")
NOVEMBER = re.compile(r"(?i)ocak\s*-\s*30\s*kas")
DECEMBER_MONTH = re.compile(r"(?i)^1\s*-\s*31\s*aral")


def by_year() -> dict[int, Values]:
    found = files()
    out: dict[int, Values] = {}
    for year in range(FIRST_YEAR, 2026):
        if year in (2017, 2018):
            november = read(found[year, 11], NOVEMBER, year)
            december = read(found[year + 1, 1], DECEMBER_MONTH, year)
            keys = november.keys() | december.keys()
            out[year] = {k: november.get(k, 0.0) + december.get(k, 0.0) for k in keys}
        else:
            out[year] = read(found[year, 12], YEAR_TO_DATE, year)
    return out


def check_against_provinces(data: dict[int, Values]) -> None:
    from .tim import december_files

    province_files = december_files()
    for year, values in data.items():
        provinces = read_year(year, province_files[year])  # dollars
        sums: dict[str, float] = {}
        for (_, p), v in values.items():
            sums[p] = sums.get(p, 0.0) + v
        total_s, total_p = sum(sums.values()), sum(provinces.values()) / 1000
        if abs(total_s - total_p) > total_p * 1e-3:
            raise ValueError(
                f"TİM sektör {year}: toplam {total_s:,.0f}, il dosyası {total_p:,.0f}"
            )
        for p, v in provinces.items():
            s = sums.get(p, 0.0)
            if abs(s - v / 1000) > max(50.0, v / 1000 * 0.02):
                raise ValueError(
                    f"TİM sektör {year} {p}: sektörler {s:,.0f}, il {v / 1000:,.0f}"
                )


class TimSectorExports:
    source_id = "tim"
    indicator_id = "tim_exports_by_sector"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        data = by_year()
        check_against_provinces(data)
        records = [
            {
                "area_id": area,
                "period_start": dt.date(year, 1, 1),
                "dims": "tim_sector=" + sector,
                "value": value,
            }
            for year, values in sorted(data.items())
            for (sector, area), value in sorted(values.items())
            if value
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


TIM_SECTOR_ADAPTERS = {"tim_exports_by_sector": TimSectorExports}
