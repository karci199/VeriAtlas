"""One spreadsheet of the vital events by province: mortality by age, the age structure
that produces it, and the marriage and marital-status series that sit next to it.

Why a file and not a screen: every sheet here is "eighty-one provinces, two years, and
the change between them", sorted by the change. The explorer answers that one province at
a time and draws it well; ranking all of them against each other is a spreadsheet.

Everything is at **province level and runs as far back as the source goes** — which is
not one span but four, and the sheets say which:

* Deaths by age and the rates from them: **2009-2025**
* Population and its age structure: **2007-2025**
* Marriage and divorce counts: **2001-2025**, the crude rates only from 2007, since the
  denominator does not exist before that
* Marital status: **2008-2025**

The sheets:

* **Özet** — the ten highest and lowest of each thing the other sheets rank.
* **Ölüm hızı 65+**, **0-14**, **15-64** — a row per province, every year across, and
  the change at the end. Both sexes together, weighted: deaths summed and population
  summed before the division, never the average of the two rates.
* **Ölüm hızı bantlar** — the full published banding for the first and last year, for
  the reader who wants to see where in the age range a province differs.
* **Yaş yapısı** — the three broad groups as counts and as shares, first year against
  last, the change in points and in percent. The 65+ *share* rising while the 65+ death
  *rate* falls is the whole story of these two decades and it takes both sheets to see.
* **Evlenme boşanma** — counts and crude rates, and the change.
* **Medeni durum** — the distribution of the 15+ population, first year against last.
* **Notlar** — what these numbers do and do not say, inside the file.

Run:  uv run python scripts/build_vital_excel.py
"""

from __future__ import annotations

import sys

import polars as pl
import xlsxwriter

sys.path.insert(0, "src")

from veriatlas.areas import load_areas
from veriatlas.config import OUTPUT, PUBLIC

TARGET = OUTPUT / "olum" / "olum-evlenme-yas.xlsx"

#: The broad groups, in the order a reader expects to see them.
BROAD = ("0-14", "15-64", "65+")

#: Marital status ids to the Turkish the sheet prints. `unknown` is in the source for the
#: early years and disappears later; kept, because a distribution that quietly drops a
#: category adds up to less than a hundred percent and does not say why.
MARITAL = {
    "never_married": "hic_evlenmedi",
    "married": "evli",
    "divorced": "bosandi",
    "widowed": "esi_oldu",
    "unknown": "bilinmeyen",
}


def facts() -> pl.DataFrame:
    """The warehouse export, provinces only, with year and breakdowns split out."""
    return (
        pl.read_parquet(PUBLIC / "fact.parquet")
        .filter(pl.col("area_level") == "province")
        .with_columns(
            pl.col("period_start").dt.year().alias("yil"),
            pl.col("dims").str.extract(r"age=([^;]+)").alias("yas"),
            pl.col("dims").str.extract(r"sex=([^;]+)").alias("cinsiyet"),
            pl.col("dims").str.extract(r"marital=([^;]+)").alias("medeni"),
        )
    )


def names() -> pl.DataFrame:
    return load_areas().select("area_id", pl.col("name_tr").alias("il"))


def broad_population(fact: pl.DataFrame) -> pl.DataFrame:
    """Province-year population in the three broad groups, from the single years.

    Summed from single years rather than read off a published grouping, for the reason
    the whole project keeps saying: a coarse reading of a fine breakdown is an exact sum
    of it, and the fine breakdown is what we hold. The closing `75+` band is folded into
    65+ with the rest.
    """
    people = fact.filter(pl.col("indicator_id") == "population").filter(
        pl.col("yas").str.contains(r"^\d+$") | (pl.col("yas") == "75+")
    )
    year = pl.col("yas").cast(pl.Int32, strict=False)
    return (
        people.with_columns(
            pl.when(pl.col("yas") == "75+")
            .then(pl.lit("65+"))
            .when(year < 15)
            .then(pl.lit("0-14"))
            .when(year < 65)
            .then(pl.lit("15-64"))
            .otherwise(pl.lit("65+"))
            .alias("grup")
        )
        .group_by("area_id", "yil", "grup")
        .agg(pl.col("value").sum().alias("kisi"))
    )


def totals(fact: pl.DataFrame) -> pl.DataFrame:
    """Total population per province-year — the denominator of the crude rates."""
    return (
        fact.filter(pl.col("indicator_id") == "population")
        .filter(pl.col("yas").str.contains(r"^\d+$") | (pl.col("yas") == "75+"))
        .group_by("area_id", "yil")
        .agg(pl.col("value").sum().alias("nufus"))
    )


def death_rate_both_sexes(fact: pl.DataFrame) -> pl.DataFrame:
    """The broad-group death rate for men and women together.

    Rebuilt from the counts rather than averaged from the two stored rates. Men and women
    are not present in equal numbers in a band — at 75+ they are nowhere near it — so the
    midpoint of the two rates is not the rate of the two together.
    """
    deaths = (
        fact.filter(pl.col("indicator_id") == "deaths_by_age")
        .filter(pl.col("yas") != "unknown")
        .with_columns(
            pl.when(pl.col("yas").is_in(["0", "1-4", "5-9", "10-14"]))
            .then(pl.lit("0-14"))
            .when(pl.col("yas").is_in(["65-69", "70-74", "75+"]))
            .then(pl.lit("65+"))
            .otherwise(pl.lit("15-64"))
            .alias("grup")
        )
        .group_by("area_id", "yil", "grup")
        .agg(pl.col("value").sum().alias("olum"))
    )
    return (
        deaths.join(broad_population(fact), on=["area_id", "yil", "grup"], how="inner")
        .filter(pl.col("kisi") > 0)
        .with_columns((pl.col("olum") / pl.col("kisi") * 1000).alias("hiz"))
    )


def wide_years(
    frame: pl.DataFrame, value: str, name: pl.DataFrame, places: int
) -> pl.DataFrame:
    """A province per row, a year per column, with the change at the end.

    Two changes, not one, and they answer different questions: the difference is in the
    unit itself (‰, points) and the percent is relative to where the province started.
    A province falling from 60‰ to 50‰ and one falling from 12‰ to 10‰ have the same
    percent change and a five-fold difference in lives.
    """
    years = sorted(frame["yil"].unique().to_list())
    first, last = years[0], years[-1]
    table = (
        frame.pivot(values=value, index="area_id", on="yil")
        .join(name, on="area_id", how="left")
        .with_columns(
            (pl.col(str(last)) - pl.col(str(first))).round(places).alias("fark"),
            pl.when(pl.col(str(first)) != 0)
            .then(pl.col(str(last)) / pl.col(str(first)) - 1)
            .alias("degisim"),
        )
        .with_columns([pl.col(str(y)).round(places) for y in years])
    )
    return table.select(["il", *[str(y) for y in years], "fark", "degisim"]).sort(
        str(last), descending=True
    )


def main() -> None:
    fact = facts()
    name = names()

    # region Mortality

    rate = death_rate_both_sexes(fact)
    by_group = {
        group: wide_years(rate.filter(pl.col("grup") == group), "hiz", name, 2)
        for group in BROAD
    }

    # The published bands, first year and last, so the reader can see *where* in the age
    # range two provinces differ rather than only that they do.
    band = (
        fact.filter(pl.col("indicator_id") == "death_rate_by_age")
        .join(name, on="area_id", how="left")
        .select("il", "yil", "yas", "cinsiyet", pl.col("value").round(2).alias("hiz"))
    )
    band_years = sorted(band["yil"].unique().to_list())
    bands = (
        band.filter(pl.col("yil").is_in([band_years[0], band_years[-1]]))
        .pivot(values="hiz", index=["il", "yas", "cinsiyet"], on="yil")
        .with_columns(
            (pl.col(str(band_years[-1])) - pl.col(str(band_years[0])))
            .round(2)
            .alias("fark")
        )
        .sort("il", "cinsiyet", "yas")
    )

    # endregion

    # region Age structure

    people = broad_population(fact)
    share = (
        people.join(
            people.group_by("area_id", "yil").agg(pl.col("kisi").sum().alias("toplam")),
            on=["area_id", "yil"],
            how="left",
        )
        .with_columns((pl.col("kisi") / pl.col("toplam")).alias("pay"))
        .join(name, on="area_id", how="left")
    )
    years = sorted(share["yil"].unique().to_list())
    first, last = years[0], years[-1]

    structure = (
        share.filter(pl.col("yil").is_in([first, last]))
        .pivot(values=["kisi", "pay"], index=["il", "grup"], on="yil")
        .rename(
            {
                f"kisi_{first}": f"kisi_{first}",
                f"kisi_{last}": f"kisi_{last}",
                f"pay_{first}": f"pay_{first}",
                f"pay_{last}": f"pay_{last}",
            }
        )
        .with_columns(
            (pl.col(f"kisi_{last}") - pl.col(f"kisi_{first}")).alias("kisi_fark"),
            (pl.col(f"kisi_{last}") / pl.col(f"kisi_{first}") - 1).alias(
                "kisi_degisim"
            ),
            # In points, not in percent: 8% to 12% is four points and a 50% rise, and
            # calling either one "the change" without saying which is how a share gets
            # misread. Both columns are here and both are labelled.
            (pl.col(f"pay_{last}") - pl.col(f"pay_{first}")).alias("pay_fark"),
        )
        .sort("grup", "pay_" + str(last), descending=[False, True])
    )

    # endregion

    # region Marriage, divorce, marital status

    def counted(indicator_id: str, column: str) -> pl.DataFrame:
        return (
            fact.filter(pl.col("indicator_id") == indicator_id)
            .group_by("area_id", "yil")
            .agg(pl.col("value").sum().alias(column))
        )

    base = totals(fact)
    unions = (
        counted("marriages", "evlenme")
        .join(
            counted("divorces", "bosanma"),
            on=["area_id", "yil"],
            how="full",
            coalesce=True,
        )
        # Left join on the population: the counts start in 2001 and the register in 2007,
        # and those early years are real observations. They keep their counts and get no
        # rate, rather than being dropped for want of a denominator.
        .join(base, on=["area_id", "yil"], how="left")
        .with_columns(
            (pl.col("evlenme") / pl.col("nufus") * 1000).round(2).alias("evlenme_hizi"),
            (pl.col("bosanma") / pl.col("nufus") * 1000).round(2).alias("bosanma_hizi"),
        )
        .join(name, on="area_id", how="left")
    )
    union_years = sorted(unions["yil"].unique().to_list())
    unions_wide = (
        unions.filter(pl.col("yil").is_in([union_years[0], union_years[-1]]))
        .pivot(
            values=["evlenme", "bosanma", "evlenme_hizi", "bosanma_hizi"],
            index="il",
            on="yil",
        )
        .sort("il")
    )

    marital = (
        fact.filter(pl.col("indicator_id") == "marital_status")
        .group_by("area_id", "yil", "medeni")
        .agg(pl.col("value").sum().alias("kisi"))
    )
    marital = (
        marital.join(
            marital.group_by("area_id", "yil").agg(
                pl.col("kisi").sum().alias("toplam")
            ),
            on=["area_id", "yil"],
            how="left",
        )
        .with_columns(
            (pl.col("kisi") / pl.col("toplam")).alias("pay"),
            pl.col("medeni").replace_strict(MARITAL, default="bilinmeyen"),
        )
        .join(name, on="area_id", how="left")
    )
    marital_years = sorted(marital["yil"].unique().to_list())
    m_first, m_last = marital_years[0], marital_years[-1]
    marital_wide = (
        marital.filter(pl.col("yil").is_in([m_first, m_last]))
        .pivot(values="pay", index=["il", "medeni"], on="yil")
        .with_columns((pl.col(str(m_last)) - pl.col(str(m_first))).alias("pay_fark"))
        .sort("medeni", str(m_last), descending=[False, True])
    )

    # endregion

    # region Summary

    def top(frame, column, label, rising=True, take=10, key="il", scale=1):
        """Ten provinces, ranked, as one block of the summary sheet.

        `scale` is there because this sheet puts measures of different kinds in a single
        column: a rate is already per thousand, a share is a fraction of one. Left alone,
        "65+ payı en yüksek il" printed 0,20 next to a death rate of 45,07 — the same
        column saying twenty percent and forty-five per thousand in two notations, one of
        which reads as nothing at all. The share is scaled to points here and the label
        says so; the alternative, a second column, would be empty in most rows.
        """
        ordered = frame.drop_nulls(column).sort(column, descending=rising).head(take)
        return pl.DataFrame(
            {
                "olcut": [label] * len(ordered),
                "sira": list(range(1, len(ordered) + 1)),
                "il": ordered[key].to_list(),
                "deger": [value * scale for value in ordered[column].to_list()],
            }
        )

    old = by_group["65+"]
    child = by_group["0-14"]
    work = by_group["15-64"]
    last_death = str(max(rate["yil"].unique().to_list()))
    old_share = structure.filter(pl.col("grup") == "65+")

    summary = pl.concat(
        [
            top(old, last_death, f"65+ ölüm hızı en yüksek il ({last_death}, ‰)"),
            top(old, last_death, f"65+ ölüm hızı en düşük il ({last_death}, ‰)", False),
            top(old, "fark", "65+ ölüm hızı en çok düşen il (‰ fark)", False),
            # "En az düşen", not "en çok artan": no province rose. A ranking labelled
            # "artan" whose every value is negative reads as a rise to anyone
            # skimming the column.
            top(old, "fark", "65+ ölüm hızı en az düşen il (‰ fark)"),
            top(child, last_death, f"0-14 ölüm hızı en yüksek il ({last_death}, ‰)"),
            top(
                child, "degisim", "0-14 ölüm hızı en çok düşen il (%)", False, scale=100
            ),
            top(work, last_death, f"15-64 ölüm hızı en yüksek il ({last_death}, ‰)"),
            top(
                old_share,
                f"pay_{last}",
                f"65+ payı en yüksek il ({last}, %)",
                scale=100,
            ),
            top(
                old_share,
                f"pay_{last}",
                f"65+ payı en düşük il ({last}, %)",
                False,
                scale=100,
            ),
            top(old_share, "pay_fark", "65+ payı en çok artan il (puan)", scale=100),
            top(
                structure.filter(pl.col("grup") == "0-14"),
                "pay_fark",
                "0-14 payı en çok düşen il (puan)",
                False,
                scale=100,
            ),
        ]
    )

    # endregion

    # region Writing

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    book = xlsxwriter.Workbook(str(TARGET))

    head = book.add_format(
        {
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,
            "bg_color": "#1F3864",
            "font_color": "#FFFFFF",
            "border": 1,
        }
    )
    left = book.add_format({"align": "left", "valign": "vcenter"})
    middle = book.add_format({"align": "center", "valign": "vcenter"})
    count = book.add_format(
        {"num_format": "#,##0", "align": "center", "valign": "vcenter"}
    )
    rate_fmt = book.add_format(
        {"num_format": "0.00", "align": "center", "valign": "vcenter"}
    )
    percent = book.add_format(
        {"num_format": "0.0%", "align": "center", "valign": "vcenter"}
    )

    def write(frame: pl.DataFrame, title: str, kinds: dict) -> None:
        page = book.add_worksheet(title)
        page.freeze_panes(1, 1)
        page.set_row(0, 30)
        for index, column in enumerate(frame.columns):
            style = kinds.get(column, middle)
            page.write(0, index, column, head)
            page.set_column(index, index, 18 if index == 0 else 11, style)
            for row, value in enumerate(frame[column].to_list(), start=1):
                if value is None:
                    continue
                page.write(row, index, value, style)
        page.autofilter(0, 0, len(frame), len(frame.columns) - 1)

    rates_kind = {"il": left, "degisim": percent}
    rates_kind.update(
        {column: rate_fmt for column in by_group["65+"].columns if column != "il"}
    )
    rates_kind["degisim"] = percent

    write(
        summary,
        "Özet",
        {"olcut": left, "il": left, "sira": middle, "deger": rate_fmt},
    )
    for group in BROAD:
        write(by_group[group], "Ölüm hızı " + group, rates_kind)
    write(
        bands,
        "Ölüm hızı bantlar",
        {
            "il": left,
            "yas": middle,
            "cinsiyet": middle,
            str(band_years[0]): rate_fmt,
            str(band_years[-1]): rate_fmt,
            "fark": rate_fmt,
        },
    )
    write(
        structure,
        "Yaş yapısı",
        {
            "il": left,
            "grup": middle,
            f"kisi_{first}": count,
            f"kisi_{last}": count,
            "kisi_fark": count,
            "kisi_degisim": percent,
            f"pay_{first}": percent,
            f"pay_{last}": percent,
            "pay_fark": percent,
        },
    )
    write(
        unions_wide,
        "Evlenme boşanma",
        {
            "il": left,
            **{
                column: (rate_fmt if "hizi" in column else count)
                for column in unions_wide.columns
                if column != "il"
            },
        },
    )
    write(
        marital_wide,
        "Medeni durum",
        {
            "il": left,
            "medeni": middle,
            str(m_first): percent,
            str(m_last): percent,
            "pay_fark": percent,
        },
    )

    notes = book.add_worksheet("Notlar")
    notes.set_column(0, 0, 108, book.add_format({"text_wrap": True, "valign": "top"}))
    lines = [
        "VeriAtlas — ölüm, yaş yapısı, evlenme ve medeni durum (il düzeyi)",
        "",
        "Kaynak: TÜİK MEDAS. Çekim: 2026-08. Ölüm ve doğum ikametgah yerine göredir.",
        "",
        "YILLAR — her ölçünün kendi başlangıcı var, en geriye gidebildiği yer:",
        f"· Yaş ve cinsiyete göre ölüm: {band_years[0]}-{band_years[-1]}",
        f"· Nüfus ve yaş yapısı: {first}-{last}",
        (
            f"· Evlenme ve boşanma sayısı: {union_years[0]}-{union_years[-1]}"
            " (hız yalnız nüfusun olduğu yıllarda)"
        ),
        f"· Medeni durum: {m_first}-{m_last}",
        "",
        "ÖLÜM HIZI NEDİR, NE DEĞİLDİR",
        "· Buradaki hız, yaş grubundaki ölüm sayısının AYNI yaş grubunun bin kişisine",
        "  oranıdır. Kaba ölüm hızı değildir: kaba hız herkesi paydaya koyar, o yüzden",
        "  yaşlı bir ilde ölümlülük artmadan yüksek çıkar.",
        "· İki cinsiyet birlikte verilirken iki hızın ortalaması alınmadı; ölümler ve",
        "  nüfuslar ayrı ayrı toplanıp en sonda bölündü. 75+ bandında kadın ve erkek",
        "  sayısı eşit olmadığı için ortalama yanlış olurdu.",
        "· Payda yıl sonu (31 Aralık) ADNKS nüfusudur — TÜİK'in kaba hızlarda kullandığı",
        "  paydanın aynısı. Yıl ortası nüfus kullanılsaydı değerler biraz değişirdi.",
        "· Yaşı bilinmeyen ölümler hızın dışındadır: karşılığı bir nüfus yok. 2009'da",
        "  Türkiye genelinde 963 ölüm, 2014'ten sonra sıfır.",
        "",
        "OKURKEN DİKKAT",
        "· 65+ payı yükselirken 65+ ölüm hızının düşmesi çelişki değildir: nüfus yaşlanıyor,",
        "  yaşlıların ölüm riski ise azalıyor. İki sayfa birlikte okunmalı.",
        "· 2020 ve 2021 pandemi yıllarıdır; ölüm hızlarındaki sıçrama gerçektir, eğilim",
        "  değildir.",
        "· 2023'te deprem illerinde ölüm sayıları olağandışıdır. Kahramanmaraş, Hatay,",
        "  Adıyaman ve çevresinde o yılın satırı bir felaketin kaydıdır.",
        "· Küçük illerde çocuk ölümü yılda birkaç kişidir; oran bu yüzden yıldan yıla",
        "  sıçrar. 0-14 sayfasında tek bir yıl değil, eğilim okunmalı.",
        "· Evlenme ve boşanma OLAYIN YERİNE göre sayılır (nikâhın kıyıldığı, kararın",
        "  verildiği il), ölüm ve doğum ise İKAMETGAHA göre. Turistik ilçelerde bu ikisi",
        "  ayrışır.",
        "· Bir yılın boşanma sayısı o yılın evlenme sayısına bölünmemeli: boşananlar başka",
        "  yıllarda evlenmiş çiftlerdir.",
        "· Medeni durum payları 15 yaş üstü nüfusundadır ve 'bilinmeyen' kategorisi ilk",
        "  yıllarda doludur, sonra kayboluyor — silinmedi, çünkü silinseydi paylar",
        "  toplamı yüzü bulmaz ve sayfa bunu söylemezdi.",
        "",
        "SÜTUNLAR",
        "· 'fark' = son yıl − ilk yıl, göstergenin kendi biriminde (‰ ya da puan).",
        "· 'degisim' = son yıl / ilk yıl − 1, yani orana göre değişim.",
        "· İkisi ayrı sorudur: 60‰'den 50‰'ye düşen il ile 12‰'den 10‰'ye düşen ilin",
        "  yüzde değişimi aynıdır, kaybettiği insan sayısı beş katı farklıdır.",
    ]
    for row, line in enumerate(lines):
        notes.write(row, 0, line)

    book.close()
    # endregion

    print("yazildi:", TARGET)
    print(
        "  Ölüm hızı:",
        len(by_group["65+"]),
        "il ×",
        len(band_years),
        "yıl | Bantlar:",
        len(bands),
        "| Yaş yapısı:",
        len(structure),
        "| Evlenme:",
        len(unions_wide),
        "| Medeni durum:",
        len(marital_wide),
    )


if __name__ == "__main__":
    main()
