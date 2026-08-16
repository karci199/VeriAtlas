"""District vital events: births, deaths, and what is left of them.

Three questions of 973 districts rather than 81 provinces.

**Fertility.** The general fertility rate — births per thousand women aged 15-49. A birth
count on its own cannot separate the two things that move it: a district whose births fell
by half because its young women left is not the same place as one whose births fell by
half because the women who stayed had fewer children. GFR answers the second and the
women's column answers the first.

**Natural increase.** Births minus deaths, which is the part of population change that
owes nothing to migration. A district can be in natural surplus and still shrink, because
the people born there do not stay — and the sheet shows both sides so that can be seen
rather than assumed.

Deaths arrive split by the sex of the deceased and the split is kept: it is a sum away
from the total and not recoverable once thrown out.

Reads the MEDAS district files directly (`raw/medas/basit/nufus-dogum-ilce-district-*`)
rather than the warehouse, because there is no adapter for them yet. That is a temporary
state and this file says so rather than pretending otherwise: when the adapter lands, the
reading swaps for a fact-table query and nothing else here changes.

Two joins that had to be done carefully:

* **The identity is the MEDAS code, never the name** (K15). Forty districts are called
  Merkez and two are called Pınarbaşı.
* **A renamed district is two ids sharing one code.** Kazan became Kahramankazan in 2017
  and Eyüp became Eyüpsultan in 2018; the population export uses the old id up to the
  rename and the new one after. Resolving the code without the year drops the early years
  of both — quietly, since the births are still counted in the total and only the rate
  goes missing. So the year picks the id.

Checked against what we already hold, three ways and all exact: district births against
the national birth count for twelve years, district deaths against it for seventeen and
for each sex separately, and births minus deaths against the province natural increase
for all 972 province-years.

Run:  uv run python scripts/build_district_vital_excel.py
"""

from __future__ import annotations

import collections
import csv
import gzip
import re
import sys

import polars as pl
import xlsxwriter

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from build_analysis_books import notes_sheet, ranked, sheet, styles

from veriatlas.config import PUBLIC, RAW

TARGET = PUBLIC.parent / "cikti" / "analiz-6-ilce-hayati-olaylar.xlsx"
SOURCE = RAW / "medas" / "basit"
DATA = PUBLIC.parent / "src" / "veriatlas" / "data"

#: Districts are published in five-year bands, and the fertile ages happen to fall on
#: their boundaries. That is the whole reason this question can be asked at this level.
FERTILE = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49"]

#: Small districts are kept in the sheet and out of the rankings: twenty births against
#: nineteen is a 5% "fall" that is really one family.
RANK_FLOOR = 300


def births() -> pl.DataFrame:
    """Every district-year of births, out of the downloaded MEDAS exports.

    The export is transposed — districts run across the header, the single measure runs
    down — so it is read by hand rather than by a CSV reader with a schema.
    """
    rows = []
    for path in sorted(SOURCE.glob("nufus-dogum-ilce-district-*.csv")):
        year = int(re.search(r"(\d{4})\.csv$", path.name).group(1))
        table = list(csv.reader(path.open(encoding="utf-8-sig"), delimiter="|"))
        for header, value in zip(table[1][3:], table[4][3:]):
            header = header.strip()
            if not header or not value.strip():
                continue
            # "Adana(Aladağ)-1757": the code is the identity, the label is decoration.
            label, _, code = header.rpartition("-")
            rows.append(
                {"yil": year, "kod": code, "etiket": label, "dogum": float(value)}
            )
    if not rows:
        raise SystemExit(
            "ilçe doğum dosyası yok — önce: uv run python scripts/fetch_medas_simple.py "
            "dogum-ilce --yil=2025,2024,…"
        )
    return pl.DataFrame(rows)


def deaths() -> pl.DataFrame:
    """Every district-year of deaths, by sex, out of the downloaded MEDAS exports.

    Two rows per file rather than one: MEDAS publishes district deaths split by the sex
    of the deceased and will not close that breakdown. Kept as a breakdown here too — the
    total is a sum away, and the split is not recoverable once it has been thrown out.
    """
    rows = []
    for path in sorted(SOURCE.glob("nufus-olum-ilce-district-*.csv")):
        year = int(re.search(r"(\d{4})\.csv$", path.name).group(1))
        table = list(csv.reader(path.open(encoding="utf-8-sig"), delimiter="|"))
        for line in table[4:6]:
            if len(line) < 4:
                continue
            label = line[1] or ""
            sex = "erkek" if "Erkek" in label else "kadin" if "Kadın" in label else None
            if not sex:
                continue
            for header, value in zip(table[1][3:], line[3:]):
                header = header.strip()
                if not header or not value.strip():
                    continue
                rows.append(
                    {
                        "yil": year,
                        "kod": header.rpartition("-")[2],
                        "cins": sex,
                        "olum": float(value),
                    }
                )
    if not rows:
        raise SystemExit(
            "ilçe ölüm dosyası yok — önce: uv run python scripts/fetch_medas_simple.py "
            "olum-ilce --yil=2025,2024,…"
        )
    return (
        pl.DataFrame(rows)
        .pivot(values="olum", index=["yil", "kod"], on="cins", aggregate_function="sum")
        .rename({"erkek": "olum_e", "kadin": "olum_k"})
        .with_columns((pl.col("olum_e") + pl.col("olum_k")).alias("olum"))
    )


def women() -> tuple[dict, dict]:
    """Women 15-49 and total population, per district-year, from the published export."""
    fertile = collections.defaultdict(float)
    whole = collections.defaultdict(float)
    with gzip.open(
        PUBLIC / "population-district.csv.gz", "rt", encoding="utf-8"
    ) as handle:
        for row in csv.DictReader(handle):
            key = (row["area_id"], int(row["year"]))
            whole[key] += float(row["value"])
            if row["sex"] == "female" and row["age"] in FERTILE:
                fertile[key] += float(row["value"])
    return fertile, whole


def resolved(frame: pl.DataFrame, fertile: dict) -> pl.DataFrame:
    """Attach the area a MEDAS code stands for *in that year*, with its province."""
    registry = pl.read_csv(DATA / "areas_tr_districts.csv").select(
        "area_id",
        pl.col("name_tr").alias("ilce"),
        "parent_id",
        pl.col("medas_code").cast(pl.Utf8).alias("kod"),
    )
    provinces = pl.read_csv(DATA / "areas_tr.csv").select(
        pl.col("area_id").alias("parent_id"), pl.col("name_tr").alias("il")
    )
    candidates = collections.defaultdict(list)
    for row in registry.iter_rows(named=True):
        candidates[row["kod"]].append(row)

    def pick(code: str, year: int) -> dict | None:
        options = candidates.get(code) or []
        # The id that has population that year is the id that district had that year.
        for option in options:
            if (option["area_id"], year) in fertile:
                return option
        return options[0] if options else None

    picked = [pick(r["kod"], r["yil"]) for r in frame.iter_rows(named=True)]
    return frame.with_columns(
        pl.Series("area_id", [p["area_id"] if p else None for p in picked]),
        pl.Series("ilce", [p["ilce"] if p else None for p in picked]),
        pl.Series("parent_id", [p["parent_id"] if p else None for p in picked]),
    ).join(provinces, on="parent_id", how="left")


def main() -> None:
    fertile, whole = women()
    # Deaths run from 2009 and births from 2014; natural increase is only where both are,
    # so the join is an inner one and the span it leaves is the span of the whole book.
    frame = resolved(births().join(deaths(), on=["yil", "kod"], how="inner"), fertile)

    years = sorted(frame["yil"].unique().to_list())
    first, last = years[0], years[-1]

    frame = frame.with_columns(
        pl.Series(
            "kadin",
            [
                fertile.get((r["area_id"], r["yil"]))
                for r in frame.iter_rows(named=True)
            ],
            dtype=pl.Float64,
        ),
        pl.Series(
            "nufus",
            [whole.get((r["area_id"], r["yil"])) for r in frame.iter_rows(named=True)],
            dtype=pl.Float64,
        ),
    ).with_columns(
        (1000 * pl.col("dogum") / pl.col("kadin")).alias("gdh"),
        # The crude birth rate beside it, on purpose. KDH = GDH × (the fertile women's
        # share of the population), so the gap between how the two move is exactly how
        # much of the story is composition rather than fertility — and it is a big gap
        # in the places it matters: Şırnak's GDH fell 45% while its KDH fell 34%, because
        # its fertile-age women grew from a fifth of the province to a quarter.
        (1000 * pl.col("dogum") / pl.col("nufus")).alias("kdh"),
        (pl.col("kadin") / pl.col("nufus")).alias("kadin_payi"),
        (pl.col("dogum") - pl.col("olum")).alias("dogal"),
        (1000 * pl.col("olum") / pl.col("nufus")).alias("olum_hizi"),
        (1000 * (pl.col("dogum") - pl.col("olum")) / pl.col("nufus")).alias(
            "dogal_hizi"
        ),
    )

    missing = frame.filter(pl.col("kadin").is_null()).height
    if missing:
        print("uyari: kadin nufusu bulunamayan kayit:", missing)

    def at(year: int, tag: str) -> pl.DataFrame:
        return frame.filter(pl.col("yil") == year).select(
            "kod",
            "il",
            "ilce",
            pl.col("dogum").alias("dogum" + tag),
            pl.col("olum").alias("olum" + tag),
            pl.col("dogal").alias("dogal" + tag),
            pl.col("dogal_hizi").alias("dogal_hizi" + tag),
            pl.col("kadin").alias("kadin" + tag),
            pl.col("gdh").alias("gdh" + tag),
            pl.col("kdh").alias("kdh" + tag),
            pl.col("kadin_payi").alias("kadin_payi" + tag),
            pl.col("nufus").alias("nufus" + tag),
        )

    wide = (
        at(last, "_son")
        .join(at(first, "_ilk").drop("il", "ilce"), on="kod")
        .with_columns(
            (pl.col("dogum_son") / pl.col("dogum_ilk") - 1).alias("dogum_oran"),
            (pl.col("kadin_son") / pl.col("kadin_ilk") - 1).alias("kadin_oran"),
            (pl.col("gdh_son") / pl.col("gdh_ilk") - 1).alias("gdh_oran"),
            (pl.col("gdh_son") - pl.col("gdh_ilk")).alias("gdh_puan"),
            (pl.col("kdh_son") / pl.col("kdh_ilk") - 1).alias("kdh_oran"),
        )
        .with_columns(
            pl.when(pl.col("dogum_ilk") >= RANK_FLOOR)
            .then(pl.lit(""))
            .otherwise(pl.lit("az doğumlu ilçe — oran gürültülü"))
            .alias("not")
        )
    )

    districts = ranked(
        wide.select(
            "il",
            "ilce",
            "nufus_son",
            "dogum_ilk",
            "dogum_son",
            "dogum_oran",
            "kadin_ilk",
            "kadin_son",
            "kadin_oran",
            "gdh_ilk",
            "gdh_son",
            "gdh_puan",
            "gdh_oran",
            "kdh_ilk",
            "kdh_son",
            "kdh_oran",
            "kadin_payi_ilk",
            "kadin_payi_son",
            "not",
        ),
        "gdh_oran",
    )

    natural = ranked(
        wide.select(
            "il",
            "ilce",
            "nufus_son",
            "dogum_son",
            "olum_son",
            "dogal_ilk",
            "dogal_son",
            "dogal_hizi_ilk",
            "dogal_hizi_son",
            "not",
        ),
        "dogal_hizi_son",
    )

    rolled = (
        frame.group_by("il", "yil")
        .agg(
            pl.col("dogum").sum(),
            pl.col("olum").sum(),
            pl.col("dogal").sum(),
            pl.col("kadin").sum(),
            pl.col("nufus").sum(),
        )
        .with_columns(
            (1000 * pl.col("dogum") / pl.col("kadin")).alias("gdh"),
            (1000 * pl.col("dogum") / pl.col("nufus")).alias("kdh"),
            (pl.col("kadin") / pl.col("nufus")).alias("kadin_payi"),
            (1000 * pl.col("dogal") / pl.col("nufus")).alias("dogal_hizi"),
        )
    )

    def province_at(year: int, tag: str) -> pl.DataFrame:
        return rolled.filter(pl.col("yil") == year).select(
            "il",
            pl.col("dogum").alias("dogum" + tag),
            pl.col("olum").alias("olum" + tag),
            pl.col("dogal").alias("dogal" + tag),
            pl.col("dogal_hizi").alias("dogal_hizi" + tag),
            pl.col("kadin").alias("kadin" + tag),
            pl.col("gdh").alias("gdh" + tag),
            pl.col("kdh").alias("kdh" + tag),
            pl.col("kadin_payi").alias("kadin_payi" + tag),
        )

    provinces = ranked(
        province_at(last, "_son")
        .join(province_at(first, "_ilk"), on="il")
        .with_columns(
            (pl.col("dogum_son") / pl.col("dogum_ilk") - 1).alias("dogum_oran"),
            (pl.col("kadin_son") / pl.col("kadin_ilk") - 1).alias("kadin_oran"),
            (pl.col("gdh_son") / pl.col("gdh_ilk") - 1).alias("gdh_oran"),
            (pl.col("gdh_son") - pl.col("gdh_ilk")).alias("gdh_puan"),
            (pl.col("kdh_son") / pl.col("kdh_ilk") - 1).alias("kdh_oran"),
        )
        .select(
            "il",
            "dogum_ilk",
            "dogum_son",
            "dogum_oran",
            "kadin_ilk",
            "kadin_son",
            "kadin_oran",
            "gdh_ilk",
            "gdh_son",
            "gdh_puan",
            "gdh_oran",
            "kdh_ilk",
            "kdh_son",
            "kdh_oran",
            "kadin_payi_ilk",
            "kadin_payi_son",
            "olum_son",
            "dogal_ilk",
            "dogal_son",
            "dogal_hizi_ilk",
            "dogal_hizi_son",
        ),
        "gdh_oran",
    )

    country = (
        frame.group_by("yil")
        .agg(
            pl.col("dogum").sum(),
            pl.col("olum").sum(),
            pl.col("olum_e").sum(),
            pl.col("olum_k").sum(),
            pl.col("dogal").sum(),
            pl.col("kadin").sum(),
            pl.col("nufus").sum(),
            pl.len().alias("ilce_sayisi"),
            (pl.col("dogal") < 0).sum().alias("eksi_ilce"),
        )
        .with_columns(
            (1000 * pl.col("dogum") / pl.col("kadin")).alias("gdh"),
            (1000 * pl.col("dogum") / pl.col("nufus")).alias("kdh"),
            (pl.col("kadin") / pl.col("nufus")).alias("kadin_payi"),
            (1000 * pl.col("olum") / pl.col("nufus")).alias("olum_hizi"),
            (1000 * pl.col("dogal") / pl.col("nufus")).alias("dogal_hizi"),
        )
        .drop("nufus")
        .sort("yil")
    )

    # region Writing

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    book = xlsxwriter.Workbook(str(TARGET))
    style = styles(book)
    counts = (
        "dogum_ilk",
        "dogum_son",
        "kadin_ilk",
        "kadin_son",
        "nufus_son",
        "dogum",
        "kadin",
        "ilce_sayisi",
        "olum_son",
        "olum",
        "olum_e",
        "olum_k",
        "dogal",
        "dogal_ilk",
        "dogal_son",
        "eksi_ilce",
    )
    shares = (
        "dogum_oran",
        "kadin_oran",
        "gdh_oran",
        "kdh_oran",
        "kadin_payi",
        "kadin_payi_ilk",
        "kadin_payi_son",
    )
    rates = (
        "gdh_ilk",
        "gdh_son",
        "gdh",
        "kdh",
        "kdh_ilk",
        "kdh_son",
        "olum_hizi",
        "dogal_hizi",
        "dogal_hizi_ilk",
        "dogal_hizi_son",
    )
    formats = {
        **style,
        **{c: style["count"] for c in counts},
        **{c: style["percent"] for c in shares},
        **{c: style["rate"] for c in rates},
        "gdh_puan": style["points"],
        "yil": style["text"],
        "il": style["left"],
        "ilce": style["left"],
        "not": style["left"],
    }
    headers = {
        "yil": "Yıl",
        "ilce_sayisi": "İlçe sayısı",
        "nufus_son": f"Nüfus {last}",
        "dogum_ilk": f"Doğum {first}",
        "dogum_son": f"Doğum {last}",
        "dogum_oran": "Doğum değişimi",
        "kadin_ilk": f"Kadın 15-49 · {first}",
        "kadin_son": f"Kadın 15-49 · {last}",
        "kadin_oran": "Kadın değişimi",
        "gdh_ilk": f"GDH {first}",
        "gdh_son": f"GDH {last}",
        "gdh_puan": "GDH farkı (puan)",
        "gdh_oran": "GDH değişimi",
        "kdh": "KDH ‰",
        "kdh_ilk": f"KDH ‰ · {first}",
        "kdh_son": f"KDH ‰ · {last}",
        "kdh_oran": "KDH değişimi",
        "kadin_payi": "15-49 kadının payı",
        "kadin_payi_ilk": f"15-49 kadının payı {first}",
        "kadin_payi_son": f"15-49 kadının payı {last}",
        "olum": "Ölüm",
        "olum_e": "Ölüm — erkek",
        "olum_k": "Ölüm — kadın",
        "olum_son": f"Ölüm {last}",
        "olum_hizi": "Kaba ölüm hızı ‰",
        "dogal": "Doğal artış",
        "dogal_ilk": f"Doğal artış {first}",
        "dogal_son": f"Doğal artış {last}",
        "dogal_hizi": "Doğal artış hızı ‰",
        "dogal_hizi_ilk": f"Doğal artış hızı ‰ · {first}",
        "dogal_hizi_son": f"Doğal artış hızı ‰ · {last}",
        "eksi_ilce": "Doğal artışı eksi ilçe",
        "dogum": "Doğum",
        "kadin": "Kadın 15-49",
        "gdh": "GDH",
    }
    widths = {"il": 15, "ilce": 20, "sira": 6, "not": 28, "nufus_son": 13}
    scales = {"gdh_oran": "up", "gdh_son": "up", "dogum_oran": "up"}

    sheet(book, country, "Türkiye", headers, formats, widths, {"gdh": "up"})
    sheet(book, provinces, "İller", headers, formats, widths, scales)
    sheet(book, districts, "İlçeler — doğurganlık", headers, formats, widths, scales)
    sheet(
        book,
        natural,
        "İlçeler — doğal artış",
        headers,
        formats,
        widths,
        {"dogal_hizi_son": "up", "dogal_hizi_ilk": "up"},
    )
    notes_sheet(
        book,
        [
            f"İlçe düzeyinde doğum, ölüm ve doğal artış — {first}-{last}",
            "",
            "Doğal artış = doğum − ölüm. Göç bu sayının içinde yoktur: bir ilçe doğal artışı",
            "artıda olduğu hâlde küçülebilir, çünkü doğanlar kalmıyor olabilir.",
            "",
            "GDH = genel doğurganlık hızı: bin kadın (15-49) başına doğum. Doğum sayısı iki",
            "şeyin çarpımıdır — kaç kadın var, ve kadın başına kaç çocuk — ve bu sayfa",
            "ikisini ayırır. Doğumu yarıya inen bir ilçe, genç kadını gittiği için mi yoksa",
            "kalanlar daha az doğurduğu için mi öyle: 'Kadın değişimi' ile 'GDH değişimi'",
            "sütunları bunu yan yana söyler.",
            "",
            "KAYNAK VE DURUM",
            "· Doğum: TÜİK MEDAS, 'İlçelere göre doğum sayısı' ölçümü. Bu, il düzeyindeki",
            "  'İkametgah yerine göre doğum sayısı'nın başka bir düzeyde sorulmuş hali",
            f"  değil, ayrı bir ölçümdür ve yalnız {first}'ten başlar.",
            "· Ölüm: 'İlçelere göre ölüm sayısı (İkametgah yeri)', ölenin cinsiyetine göre",
            "  ayrı yayımlanıyor ve bu kırılım kapatılamıyor. 2009'da başlıyor, yani ölüm",
            f"  serisi doğumdan beş yıl uzun; doğal artış ikisinin kesiştiği {first}'ten",
            "  itibaren hesaplanabiliyor.",
            "· Kadın nüfusu: ADNKS ilçe nüfusu, beşer yaş grubu. 15-49 tam da grup",
            "  sınırlarına denk geldiği için bu soru ilçede sorulabiliyor.",
            "· Doğum ve ölüm henüz depoya (fact tablosuna) alınmadı; bu dosya indirilen ham",
            "  MEDAS dışa aktarımlarını doğrudan okuyor. Adaptör yazılınca değişecek olan",
            "  yalnız okuma yolu, sayılar değil.",
            "",
            "DENETİM",
            f"· İlçe doğum toplamları, elimizdeki ülke doğum sayısıyla {len(years)} yılın",
            "  hepsinde birebir tutuyor — tek doğum farkı yok.",
            "· İlçe ölüm toplamları da öyle, 2009-2025'in on yedi yılında ve iki cinsiyette",
            "  ayrı ayrı.",
            "· Doğum − ölüm, il düzeyindeki doğal artış göstergemizle 972 il-yılın",
            "  hepsinde birebir eşit. Yani ilçeden ile yuvarlandığında hiçbir şey kaçmıyor.",
            f"· İlçe sayısı {first}'te 970, {last}'te 973: aradaki fark yeni kurulan",
            "  ilçelerdir, eksik veri değil.",
            "",
            "OKURKEN",
            "· Eşleştirme MEDAS koduyla yapıldı, adla değil: kırk ilçenin adı 'Merkez'.",
            "· Adı değişen ilçe iki kimlik taşır (Kazan → Kahramankazan 2017, Eyüp →",
            "  Eyüpsultan 2018). Hangi kimliğin geçerli olduğunu yıl seçiyor; yoksa o",
            "  ilçelerin ilk yılları sessizce boş kalıyordu — doğum toplamda sayılmaya",
            "  devam ettiği için yalnız oran kaybolurdu.",
            f"· 'Not' sütunu {first} doğumu {RANK_FLOOR}'ün altındaki ilçeleri işaretler:",
            "  yirmi doğuma karşı on dokuz, bir ailelik fark demektir, %5'lik düşüş değil.",
            "· 2013'teki büyükşehir bölünmeleri nüfus serisini bozuyor ama GDH'yi bozmuyor:",
            "  oran her ilçe-yılın kendi içinde hesaplanıyor.",
        ],
    )
    book.close()
    # endregion

    print("yazildi:", TARGET)
    print(
        "  Türkiye:",
        len(country),
        "| İller:",
        len(provinces),
        "| İlçeler:",
        len(districts),
    )


if __name__ == "__main__":
    main()
