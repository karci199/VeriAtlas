"""One spreadsheet of every settlement in Türkiye: neighbourhoods, villages, and the
urban/rural split that falls out of having both.

Why a file and not a screen: 32.681 rows sorted by "which neighbourhood has the most
adults" is a spreadsheet question. The explorer answers "how does this place compare to
that one over time"; it would need a menu of 32.681 entries to answer this one, and the
menu would be worse than the question.

The sheets:

* **Mahalleler** — a row per neighbourhood. Columns are grouped by *measure*, not by
  year: first year, last year and the growth stand next to each other, three times over
  (total, children, adults). Reading across a row then answers one question at a time. A
  neighbourhood whose population grew 40% while its children fell is a different place
  from one where both grew; one column cannot say that, three can.
* **Köyler** — a row per village, total only. TÜİK publishes the 18+ split for
  municipality neighbourhoods and not for villages: tick the age breakdown in MEDAS and
  `Köy` disappears from the level box. So the village sheet compares populations, never
  ages, and says so.
* **İlçeler**, **İller** — the same numbers rolled up, plus how many settlements of each
  kind sit inside and how big the typical one is. A province of 300 small villages and a
  province of 30 large ones can share a rural population; the counts separate them.
* **Özet** — the ten highest and lowest of what people actually ask for, each carrying
  the numbers it was ranked on. A rank with no quantity next to it is a claim without
  evidence.
* **Yıllar** — every settlement's total, year by year, wide.
* **Notlar** — what the numbers do and do not cover, in Turkish, inside the file. A
  spreadsheet travels away from whoever made it; the caveats have to travel with it.

Percentages are written as plain numbers with the unit in the header — `65,4` under
"Yetişkin payı (%)", not `65,4%` in the cell. Excel number formats are written in US
convention and rendered in the reader's locale, and a format of `0,00%` therefore does
not mean two decimals: the comma is a thousands separator, which is where `065,4%` and
`-002%` came from. Keeping the unit in the header sidesteps the whole class of bug and
leaves the cell a number that sorts, averages and charts.

The urban/rural split only exists for **51 provinces**. Law 6360 turned every village in
the 30 metropolitan provinces into a neighbourhood in 2014, so there they are all "kent"
by definition and the ratio would be 100% everywhere — true and useless. Where villages
survive, the split is the real thing: the belediye population against the village
population, both counted the same way.

Run:  uv run python scripts/build_settlement_excel.py
"""

from __future__ import annotations

import sys

import polars as pl
import xlsxwriter

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC

TARGET = PUBLIC.parent / "cikti" / "mahalle-nufus.xlsx"
DATA = PUBLIC.parent / "src" / "veriatlas" / "data"

CHILD = "0-17"
ADULT = "18+"

#: Columns holding a proportion. They are multiplied by 100 on the way out and their
#: header gains "(%)" — the unit lives in the header, never in the cell.
SHARE = {"yetiskin_payi", "kapsam", "kir_payi", "degisim", "deger_yuzde"}


def is_share(column: str) -> bool:
    return column in SHARE or column.endswith("_artis")


def villages() -> pl.DataFrame:
    """Every village-year, from the warehouse and the village registry.

    Read here rather than parsed here. The exports have their own trap — the bucak stops
    being written in 2017, so a village's label loses a path segment mid-series — and that
    belongs in the adapter with the rest of the reading, not in a second copy that can
    drift from it. Since `tuik_villages` loads them, this script does what everything else
    does: asks the fact table.
    """
    fact = pl.read_parquet(PUBLIC / "fact.parquet")
    rows = (
        fact.filter(
            (pl.col("indicator_id") == "population")
            & (pl.col("area_level") == "village")
        )
        .with_columns(pl.col("period_start").dt.year().alias("yil"))
        .select("area_id", "yil", pl.col("value").alias("nufus"))
    )
    if rows.is_empty():
        raise ValueError("depoda koy satiri yok — once load.py tuik_villages")

    registry = pl.read_csv(DATA / "areas_tr_villages.csv").select(
        "area_id",
        pl.col("name_tr").alias("koy"),
        pl.col("bucak"),
        pl.col("parent_id"),
        pl.col("medas_code").alias("kod"),
    )
    districts = pl.read_csv(DATA / "areas_tr_districts.csv").select(
        "area_id", pl.col("name_tr").alias("ilce")
    )
    provinces = pl.read_csv(DATA / "areas_tr.csv").select(
        "area_id", pl.col("name_tr").alias("il")
    )
    return (
        rows.join(registry, on="area_id")
        .join(districts, left_on="parent_id", right_on="area_id", how="left")
        .with_columns(pl.col("area_id").str.slice(0, 5).alias("il_id"))
        .join(provinces, left_on="il_id", right_on="area_id", how="left")
    )


def neighbourhoods() -> pl.DataFrame:
    """Every neighbourhood-year, wide: total, child, adult."""
    fact = pl.read_parquet(PUBLIC / "fact.parquet")
    rows = (
        fact.filter(
            (pl.col("indicator_id") == "population")
            & (pl.col("area_level") == "neighbourhood")
        )
        .with_columns(
            pl.col("period_start").dt.year().alias("yil"),
            pl.col("dims").str.extract(r"age=([^;]*)").alias("yas"),
        )
        .group_by("area_id", "yil", "yas")
        .agg(pl.col("value").sum().alias("kisi"))
    )
    wide = rows.pivot(values="kisi", index=["area_id", "yil"], on="yas").with_columns(
        (pl.col(CHILD).fill_null(0) + pl.col(ADULT).fill_null(0)).alias("toplam"),
        # TÜİK suppresses small cells. Summing what was published gives a total that is
        # short by the hidden half, and the adult share then reads 100% — a settlement
        # with no children, which is not what the source said. The flag records whether
        # both halves arrived, so the share can refuse to answer where they did not.
        (pl.col(CHILD).is_not_null() & pl.col(ADULT).is_not_null()).alias("tam"),
    )
    return wide.rename({CHILD: "cocuk", ADULT: "yetiskin"})


def named(wide: pl.DataFrame) -> pl.DataFrame:
    """Attach province, district, municipality and neighbourhood names."""
    hoods = pl.read_csv(DATA / "areas_tr_neighbourhoods.csv")
    districts = pl.read_csv(DATA / "areas_tr_districts.csv").select(
        "area_id", pl.col("name_tr").alias("ilce")
    )
    provinces = pl.read_csv(DATA / "areas_tr.csv").select(
        "area_id", pl.col("name_tr").alias("il")
    )
    return (
        wide.join(
            hoods.select(
                "area_id",
                pl.col("name_tr").alias("mahalle"),
                pl.col("municipality").alias("belediye"),
                "parent_id",
                "first_seen",
                "last_seen",
            ),
            on="area_id",
            how="left",
        )
        .join(districts, left_on="parent_id", right_on="area_id", how="left")
        .with_columns(
            pl.col("area_id").str.slice(0, 5).alias("il_id"),
            pl.col("parent_id").alias("ilce_id"),
        )
        .join(provinces, left_on="il_id", right_on="area_id", how="left")
    )


def area_totals(level: str, year: int) -> pl.DataFrame:
    """Published population per area at a level, for the coverage column."""
    wanted = {"il": "province", "ilce": "district"}[level]
    fact = pl.read_parquet(PUBLIC / "fact.parquet")
    return (
        fact.filter(
            (pl.col("indicator_id") == "population")
            & (pl.col("area_level") == wanted)
            & (pl.col("period_start").dt.year() == year)
        )
        .group_by("area_id")
        .agg(pl.col("value").sum().alias("nufus"))
    )


def growth(now: str, before: str, name: str) -> pl.Expr:
    """Growth from one year to another, as a proportion, or nothing when there is no base.

    Nothing, not zero: a settlement that appears after the first year has no growth to
    report, and printing 0% would say it stood still.
    """
    return (
        pl.when(pl.col(before) > 0)
        .then(pl.col(now) / pl.col(before) - 1)
        .otherwise(None)
        .alias(name)
    )


def to_percent(frame: pl.DataFrame) -> pl.DataFrame:
    """Proportions to percentage points, once, at the edge.

    Everything upstream works in proportions because that is what divides and compares.
    The multiplication happens here and only here, so no intermediate frame carries a
    number whose unit depends on where it came from.
    """
    shares = [c for c in frame.columns if is_share(c)]
    if not shares:
        return frame
    return frame.with_columns([(pl.col(c) * 100).round(2).alias(c) for c in shares])


#: Column name to the words shown in the header. Capitalised, spaced, and said in Turkish
#: — the sheet is read by people, and `yetiskin_payi` is not a phrase in any language.
HEADERS = {
    "il": "İl",
    "ilce": "İlçe",
    "bucak": "Bucak",
    "belediye": "Belediye",
    "mahalle": "Mahalle",
    "koy": "Köy",
    "yer": "Yerleşim",
    "kimlik": "Kimlik",
    "kod": "MEDAS kodu",
    "mahalle_sayisi": "Mahalle sayısı",
    "koy_sayisi": "Köy sayısı",
    "belediye_sayisi": "Belediye sayısı",
    "yerlesim_sayisi": "Yerleşim sayısı",
    "mahalle_ortalama": "Ortalama mahalle nüfusu",
    "mahalle_ortanca": "Ortanca mahalle nüfusu",
    "mahalle_en_buyuk": "En büyük mahalle",
    "mahalle_en_kucuk": "En küçük mahalle",
    "koy_ortalama": "Ortalama köy nüfusu",
    "koy_ortanca": "Ortanca köy nüfusu",
    "koy_en_buyuk": "En büyük köy",
    "yetiskin_payi": "Yetişkin payı",
    "gizli_mahalle": "Yaşı gizli mahalle",
    "kapsam": "Kapsam",
    "ilk_gorulen": "İlk görülen",
    "son_gorulen": "Son görülen",
    "kent": "Kent (belediye)",
    "kir": "Kır (köy)",
    "kir_payi": "Kır payı",
    "kent_artis": "Kent artışı",
    "kir_artis": "Kır artışı",
    "sira": "Sıra",
    "olcut": "Ölçüt",
    "baslangic": "Başlangıç",
    "bitis": "Bitiş",
    "degisim": "Değişim",
    "deger_yuzde": "Değer",
    "deger_kisi": "Değer (kişi)",
}


def header_of(column: str, first: int, last: int) -> str:
    """The words for a column, with "(%)" appended when the column is a share."""
    if column in HEADERS:
        text = HEADERS[column]
    else:
        words = {
            "toplam": "Toplam",
            "cocuk": "Çocuk (0-17)",
            "yetiskin": "Yetişkin (18+)",
            "nufus": "Nüfus",
            "gercek": "Gerçek nüfus",
            "kir": "Kır (köy)",
            "kent": "Kent (belediye)",
        }
        text = column[:1].upper() + column[1:].replace("_", " ")
        for key, word in words.items():
            if column.startswith(key + "_"):
                tail = column[len(key) + 1 :]
                if tail.isdigit():
                    text = word + " " + tail
                    break
                if tail == "artis":
                    text = word + " artışı"
                    break
    return text + " (%)" if is_share(column) else text


def sheet(book, frame, title, formats, first, last, widths=None) -> None:
    """One sheet: frozen header, filter on, every cell centred but the names."""
    page = book.add_worksheet(title)
    page.freeze_panes(1, 0)
    page.set_row(0, 34)

    widths = widths or {}
    for index, column in enumerate(frame.columns):
        page.write(0, index, header_of(column, first, last), formats["head"])
        page.set_column(
            index,
            index,
            widths.get(column, 16),
            formats.get(column, formats["text"]),
        )
    page.autofilter(0, 0, len(frame), len(frame.columns) - 1)

    for index, column in enumerate(frame.columns):
        style = formats.get(column, formats["text"])
        for row, value in enumerate(frame[column].to_list(), start=1):
            if value is None:
                continue
            page.write(row, index, value, style)


def main() -> None:
    wide = named(neighbourhoods())
    years = sorted(wide["yil"].unique().to_list())
    first, last = years[0], years[-1]

    koy = villages()
    koy_years = sorted(koy["yil"].unique().to_list())
    koy_first, koy_last = koy_years[0], koy_years[-1]

    t_first, t_last = "toplam_" + str(first), "toplam_" + str(last)
    c_first, c_last = "cocuk_" + str(first), "cocuk_" + str(last)
    y_first, y_last = "yetiskin_" + str(first), "yetiskin_" + str(last)
    k_first, k_last = "nufus_" + str(koy_first), "nufus_" + str(koy_last)
    kir_first, kir_last = "kir_" + str(koy_first), "kir_" + str(koy_last)

    # region Neighbourhoods

    def at(year: int) -> pl.DataFrame:
        return wide.filter(pl.col("yil") == year).select(
            "area_id",
            pl.col("toplam").alias("toplam_" + str(year)),
            pl.col("cocuk").alias("cocuk_" + str(year)),
            pl.col("yetiskin").alias("yetiskin_" + str(year)),
        )

    base = (
        wide.filter(pl.col("yil") == last)
        .join(at(first), on="area_id", how="left")
        .with_columns(
            pl.when(pl.col("tam"))
            .then(pl.col("yetiskin") / pl.col("toplam"))
            .otherwise(None)
            .alias("yetiskin_payi")
        )
        .rename(
            {
                "toplam": t_last,
                "cocuk": c_last,
                "yetiskin": y_last,
                "first_seen": "ilk_gorulen",
                "last_seen": "son_gorulen",
            }
        )
        .with_columns(
            growth(t_last, t_first, "toplam_artis"),
            growth(c_last, c_first, "cocuk_artis"),
            growth(y_last, y_first, "yetiskin_artis"),
        )
    )

    # Grouped by measure, not by year: total then children then adults, each as
    # before / after / growth. The question "did this place grow?" is answered by three
    # adjacent cells instead of three cells six columns apart.
    mahalleler = base.select(
        "il",
        "ilce",
        "belediye",
        "mahalle",
        t_first,
        t_last,
        "toplam_artis",
        c_first,
        c_last,
        "cocuk_artis",
        y_first,
        y_last,
        "yetiskin_artis",
        "yetiskin_payi",
        "ilk_gorulen",
        "son_gorulen",
        pl.col("area_id").alias("kimlik"),
    ).sort(t_last, descending=True)

    # endregion

    # region Villages

    def koy_at(year: int) -> pl.DataFrame:
        return koy.filter(pl.col("yil") == year).select(
            "kod", pl.col("nufus").alias("nufus_" + str(year))
        )

    koyler = (
        koy_at(koy_last)
        .join(koy_at(koy_first), on="kod", how="left")
        .join(
            koy.group_by("kod").agg(
                pl.col("il").last(),
                pl.col("ilce").last(),
                pl.col("bucak").last(),
                pl.col("koy").last(),
            ),
            on="kod",
        )
        .with_columns(growth(k_last, k_first, "nufus_artis"))
        .select("il", "ilce", "bucak", "koy", k_first, k_last, "nufus_artis", "kod")
        .sort(k_last, descending=True)
    )

    # endregion

    # region Roll-ups

    def koy_stats(key: str) -> pl.DataFrame:
        """Village counts and typical sizes per district (`parent_id`) or province.

        Keyed by identity, never by name: forty-odd districts are called "Merkez" and a
        name join would pour one province's villages into another's.
        """
        now = koy.filter(pl.col("yil") == koy_last)
        then = koy.filter(pl.col("yil") == koy_first)
        return (
            now.group_by(key)
            .agg(
                pl.col("kod").n_unique().alias("koy_sayisi"),
                pl.col("nufus").sum().alias(kir_last),
                pl.col("nufus").mean().round(0).alias("koy_ortalama"),
                pl.col("nufus").median().round(0).alias("koy_ortanca"),
                pl.col("nufus").max().alias("koy_en_buyuk"),
            )
            .join(
                then.group_by(key).agg(pl.col("nufus").sum().alias(kir_first)),
                on=key,
                how="left",
            )
            .with_columns(growth(kir_last, kir_first, "kir_artis"))
        )

    def rolled(keys: list[str], area: str) -> pl.DataFrame:
        """Neighbourhood rows summed to a level, with how many and how big they are."""
        whole = area_totals(area, last)
        summed = (
            base.group_by(keys)
            .agg(
                pl.len().alias("mahalle_sayisi"),
                pl.col("belediye").n_unique().alias("belediye_sayisi"),
                pl.col(t_last).sum().alias(t_last),
                pl.col(c_last).sum().alias(c_last),
                pl.col(y_last).sum().alias(y_last),
                pl.col(t_first).sum().alias(t_first),
                pl.col(c_first).sum().alias(c_first),
                pl.col(y_first).sum().alias(y_first),
                pl.col(t_last).mean().round(0).alias("mahalle_ortalama"),
                pl.col(t_last).median().round(0).alias("mahalle_ortanca"),
                pl.col(t_last).max().alias("mahalle_en_buyuk"),
                pl.col(t_last).min().alias("mahalle_en_kucuk"),
                pl.col(area + "_id").first().alias("kimlik"),
                # The share is taken over the neighbourhoods whose breakdown is whole,
                # not over the sum of everything: a district's total is right even when a
                # few of its cells are suppressed, but its ratio would not be.
                pl.col(y_last).filter(pl.col("tam")).sum().alias("yetiskin_tam"),
                pl.col(t_last).filter(pl.col("tam")).sum().alias("toplam_tam"),
                (~pl.col("tam")).sum().alias("gizli_mahalle"),
            )
            .with_columns(
                pl.when(pl.col("toplam_tam") > 0)
                .then(pl.col("yetiskin_tam") / pl.col("toplam_tam"))
                .otherwise(None)
                .alias("yetiskin_payi"),
                growth(t_last, t_first, "toplam_artis"),
                growth(c_last, c_first, "cocuk_artis"),
                growth(y_last, y_first, "yetiskin_artis"),
            )
        )
        return summed.join(
            whole, left_on="kimlik", right_on="area_id", how="left"
        ).with_columns((pl.col(t_last) / pl.col("nufus")).alias("kapsam"))

    def with_villages(frame: pl.DataFrame, key: str) -> pl.DataFrame:
        """Attach the village side and the counts that need both halves."""
        return (
            frame.join(koy_stats(key).rename({key: "kimlik"}), on="kimlik", how="left")
            .with_columns(
                pl.col("koy_sayisi").fill_null(0),
                (pl.col("mahalle_sayisi") + pl.col("koy_sayisi").fill_null(0)).alias(
                    "yerlesim_sayisi"
                ),
                pl.col(t_last).alias("kent_" + str(last)),
                growth(t_last, t_first, "kent_artis"),
            )
            .with_columns(
                pl.when(pl.col(kir_last).is_not_null())
                .then(pl.col(kir_last) / (pl.col(kir_last) + pl.col(t_last)))
                .otherwise(None)
                .alias("kir_payi")
            )
        )

    settlement = [
        "yerlesim_sayisi",
        "mahalle_sayisi",
        "koy_sayisi",
        "belediye_sayisi",
        "mahalle_ortalama",
        "mahalle_ortanca",
        "mahalle_en_buyuk",
        "mahalle_en_kucuk",
        "koy_ortalama",
        "koy_ortanca",
        "koy_en_buyuk",
    ]
    population = [
        t_first,
        t_last,
        "toplam_artis",
        c_first,
        c_last,
        "cocuk_artis",
        y_first,
        y_last,
        "yetiskin_artis",
        "yetiskin_payi",
        "gizli_mahalle",
    ]
    rural = [kir_first, kir_last, "kir_artis", "kir_payi"]

    ilceler = (
        with_villages(rolled(["il", "ilce"], "ilce"), "parent_id")
        .rename({"nufus": "gercek_" + str(last)})
        .select(
            ["il", "ilce"]
            + settlement
            + population
            + rural
            + ["gercek_" + str(last), "kapsam", "kimlik"]
        )
        .sort(t_last, descending=True)
    )

    iller = (
        with_villages(rolled(["il"], "il"), "il_id")
        .rename({"nufus": "gercek_" + str(last)})
        .select(
            ["il"]
            + settlement
            + population
            + rural
            + ["kent_artis", "gercek_" + str(last), "kapsam"]
        )
        .sort(t_last, descending=True)
    )

    # endregion

    # region Summary

    def rank(
        frame: pl.DataFrame,
        column: str,
        label: str,
        *,
        rising: bool = True,
        take: int = 10,
        yer: str | None = None,
        start: str | None = None,
        end: str | None = None,
        floor: int = 0,
    ) -> pl.DataFrame:
        """The top or bottom `take` rows on one column, carrying their own evidence.

        A rank on its own is unreadable — "Ardahan, 1" says nothing about whether that is
        a hundred people or a hundred thousand. So every row also shows what it started
        at, what it ended at, and the change between; the ranked value repeats in the
        column that matches its unit, so a single format can never misprint it.

        `floor` guards the growth ranks. Without it the biggest riser is always a
        settlement that went from 3 people to 300 — arithmetically 9.900% and about
        nothing.
        """
        ordered = frame.drop_nulls(column)
        if floor and start:
            ordered = ordered.filter(pl.col(start) >= floor)
        ordered = ordered.sort(column, descending=rising).head(take)
        size = len(ordered)
        share = is_share(column)
        began = ordered[start].cast(pl.Float64).to_list() if start else [None] * size
        ended = ordered[end].cast(pl.Float64).to_list() if end else [None] * size
        # Recomputed from the two columns actually shown rather than read from a growth
        # column: the pair varies by rank (children here, villages there) and a change
        # that does not divide the numbers beside it is worse than no change at all.
        moved = [
            None if not a or b is None else b / a - 1 for a, b in zip(began, ended)
        ]
        return pl.DataFrame(
            {
                "olcut": [label] * size,
                "sira": list(range(1, size + 1)),
                "il": ordered["il"].to_list(),
                "yer": ordered[yer].to_list() if yer else [None] * size,
                "baslangic": began,
                "bitis": ended,
                "degisim": moved,
                "deger_yuzde": (ordered[column].to_list() if share else [None] * size),
                "deger_kisi": (
                    [None] * size
                    if share
                    else ordered[column].cast(pl.Float64).to_list()
                ),
            },
            schema={
                "olcut": pl.Utf8,
                "sira": pl.Int64,
                "il": pl.Utf8,
                "yer": pl.Utf8,
                "baslangic": pl.Float64,
                "bitis": pl.Float64,
                "degisim": pl.Float64,
                "deger_yuzde": pl.Float64,
                "deger_kisi": pl.Float64,
            },
        )

    ozet = pl.concat(
        [
            rank(
                iller,
                "toplam_artis",
                "En çok büyüyen il (belediye nüfusu)",
                start=t_first,
                end=t_last,
            ),
            rank(
                iller,
                "toplam_artis",
                "En çok küçülen il (belediye nüfusu)",
                rising=False,
                start=t_first,
                end=t_last,
            ),
            rank(
                iller,
                "cocuk_artis",
                "Çocuk nüfusu en çok düşen il",
                rising=False,
                start=c_first,
                end=c_last,
            ),
            rank(
                iller,
                "cocuk_artis",
                "Çocuk nüfusu en çok artan il",
                start=c_first,
                end=c_last,
            ),
            rank(
                iller,
                "yetiskin_artis",
                "Yetişkin nüfusu en çok artan il",
                start=y_first,
                end=y_last,
            ),
            rank(
                iller,
                "yetiskin_payi",
                "Yetişkin payı en yüksek il",
                start=y_first,
                end=y_last,
            ),
            rank(
                iller,
                "yetiskin_payi",
                "Yetişkin payı en düşük il",
                rising=False,
                start=y_first,
                end=y_last,
            ),
            rank(
                iller,
                "kir_payi",
                "Kır payı en yüksek il (51 il içinde)",
                start=kir_first,
                end=kir_last,
            ),
            rank(
                iller,
                "kir_payi",
                "Kır payı en düşük il (51 il içinde)",
                rising=False,
                start=kir_first,
                end=kir_last,
            ),
            rank(
                iller,
                "kir_artis",
                "Kır nüfusu en çok düşen il",
                rising=False,
                start=kir_first,
                end=kir_last,
            ),
            rank(
                iller,
                "koy_sayisi",
                "Köyü en çok olan il",
                start=kir_first,
                end=kir_last,
            ),
            rank(
                ilceler,
                t_last,
                "En kalabalık ilçe (belediye nüfusu)",
                yer="ilce",
                start=t_first,
                end=t_last,
            ),
            rank(
                ilceler,
                "toplam_artis",
                "En çok büyüyen ilçe (en az 5.000 kişiden)",
                yer="ilce",
                start=t_first,
                end=t_last,
                floor=5000,
            ),
            rank(
                mahalleler,
                t_last,
                "En kalabalık mahalle",
                yer="mahalle",
                start=t_first,
                end=t_last,
            ),
            rank(
                mahalleler,
                "toplam_artis",
                "En çok büyüyen mahalle (en az 1.000 kişiden)",
                yer="mahalle",
                start=t_first,
                end=t_last,
                floor=1000,
            ),
            rank(
                mahalleler,
                "yetiskin_payi",
                "Yetişkin payı en yüksek mahalle",
                yer="mahalle",
                start=y_first,
                end=y_last,
            ),
            rank(
                koyler, k_last, "En kalabalık köy", yer="koy", start=k_first, end=k_last
            ),
            rank(
                koyler,
                "nufus_artis",
                "En çok büyüyen köy (en az 500 kişiden)",
                yer="koy",
                start=k_first,
                end=k_last,
                floor=500,
            ),
        ]
    )

    # endregion

    seri = (
        wide.select("area_id", "il", "ilce", "mahalle", "yil", "toplam")
        .pivot(values="toplam", index=["area_id", "il", "ilce", "mahalle"], on="yil")
        .select(
            ["il", "ilce", "mahalle"]
            + [str(y) for y in years]
            + [pl.col("area_id").alias("kimlik")]
        )
        .sort(str(last), descending=True)
    )

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
    text = book.add_format({"align": "left", "valign": "vcenter"})
    middle = book.add_format({"align": "center", "valign": "vcenter"})
    # Formats are written in US convention whatever the reader's locale: "." is the
    # decimal point here and Excel renders it as a comma for a Turkish reader.
    sayi = book.add_format(
        {"num_format": "#,##0", "align": "center", "valign": "vcenter"}
    )
    ondalik = book.add_format(
        {"num_format": "#,##0.0", "align": "center", "valign": "vcenter"}
    )

    numeric = {}
    for column in (
        ["kod", "ilk_gorulen", "son_gorulen", "sira", "deger_kisi", "gizli_mahalle"]
        + ["baslangic", "bitis", "gercek_" + str(last)]
        + settlement
        + [t_first, t_last, c_first, c_last, y_first, y_last]
        + [k_first, k_last, kir_first, kir_last, "kent_" + str(last)]
        + [str(y) for y in years]
    ):
        numeric[column] = sayi
    for column in (
        "yetiskin_payi",
        "kapsam",
        "kir_payi",
        "toplam_artis",
        "cocuk_artis",
        "yetiskin_artis",
        "nufus_artis",
        "kir_artis",
        "kent_artis",
        "degisim",
        "deger_yuzde",
    ):
        numeric[column] = ondalik

    formats = {
        **numeric,
        "head": head,
        "text": middle,
        "il": text,
        "ilce": text,
        "bucak": text,
        "belediye": text,
        "mahalle": text,
        "koy": text,
        "yer": text,
        "olcut": text,
        "kimlik": middle,
    }
    widths = {
        "il": 15,
        "ilce": 20,
        "bucak": 18,
        "belediye": 24,
        "mahalle": 28,
        "koy": 24,
        "yer": 26,
        "kimlik": 20,
        "olcut": 40,
        "yetiskin_payi": 14,
        "kapsam": 12,
        "mahalle_ortalama": 13,
        "mahalle_ortanca": 13,
        "koy_ortalama": 13,
        "koy_ortanca": 13,
    }

    # The summary first: it is the sheet that answers a question without being asked one.
    for frame, title in (
        (ozet, "Özet"),
        (mahalleler, "Mahalleler"),
        (koyler, "Köyler"),
        (ilceler, "İlçeler"),
        (iller, "İller"),
        (seri, "Yıllar"),
    ):
        sheet(book, to_percent(frame), title, formats, first, last, widths)

    notes = book.add_worksheet("Notlar")
    notes.set_column(0, 0, 112, book.add_format({"text_wrap": True, "valign": "top"}))
    kayip = len(seri) - len(mahalleler)
    koy_il = koy["il"].n_unique()
    lines = [
        "VeriAtlas — yerleşim nüfusu (mahalle ve köy)",
        "",
        "Kaynak: TÜİK MEDAS, adrese dayalı nüfus kayıt sistemi. Çekim: 2026-08.",
        f"Mahalleler: {first}-{last}, {len(mahalleler)} mahalle, 81 il.",
        f"Köyler: {koy_first}-{koy_last}, {len(koyler)} köy, {koy_il} il.",
        "",
        "YÜZDELER",
        "· Yüzde sütunları hücrede düz sayıdır, birim başlıkta durur: '65,4' değeri",
        "  'Yetişkin payı (%)' başlığı altında yüzde 65,4 demektir. Hücrede % işareti",
        "  yoktur; sayı olduğu gibi sıralanır, ortalaması alınır, grafiğe girer.",
        "· Artış oranları son yıl / ilk yıl − 1 biçimindedir. '233,0' yüzde 233 artış,",
        "  '-11,4' yüzde 11,4 azalış demektir.",
        "",
        "MAHALLE / KÖY AYRIMI",
        "· 6360 sayılı yasa 2014'te 30 büyükşehir ilindeki bütün köyleri mahalleye",
        "  çevirdi. O illerde köy yok — eksik değil, gerçekten yok.",
        "· Kalan 51 ilde ikisi bir arada: belediye mahalleleri (kent) ve köyler (kır).",
        "  'İller' ve 'İlçeler' sayfasındaki kır sütunları yalnız bu 51 il için doludur.",
        "  Büyükşehirlerde bu hücreler boştur; sıfır değildir, hesaplanamaz.",
        "· 'Belediye sayısı' o alandaki ayrı belediye adedidir. Belde belediyesi ile",
        "  büyükşehir ilçe belediyesi kaynakta aynı alanda geçiyor, ayrılamıyor.",
        "",
        "YAŞ AYRIMI YALNIZ MAHALLEDE",
        "· TÜİK 18+ kırılımını yalnız belediye mahalleleri için yayımlıyor: MEDAS'ta yaş",
        "  kırılımı işaretlenince Köy düzeyi seçeneklerden kayboluyor.",
        "· Bu yüzden köyler yalnız toplam nüfusla karşılaştırılıyor. Köy sayfasında çocuk",
        "  ve yetişkin sütunu yoktur — boş bırakılmamıştır, sorulamaz.",
        "",
        "GİZLENEN HÜCRELER",
        "· TÜİK küçük hücreleri gizliyor: bir mahallenin çocuk sayısı yayımlanmamış",
        "  olabiliyor. Yayımlananı toplamak o mahalleyi '%100 yetişkin' gösterirdi.",
        "· Bu yüzden yetişkin payı, yalnız iki yaş grubu da yayımlanmış mahallelerde",
        "  hesaplanıyor; ötekilerde hücre boştur. İl ve ilçe payı da yalnız bu",
        "  mahalleler üzerinden alınıyor. 'Yaşı gizli mahalle' sütunu kaçının böyle",
        "  olduğunu söylüyor.",
        "· Toplam nüfus sütunları bundan etkilenmez; gizlenen yalnız yaş ayrımıdır.",
        "",
        "ÖZET SAYFASI",
        "· Her sıra, sıralandığı sayıyı yanında taşır: başlangıç yılı, bitiş yılı ve",
        "  aradaki değişim. Sıra tek başına okunmaz.",
        "· Değer iki sütuna ayrılmıştır — 'Değer (%)' ve 'Değer (kişi)' — çünkü tek",
        "  sütunda yüzde ile kişi aynı biçimle yazılırdı ve biri yanlış görünürdü.",
        "· Artış sıralamalarında bir taban vardır (mahallede 1.000, ilçede 5.000, köyde",
        "  500 kişi). Tabansız sıralamada birinci hep 3 kişiden 300'e çıkan yerdir:",
        "  yüzde 9.900 artış, ve hiçbir şey anlatmaz.",
        "",
        "KAPSAM",
        "· 'Kapsam' sütunu: mahallelerin toplamı, yayımlanan gerçek nüfusun yüzde kaçı.",
        "  Türkiye genelinde %95. Şanlıurfa ve Van'da %100 (her köy mahalle olmuş),",
        "  Ardahan'da %47 — aradaki fark köylerde yaşayanlardır ve o kısım 'Köyler'",
        "  sayfasındadır.",
        f"· {kayip} mahalle 'Mahalleler' sayfasında yok: {last} yılında verisi olan {len(mahalleler)} mahalle",
        f"  var, oysa {first}-{last} arasında {len(seri)} ayrı mahalle görüldü. Fark; birleşen, kapanan",
        "  ya da kimliği değişenlerdir. Hepsi 'Yıllar' sayfasında, son görüldüğü yılla.",
        "",
        "İSİMLER",
        "· Kimlik MEDAS kodudur, ad değildir. Aynı il içinde yüzlerce mahalle aynı adı",
        "  taşıyor ('Merkez', 'Yeni'); köylerde de 'Merkez Bucağı' altında aynı adlar",
        "  tekrarlanıyor. Bu yüzden hiçbir eşleştirme ada göre yapılmadı.",
        "· Gösterilen ad, görülen EN YENİ addır. 2013-2025 arasında 846 mahalle adı",
        "  değişti; eski adlarıyla birlikte docs/mahalle-adlari.md dosyasında.",
        "· 'İlk görülen' / 'son görülen', verinin bulunduğu yıllardır — idari kuruluş ya",
        "  da kapanış tarihi değildir.",
        "",
        "ORANLAR",
        "· Yetişkin payı = 18+ / toplam. Kır payı = köy / (köy + belediye).",
        "· Bir yerleşim aradaki yıllarda bölündüyse ya da birleştiyse, oran o idari",
        "  değişimi de içerir; nüfusun kendi hareketi değildir.",
    ]
    for row, line in enumerate(lines):
        notes.write(row, 0, line)

    book.close()
    # endregion

    print("yazildi:", TARGET)
    print(
        "  Mahalleler:",
        len(mahalleler),
        "| Köyler:",
        len(koyler),
        "| İlçeler:",
        len(ilceler),
        "| İller:",
        len(iller),
        "| Özet:",
        len(ozet),
    )


if __name__ == "__main__":
    main()
