"""Mortality with the age structure taken out of the way.

A crude death rate says almost nothing about mortality: Sındırgı's 15,79‰ against
Silopi's 2,14‰ is a difference in how old the two places are, not in how likely anyone is
to die. Three readings take that out, and this book is the three of them.

* **Yaşa göre ölüm hızı** — deaths at an age over the people at that age. The only
  reading that answers "did dying get less likely" without an argument. Nationally it
  fell in every band between 2014 and 2025 except one, and that exception (15-44, +1,6%)
  is the finding.
* **65+ ölümlerdeki pay** — of all deaths, how many were of people over 65, beside the
  share of the population they are. Two provinces with the same crude rate can be at
  opposite ends of this, and it says which of the two is old and which is unhealthy.
* **Yaşam süresi** — TÜİK's own life table, which is the age-standardised answer by
  construction. Published for the country every year and for provinces only five times
  (2013, 2014, 2017, 2020, 2023), pooled over three years, so a province figure carries
  the pandemic and the earthquake inside it rather than beside it.

Read straight from the MEDAS exports rather than the warehouse, as the district book
does: deaths by age and the life tables are downloaded but not yet loaded, and the file
says so rather than waiting for them.

Run:  uv run python scripts/build_mortality_excel.py
"""

from __future__ import annotations

import collections
import csv
import re
import sys

import polars as pl
import xlsxwriter

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from build_analysis_books import notes_sheet, ranked, sheet, styles

from veriatlas.config import PUBLIC, RAW

TARGET = PUBLIC.parent / "cikti" / "analiz-7-olum-ve-yasam-suresi.xlsx"
SOURCE = RAW / "medas" / "basit"
DATA = PUBLIC.parent / "src" / "veriatlas" / "data"

FIRST, LAST = 2014, 2025

#: Death bands to population ages. The two sides are published differently — deaths come
#: in the source's own bands, population in single years at province level — so the map is
#: written once here rather than guessed at each use.
BANDS = {
    "0-14": (["0", "1-4", "5-9", "10-14"], 0, 14),
    "15-44": (["15-19", "20-24", "25-29", "30-34", "35-39", "40-44"], 15, 44),
    "45-64": (["45-49", "50-54", "55-59", "60-64"], 45, 64),
    "65-74": (["65-69", "70-74"], 65, 74),
    "75+": (["75+"], 75, 200),
}

AGE_IN_LABEL = re.compile(r"yaş grubu:\d*\.?\s*\(([^)]+)\)")
SEX_IN_LABEL = re.compile(r"cinsiyeti\s*:\s*(Erkek|Kadın)")
AREA = re.compile(r"^(?P<name>.+)-(?P<code>[A-Z0-9]+)$")


def deaths_by_age() -> dict:
    """(area code, sex, band, year) → deaths, from every downloaded slice."""
    found: dict = collections.defaultdict(float)
    for path in sorted(SOURCE.glob("nufus-olum-yas-*.csv")):
        table = list(csv.reader(path.open(encoding="utf-8-sig"), delimiter="|"))
        header = {}
        for index, cell in enumerate(table[1]):
            label = AREA.match(cell.strip())
            if label:
                header[index] = label.group("code")
        label = ""
        for row in table:
            if len(row) < 4:
                continue
            if row[1].strip():
                label = row[1].strip()
            year = row[2].strip()
            if not (year.isdigit() and len(year) == 4):
                continue
            band = AGE_IN_LABEL.search(label)
            sex = SEX_IN_LABEL.search(label)
            if not (band and sex):
                continue
            for index, code in header.items():
                if index >= len(row) or not row[index].strip():
                    continue
                key = (code, sex.group(1), band.group(1), int(year))
                found[key] += float(row[index])
    if not found:
        raise SystemExit(
            "ölenin yaşı dosyası yok — önce: uv run python scripts/fetch_medas_simple.py "
            "olum-yas"
        )
    return found


def life_expectancy() -> tuple[dict, dict]:
    """Country life table by single age, and the province figures for the five years."""
    single: dict = {}
    path = SOURCE / "nufus-hayat-tablosu-country.csv"
    if path.exists():
        label = ""
        for row in csv.reader(path.open(encoding="utf-8-sig"), delimiter="|"):
            if len(row) < 4:
                continue
            if row[1].strip():
                label = row[1].strip()
            year = row[2].strip()
            if not (year.isdigit() and len(year) == 4) or not row[3].strip():
                continue
            found = re.match(r"(Erkek|Kadın)\s*ve\s*(\d+)", label)
            if found:
                single[(found.group(1), int(found.group(2)), int(year))] = float(row[3])

    provinces: dict = {}
    path = SOURCE / "nufus-yasam-suresi-province.csv"
    if path.exists():
        table = list(csv.reader(path.open(encoding="utf-8-sig"), delimiter="|"))
        header = {
            index: AREA.match(cell.strip()).group("name")
            for index, cell in enumerate(table[1])
            if AREA.match(cell.strip())
        }
        label = ""
        for row in table:
            if len(row) < 4:
                continue
            if row[1].strip():
                label = row[1].strip()
            year = row[2].strip()
            if not (year.isdigit() and len(year) == 4):
                continue
            for index, name in header.items():
                if index < len(row) and row[index].strip():
                    provinces[(label, name, int(year))] = float(row[index])
    return single, provinces


def population() -> tuple[dict, dict]:
    """Province and country population by single age, from the fact table."""
    fact = pl.read_parquet(PUBLIC / "fact.parquet").with_columns(
        pl.col("period_start").dt.year().alias("year")
    )
    rows = (
        fact.filter(
            (pl.col("indicator_id") == "population")
            & pl.col("area_level").is_in(["province", "country"])
        )
        .with_columns(pl.col("dims").str.extract(r"age=([^;]*)").alias("age"))
        .with_columns(
            pl.when(pl.col("age") == "75+")
            .then(pl.lit(75))
            .otherwise(pl.col("age").str.replace(r"\+", "").cast(pl.Int32, strict=False))
            .alias("yas")
        )
    )
    by_band: dict = collections.defaultdict(float)
    whole: dict = collections.defaultdict(float)
    for row in rows.iter_rows(named=True):
        # The area code MEDAS uses is the plate number; the fact table's id carries it.
        code = row["area_id"].split("-")[-1].lstrip("0") or "0"
        code = "TR" if row["area_level"] == "country" else code
        whole[(code, row["year"])] += row["value"]
        for band, (_, low, high) in BANDS.items():
            if row["yas"] is not None and low <= row["yas"] <= high:
                by_band[(code, band, row["year"])] += row["value"]
    return by_band, whole


def main() -> None:
    deaths = deaths_by_age()
    single, province_life = life_expectancy()
    by_band, whole = population()

    # Provinces only. The registry also holds the country and the İBBS levels, whose ids
    # end in letters rather than a plate number — left in, they became forty-five extra
    # "provinces" with no deaths in them.
    provinces = (
        pl.read_csv(DATA / "areas_tr.csv")
        .filter(pl.col("area_level") == "province")
        .select("area_id", pl.col("name_tr").alias("il"))
    )
    code_of = {
        r["area_id"].split("-")[-1].lstrip("0"): r["il"]
        for r in provinces.iter_rows(named=True)
    }

    # region Türkiye by age
    rows = []
    for band, (parts, _, _) in BANDS.items():
        line = {"bant": band}
        for year, tag in ((FIRST, "_ilk"), (LAST, "_son")):
            count = sum(
                deaths.get(("TR", sex, part, year), 0.0)
                for sex in ("Erkek", "Kadın")
                for part in parts
            )
            people = by_band.get(("TR", band, year), 0.0)
            line["olum" + tag] = count
            line["hiz" + tag] = 1000 * count / people if people else None
        line["olum_oran"] = line["olum_son"] / line["olum_ilk"] - 1
        line["hiz_oran"] = line["hiz_son"] / line["hiz_ilk"] - 1
        rows.append(line)
    country = pl.DataFrame(rows)
    # endregion

    # region Provinces: the 65+ share of deaths against the 65+ share of people
    lines = []
    for code, name in code_of.items():
        line = {"il": name}
        for year, tag in ((FIRST, "_ilk"), (LAST, "_son")):
            total = sum(
                deaths.get((code, sex, part, year), 0.0)
                for sex in ("Erkek", "Kadın")
                for parts in BANDS.values()
                for part in parts[0]
            )
            old = sum(
                deaths.get((code, sex, part, year), 0.0)
                for sex in ("Erkek", "Kadın")
                for band in ("65-74", "75+")
                for part in BANDS[band][0]
            )
            young = sum(
                deaths.get((code, sex, part, year), 0.0)
                for sex in ("Erkek", "Kadın")
                for part in BANDS["0-14"][0]
            )
            people = whole.get((code, year), 0.0)
            elderly = by_band.get((code, "65-74", year), 0.0) + by_band.get(
                (code, "75+", year), 0.0
            )
            line["olum" + tag] = total
            line["olum65_pay" + tag] = old / total if total else None
            line["olum014_pay" + tag] = young / total if total else None
            line["nufus65_pay" + tag] = elderly / people if people else None
            line["hiz65" + tag] = 1000 * old / elderly if elderly else None
        line["fark"] = (
            line["olum65_pay_son"] - line["olum65_pay_ilk"]
            if line["olum65_pay_ilk"]
            else None
        )
        lines.append(line)
    province_ages = ranked(
        pl.DataFrame(lines).select(
            "il",
            "olum_son",
            "nufus65_pay_ilk",
            "nufus65_pay_son",
            "olum65_pay_ilk",
            "olum65_pay_son",
            "fark",
            "olum014_pay_ilk",
            "olum014_pay_son",
            "hiz65_ilk",
            "hiz65_son",
        ),
        "olum65_pay_son",
    )
    # endregion

    # region Life expectancy
    years = sorted({year for _, _, year in province_life})
    life_rows = []
    for name in sorted({n for _, n, _ in province_life}):
        line = {"il": name}
        for year in years:
            male = province_life.get(("Erkek", name, year))
            female = province_life.get(("Kadın", name, year))
            line["e" + str(year) + "_erkek"] = male
            line["e" + str(year) + "_kadin"] = female
            if male and female:
                line["fark" + str(year)] = female - male
        life_rows.append(line)
    life = ranked(pl.DataFrame(life_rows), "fark" + str(years[-1]))

    ages = sorted({age for _, age, _ in single})
    table_rows = []
    for age in ages:
        line = {"yas": age}
        for year in (2013, 2019, 2021, 2023, 2025):
            for sex, tag in (("Erkek", "_erkek"), ("Kadın", "_kadin")):
                line["e" + str(year) + tag] = single.get((sex, age, year))
        table_rows.append(line)
    country_life = pl.DataFrame(table_rows)
    # endregion

    # region Writing
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    book = xlsxwriter.Workbook(str(TARGET))
    style = styles(book)
    formats = {**style, "il": style["left"], "bant": style["left"], "yas": style["text"]}
    for frame in (country, province_ages, life, country_life):
        for column in frame.columns:
            if column.startswith(("olum6", "olum0", "nufus6")) or column.endswith(
                ("_oran", "fark")
            ):
                formats[column] = style["percent"]
            elif column.startswith(("hiz", "e")):
                formats[column] = style["rate"]
            elif column.startswith("olum"):
                formats[column] = style["count"]
    formats["fark"] = style["percent"]
    for year in years:
        formats["fark" + str(year)] = style["rate"]

    headers = {
        "bant": "Yaş bandı",
        "olum_ilk": f"Ölüm {FIRST}",
        "olum_son": f"Ölüm {LAST}",
        "olum_oran": "Ölüm sayısı değişimi",
        "hiz_ilk": f"Ölüm hızı ‰ {FIRST}",
        "hiz_son": f"Ölüm hızı ‰ {LAST}",
        "hiz_oran": "Ölüm hızı değişimi",
        "nufus65_pay_ilk": f"65+ nüfus payı {FIRST}",
        "nufus65_pay_son": f"65+ nüfus payı {LAST}",
        "olum65_pay_ilk": f"65+ ölümlerdeki payı {FIRST}",
        "olum65_pay_son": f"65+ ölümlerdeki payı {LAST}",
        "fark": "65+ ölüm payı farkı",
        "olum014_pay_ilk": f"0-14 ölümlerdeki payı {FIRST}",
        "olum014_pay_son": f"0-14 ölümlerdeki payı {LAST}",
        "hiz65_ilk": f"65+ ölüm hızı ‰ {FIRST}",
        "hiz65_son": f"65+ ölüm hızı ‰ {LAST}",
        "yas": "Yaş",
        **{
            "e" + str(y) + t: f"{y} " + ("erkek" if t == "_erkek" else "kadın")
            for y in (2013, 2019, 2021, 2023, 2025)
            for t in ("_erkek", "_kadin")
        },
        **{"fark" + str(y): f"{y} kadın−erkek" for y in years},
    }
    widths = {"il": 15, "bant": 12, "sira": 6, "yas": 6}

    sheet(book, country, "Türkiye — yaşa göre", headers, formats, widths, {"hiz_oran": "down"})
    sheet(
        book,
        province_ages,
        "İller — ölümün yaşı",
        headers,
        formats,
        widths,
        {"olum65_pay_son": "up", "nufus65_pay_son": "up"},
    )
    sheet(book, life, "İller — yaşam süresi", headers, formats, widths)
    sheet(book, country_life, "Türkiye — hayat tablosu", headers, formats, widths)
    notes_sheet(
        book,
        [
            f"Ölümün yaşı ve yaşam süresi — {FIRST}-{LAST}",
            "",
            "Kaba ölüm hızı mortaliteyi ölçmez, yaşı ölçer: Sındırgı'nın 15,79'u ile",
            "Silopi'nin 2,14'ü ölme ihtimali farkı değil, yaş farkıdır. Bu dosyadaki üç",
            "okuma yaşı aradan çıkarır.",
            "",
            "YAŞA GÖRE ÖLÜM HIZI — o yaştaki ölüm, o yaştaki nüfusa bölünmüş. Tartışmasız",
            "cevap veren tek okuma. Türkiye'de 2014-2025 arası bütün bantlarda düştü:",
            "0-14'te %43,8, 65-74'te %12,4, 75+'ta %8,4. Tek istisna 15-44 (+%1,6) ve asıl",
            "bulgu o: her yaşta ölüm azalırken genç yetişkinde azalmıyor.",
            "",
            "65+ ÖLÜMLERDEKİ PAY — bütün ölümlerin yüzde kaçı 65 üstündeydi, yanında o",
            "yaşın nüfustaki payıyla. Aynı kaba ölüm hızına sahip iki il bu sütunda zıt",
            "uçlarda olabilir; hangisinin yaşlı hangisinin sağlıksız olduğunu bu söyler.",
            "",
            "YAŞAM SÜRESİ — TÜİK'in kendi hayat tablosu, yani yapısı gereği yaşa göre",
            "arındırılmış. Ülke için her yıl, iller için yalnız beş kez yayımlanıyor",
            "(2013, 2014, 2017, 2020, 2023) ve üç yıllık havuzla. Bu yüzden bir ilin 2023",
            "değeri pandemiyi ve depremi yanında değil, içinde taşır.",
            "",
            "SINIRLAR",
            "· Ölenin yaşı ve hayat tabloları indirildi ama henüz olgu tablosuna",
            "  alınmadı; bu dosya ham MEDAS dışa aktarımlarını doğrudan okuyor.",
            "· Ölüm bantları kaynağın kendi bantları, nüfus tek yaştan toplandı; ikisinin",
            "  eşleşmesi BANDS tablosunda bir kez yazılı.",
            "· Tek yaş hayat tablosu yalnız Türkiye için var — bir ilin 93 yaşındaki",
            "  ölümleri birkaç kişi, olasılık gürültü olurdu.",
        ],
    )
    book.close()
    # endregion

    print("yazildi:", TARGET)
    print(
        "  Türkiye bandı:", len(country),
        "| İller:", len(province_ages),
        "| Yaşam süresi:", len(life),
        "| Hayat tablosu yaşı:", len(country_life),
    )


if __name__ == "__main__":
    main()
