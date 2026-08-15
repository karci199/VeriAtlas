"""Two spreadsheets of district births and deaths.

Why a file and not the screen: the explorer does not offer the district level yet, and
"973 districts sorted by natural increase" is a spreadsheet question anyway — a menu of
973 entries is a worse way to ask it than a column you can sort.

    cikti/ilce-dogum-olum.xlsx      every year of both counts
    cikti/ilce-dogal-artis-2014-2025.xlsx   the two ends, side by side

**The two files cover different spans, and the difference is TÜİK's.** Deaths are
published per district from 2009, births only from **2014** — so anything that needs both
(natural increase, and therefore the whole second file) starts at 2014. The death sheet in
the first file still runs the full seventeen years, because throwing away five years of a
published series to make two sheets line up would be a loss with nothing bought.

The rate is **per mille of the district's own population**, and it is our division, not a
TÜİK publication: the counts are the year's events, the population is the year-*end*
ADNKS, while TÜİK's own crude rates use the mid-year population. The gap that opens is
small — measured against the published province rates it is 0,05-0,10 per mille (K19) —
but it is there, so the sheets say so rather than presenting the number as the official
one.

Run:  uv run python scripts/build_vital_excel.py
"""

from __future__ import annotations

import sys

import polars as pl
import xlsxwriter

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC

OUT = PUBLIC.parent / "cikti"
ALL_YEARS = OUT / "ilce-dogum-olum.xlsx"
COMPARISON = OUT / "ilce-dogal-artis-2014-2025.xlsx"
DATA = PUBLIC.parent / "src" / "veriatlas" / "data"

#: The two ends of the comparison. Both are read back out of the data rather than trusted:
#: `first` is the first year births exist at this level, and if that ever changes the file
#: should be named after the year it actually holds.
FIRST, LAST = 2014, 2025


def facts() -> pl.DataFrame:
    """District rows of every indicator these sheets need, summed over breakdowns.

    Summed because all four are counts, and a count's total is the sum of its parts:
    deaths arrive split by sex, population by sex and age band, births and natural
    increase whole. Anything that did not add up would have to be handled per indicator —
    none of these are, and the unit dictionary is what says so.
    """
    fact = pl.read_parquet(PUBLIC / "fact.parquet")
    rows = (
        fact.filter(pl.col("area_level") == "district")
        .filter(
            pl.col("indicator_id").is_in(
                ["births", "deaths", "natural_increase", "population"]
            )
        )
        .with_columns(pl.col("period_start").dt.year().alias("yil"))
        .group_by("indicator_id", "area_id", "yil")
        .agg(pl.col("value").sum())
    )
    if rows.is_empty():
        raise ValueError(
            "depoda ilce satiri yok — once "
            "'uv run python scripts/load.py' (tuik_district_births, tuik_district_deaths)"
        )
    return rows


def renames() -> dict[str, str]:
    """Old district id → the id the same place goes by now.

    The registry deliberately keeps a renamed district as two areas with one MEDAS code
    and non-overlapping validity, so that a number lands under the name the year used
    (K26). That is right for the fact table and wrong for a spreadsheet: Kazan in 2014 and
    Kahramankazan in 2025 are one place, and left apart they come out as two half-empty
    rows that cannot be compared with themselves.

    So the pair is folded here, in the sheet, and the current name is the one shown. Two
    districts are affected: Kazan → Kahramankazan (2017) and Eyüp → Eyüpsultan (2018).
    """
    registry = pl.read_csv(DATA / "areas_tr_districts.csv")
    mapping: dict[str, str] = {}
    for code, group in registry.group_by("medas_code"):
        if group.height < 2:
            continue
        # The one still in force: no closing year. Ordered by opening year as a fallback,
        # so a code with two closed rows still resolves to the later of them rather than
        # to whichever came first in the file.
        ordered = group.sort("valid_to", nulls_last=True, descending=False)
        current = ordered.filter(pl.col("valid_to").is_null())
        target = (current if current.height else ordered.tail(1)).row(0, named=True)
        for row in group.iter_rows(named=True):
            if row["area_id"] != target["area_id"]:
                mapping[row["area_id"]] = target["area_id"]
    return mapping


def folded(rows: pl.DataFrame, mapping: dict[str, str]) -> pl.DataFrame:
    """Apply the rename map, refusing to add a place to itself.

    The two ids never overlap in time, so the sum is always a sum of one — but that is a
    property of the registry rather than of this code, and if it stopped holding the
    numbers would silently double instead of erroring.
    """
    moved = rows.with_columns(
        pl.col("area_id").replace(mapping).alias("area_id"),
    )
    clash = (
        moved.group_by("indicator_id", "area_id", "yil").len().filter(pl.col("len") > 1)
    )
    if clash.height:
        raise ValueError(
            "ad değişikliği katlanırken aynı yıl iki kez geldi: "
            + str(clash.head(5).to_dicts())
        )
    return moved


def wide(rows: pl.DataFrame) -> pl.DataFrame:
    """One row per district-year: dogum, olum, artis, nufus."""
    return (
        rows.pivot(values="value", index=["area_id", "yil"], on="indicator_id")
        .rename(
            {
                "births": "dogum",
                "deaths": "olum",
                "natural_increase": "artis",
                "population": "nufus",
            }
        )
        .with_columns(
            # Per mille of the district's own population. Guarded against a missing or
            # zero population rather than left to produce an infinity: a district with no
            # population row is a gap, and a gap divided into is not a rate.
            *[
                pl.when(pl.col("nufus") > 0)
                .then(pl.col(name) / pl.col("nufus") * 1000)
                .otherwise(None)
                .alias(name + "_hiz")
                for name in ("dogum", "olum", "artis")
            ]
        )
    )


def deaths_by_sex(mapping: dict[str, str]) -> pl.DataFrame:
    """District deaths kept split, the one breakdown these counts carry."""
    fact = pl.read_parquet(PUBLIC / "fact.parquet")
    rows = (
        fact.filter(
            (pl.col("indicator_id") == "deaths") & (pl.col("area_level") == "district")
        )
        .with_columns(
            pl.col("period_start").dt.year().alias("yil"),
            pl.col("dims").str.extract(r"sex=([^;]*)").alias("cinsiyet"),
        )
        .select("area_id", "yil", "cinsiyet", "value")
        .with_columns(pl.col("area_id").replace(mapping))
    )
    return (
        rows.pivot(values="value", index=["area_id", "yil"], on="cinsiyet")
        .rename({"male": "erkek", "female": "kadin"})
        .with_columns(
            pl.when(pl.col("kadin") > 0)
            .then(pl.col("erkek") / pl.col("kadin") * 100)
            .otherwise(None)
            .alias("cinsiyet_orani")
        )
    )


def names() -> pl.DataFrame:
    """District id → province name, district name. The province column is here because a
    district name alone does not identify one: there are several Merkez, several Yeni."""
    districts = pl.read_csv(DATA / "areas_tr_districts.csv").select(
        "area_id",
        pl.col("name_tr").alias("ilce"),
        "parent_id",
    )
    provinces = pl.read_csv(DATA / "areas_tr.csv").select(
        "area_id", pl.col("name_tr").alias("il")
    )
    return districts.join(
        provinces, left_on="parent_id", right_on="area_id", how="left"
    ).select("area_id", "il", "ilce", pl.col("parent_id").alias("il_id"))


def turkish(value: float, decimals: int = 0) -> str:
    """A number written the way the rest of the file writes it: 959.997 and 12,36.

    The cells get this from their number format; the notes are plain strings and would
    otherwise carry US separators into a Turkish page — the one place in the workbook
    where the two conventions could sit a line apart.
    """
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def change(now: str, before: str, name: str) -> pl.Expr:
    """Growth as a proportion — and only where the base is positive.

    A base of zero has no proportion, and a *negative* base inverts the sign: a natural
    increase going from −1.000 to −500 is an improvement, and "%50 düştü" says the
    opposite. The same trap the page hit (K21), so the same rule: no percentage on a base
    that is not positive. The plain difference is always there next to it and is never
    wrong.
    """
    return (
        pl.when(pl.col(before) > 0)
        .then(pl.col(now) / pl.col(before) - 1)
        .otherwise(None)
        .alias(name)
    )


#: Every header says its unit. Three different things are counted in these files — people,
#: events per thousand people, and a change as a proportion — and they sit in neighbouring
#: columns. "Doğal artış 12,36" is unreadable without knowing which of the three it is.
HEADERS = {
    "il": "İl",
    "ilce": "İlçe",
    "kimlik": "Kimlik",
    "yil": "Yıl",
    "erkek": "Erkek ölüm (kişi)",
    "kadin": "Kadın ölüm (kişi)",
    "cinsiyet_orani": "Cinsiyet oranı (E/K×100)",
    "ilce_sayisi": "İlçe sayısı",
    "sira": "Sıra",
    "olcut": "Ölçüt",
    "deger": "Değer",
    "durum": "Durum",
    "dogum": "Doğum (kişi)",
    "olum": "Ölüm (kişi)",
    "artis": "Doğal artış (kişi)",
    "nufus": "Nüfus (kişi)",
    "dogum_hiz": "Doğum hızı (‰)",
    "olum_hiz": "Ölüm hızı (‰)",
    "artis_hiz": "Doğal artış hızı (‰)",
    "artis_fark": "Doğal artış farkı (kişi)",
    "artis_hiz_fark": "Doğal artış hızı farkı (‰)",
    "dogum_degisim": "Doğum değişimi (%)",
    "olum_degisim": "Ölüm değişimi (%)",
    "nufus_degisim": "Nüfus değişimi (%)",
}

#: Word plus year, for the columns that carry one: `dogum_2014` → "Doğum 2014 (kişi)".
STEMS = {
    "dogum_hiz": "Doğum hızı {} (‰)",
    "olum_hiz": "Ölüm hızı {} (‰)",
    "artis_hiz": "Doğal artış hızı {} (‰)",
    "dogum": "Doğum {} (kişi)",
    "olum": "Ölüm {} (kişi)",
    "artis": "Doğal artış {} (kişi)",
    "nufus": "Nüfus {} (kişi)",
}


def header_of(column: str) -> str:
    if column in HEADERS:
        return HEADERS[column]
    if column.isdigit():
        return column
    # Longest stem first, or `dogum` would claim `dogum_hiz_2014`.
    for stem in sorted(STEMS, key=len, reverse=True):
        if column.startswith(stem + "_") and column[len(stem) + 1 :].isdigit():
            return STEMS[stem].format(column[len(stem) + 1 :])
    return column[:1].upper() + column[1:].replace("_", " ")


def sheet(book, frame, title, formats, widths) -> None:
    """One sheet: frozen header, filter on, names left-aligned and the rest centred."""
    page = book.add_worksheet(title)
    page.freeze_panes(1, 0)
    page.set_row(0, 34)

    for index, column in enumerate(frame.columns):
        page.write(0, index, header_of(column), formats["head"])
        page.set_column(
            index, index, widths.get(column, 14), formats.get(column, formats["text"])
        )
    page.autofilter(0, 0, len(frame), len(frame.columns) - 1)

    for index, column in enumerate(frame.columns):
        style = formats.get(column, formats["text"])
        for row, value in enumerate(frame[column].to_list(), start=1):
            if value is None:
                continue
            page.write(row, index, value, style)


def styles(book, columns: set[str]) -> tuple[dict, dict]:
    """Formats keyed by column name, and the widths. Driven by what the columns are
    called rather than by a list per sheet, so a column added to one sheet cannot arrive
    unformatted in another."""
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
    # A number format code is written in Excel's own notation, not in the reader's: the
    # dot is the decimal point and the comma is the thousands separator *inside the code*,
    # whatever the machine then displays. Written `0,00` the code says "one digit, scaled
    # down by a thousand", so 19,63 came out as 0019 — which is what a Turkish-looking
    # format string does when Excel reads it as an English one. The displayed separators
    # come from the reader's locale and need no help from here.
    sayi = book.add_format(
        {"num_format": "#,##0", "align": "center", "valign": "vcenter"}
    )
    # Negative counts in red: half the point of the natural increase sheet is which
    # districts crossed the line, and a minus sign in a column of five-digit numbers is
    # easy to read past.
    eksili = book.add_format(
        {"num_format": "#,##0;[Red]-#,##0", "align": "center", "valign": "vcenter"}
    )
    ondalik = book.add_format(
        {"num_format": "0.00;[Red]-0.00", "align": "center", "valign": "vcenter"}
    )
    yuzde = book.add_format(
        {"num_format": "0.00%;[Red]-0.00%", "align": "center", "valign": "vcenter"}
    )

    formats: dict = {
        "head": head,
        "text": middle,
        # Named alongside the per-column entries, for the summary sheet — it lays its own
        # blocks out and picks a format per cell rather than per column.
        "left": text,
        "middle": middle,
        "sayi": sayi,
        "eksili": eksili,
        "ondalik": ondalik,
        "yuzde": yuzde,
        "title": book.add_format({"bold": True, "font_size": 15, "valign": "vcenter"}),
        "block": book.add_format(
            {
                "bold": True,
                "font_size": 11,
                "valign": "vcenter",
                "bg_color": "#D9E2F3",
                "border": 1,
            }
        ),
        "note": book.add_format(
            {"italic": True, "font_color": "#555555", "valign": "vcenter"}
        ),
    }
    for column in columns:
        stem = (
            column.rsplit("_", 1)[0] if column.rsplit("_", 1)[-1].isdigit() else column
        )
        if column in ("il", "ilce", "olcut", "durum"):
            formats[column] = text
        elif column in ("kimlik", "yil", "sira"):
            formats[column] = middle
        elif stem.endswith("_hiz") or stem in ("cinsiyet_orani", "artis_hiz_fark"):
            formats[column] = ondalik
        elif stem.endswith("_degisim"):
            formats[column] = yuzde
        elif stem in ("artis", "artis_fark") or column == "deger":
            formats[column] = eksili
        else:
            formats[column] = sayi

    widths = {
        "il": 15,
        "ilce": 22,
        "kimlik": 14,
        "olcut": 42,
        "durum": 30,
        "artis_fark": 16,
        "artis_hiz_fark": 16,
        "cinsiyet_orani": 16,
    }
    return formats, widths


#: A summary block: a heading, an optional line of explanation, the column headers, and
#: the rows. Each column carries the name of the format its cells take, because a summary
#: puts people and per-mille in neighbouring columns and the format cannot be inferred
#: from the column's position.
WIDE = 6


def summary(book, page, formats, heading: str, blocks: list[dict]) -> None:
    """The Özet sheet: stacked blocks, each a small titled table.

    Not one long frame with an "ölçüt" column repeated ten times per question. That shape
    is what a filter is for, and the summary is the sheet you read *without* filtering —
    so the questions are laid out as separate little tables with their own headers, and
    each says what it is measuring in its own units.
    """
    page.set_column(0, 0, 6)
    page.set_column(1, 1, 16)
    page.set_column(2, 2, 22)
    page.set_column(3, 8, 18)

    page.set_row(0, 26)
    page.write(0, 0, heading, formats["title"])
    row = 2

    for block in blocks:
        page.merge_range(row, 0, row, WIDE, block["title"], formats["block"])
        row += 1
        if block.get("note"):
            page.merge_range(row, 0, row, WIDE, block["note"], formats["note"])
            row += 1
        for index, (header, _) in enumerate(block["columns"]):
            page.write(row, index, header, formats["head"])
        page.set_row(row, 30)
        row += 1
        for values in block["rows"]:
            for index, ((_, style), value) in enumerate(zip(block["columns"], values)):
                if value is None:
                    continue
                page.write(row, index, value, formats[style])
            row += 1
        row += 1


def ranked(frame: pl.DataFrame, column: str, columns, rising=True, take=10) -> dict:
    """The ten highest or lowest on one column, as summary rows.

    `columns` names what to show alongside the ranking — the ranking column on its own
    would answer "which" without ever saying "compared with what".
    """
    ordered = frame.drop_nulls(column).sort(column, descending=rising).head(take)
    keys = [key for key, _, _ in columns]
    return {
        "columns": [("Sıra", "middle")]
        + [(header, style) for _, header, style in columns],
        "rows": [
            [rank] + [row[key] for key in keys]
            for rank, row in enumerate(ordered.to_dicts(), start=1)
        ],
    }


def write(
    target,
    heading: str,
    blocks: list[dict],
    sheets: list[tuple[str, pl.DataFrame]],
    notes: list[str],
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    book = xlsxwriter.Workbook(str(target))
    columns = {column for _, frame in sheets for column in frame.columns}
    formats, widths = styles(book, columns)

    # First, so it is the sheet the file opens on: it answers a question without being
    # asked one.
    summary(book, book.add_worksheet("Özet"), formats, heading, blocks)

    for title, frame in sheets:
        sheet(book, frame, title, formats, widths)

    page = book.add_worksheet("Notlar")
    page.set_column(0, 0, 112, book.add_format({"text_wrap": True, "valign": "top"}))
    for row, line in enumerate(notes):
        page.write(row, 0, line)

    book.close()
    print("yazildi:", target)
    for title, frame in sheets:
        print("  ", title + ":", len(frame))


def top(frame: pl.DataFrame, column: str, label: str, rising=True, take=10):
    """The ten highest or lowest on one column, as summary rows."""
    ordered = frame.drop_nulls(column).sort(column, descending=rising).head(take)
    return pl.DataFrame(
        {
            "olcut": [label] * len(ordered),
            "sira": list(range(1, len(ordered) + 1)),
            "il": ordered["il"].to_list(),
            "ilce": ordered["ilce"].to_list(),
            "deger": ordered[column].cast(pl.Float64).to_list(),
        }
    )


def build_all_years(rows: pl.DataFrame, area: pl.DataFrame, mapping: dict) -> None:
    """Every year of both counts, one sheet per shape."""
    table = wide(rows).join(area, on="area_id", how="left")
    dogum_years = sorted(
        table.filter(pl.col("dogum").is_not_null())["yil"].unique().to_list()
    )
    olum_years = sorted(
        table.filter(pl.col("olum").is_not_null())["yil"].unique().to_list()
    )

    def spread(column: str, years: list[int]) -> pl.DataFrame:
        return (
            table.filter(pl.col("yil").is_in(years))
            .select("area_id", "il", "ilce", "yil", column)
            .pivot(values=column, index=["area_id", "il", "ilce"], on="yil")
            .select(
                ["il", "ilce"]
                + [str(y) for y in years]
                + [pl.col("area_id").alias("kimlik")]
            )
            .sort(str(years[-1]), descending=True, nulls_last=True)
        )

    son = (
        table.filter(pl.col("yil") == LAST)
        .select(
            "il",
            "ilce",
            "nufus",
            "dogum",
            "olum",
            "artis",
            "dogum_hiz",
            "olum_hiz",
            "artis_hiz",
            pl.col("area_id").alias("kimlik"),
        )
        .sort("artis", descending=True, nulls_last=True)
    )

    iller = (
        table.group_by("il", "il_id", "yil")
        .agg(
            pl.len().alias("ilce_sayisi"),
            pl.col("nufus").sum(),
            pl.col("dogum").sum(),
            pl.col("olum").sum(),
            pl.col("artis").sum(),
        )
        .filter(pl.col("yil") == LAST)
        .with_columns(
            *[
                (pl.col(name) / pl.col("nufus") * 1000).alias(name + "_hiz")
                for name in ("dogum", "olum", "artis")
            ]
        )
        .select(
            "il",
            "ilce_sayisi",
            "nufus",
            "dogum",
            "olum",
            "artis",
            "dogum_hiz",
            "olum_hiz",
            "artis_hiz",
        )
        .sort("artis", descending=True)
    )

    sex = (
        deaths_by_sex(mapping)
        .join(area, on="area_id", how="left")
        .select(
            "il",
            "ilce",
            "yil",
            "erkek",
            "kadin",
            "cinsiyet_orani",
            pl.col("area_id").alias("kimlik"),
        )
        .sort("il", "ilce", "yil")
    )

    # Türkiye, year by year: the one table that says what the whole file is about before
    # any of it is filtered.
    country = (
        table.group_by("yil")
        .agg(
            pl.col("dogum").sum(),
            pl.col("olum").sum(),
            pl.col("artis").sum(),
            pl.col("nufus").sum(),
        )
        .sort("yil")
        .with_columns(
            *[
                (pl.col(name) / pl.col("nufus") * 1000).alias(name + "_hiz")
                for name in ("dogum", "olum", "artis")
            ]
        )
    )

    # A year outside a measure's span is written as a gap, not a zero. `sum` over a column
    # of nulls returns 0, and the population reaches back to 2007 while deaths start in
    # 2009 and births in 2014 — so read literally the table opened with two years in which
    # nobody had died.
    def only(row: dict, key: str, years: list[int]):
        return row[key] if row["yil"] in years else None

    country_rows = [
        [
            row["yil"],
            row["nufus"],
            only(row, "dogum", dogum_years),
            only(row, "olum", olum_years),
            only(row, "artis", dogum_years),
            only(row, "dogum_hiz", dogum_years),
            only(row, "olum_hiz", olum_years),
            only(row, "artis_hiz", dogum_years),
        ]
        for row in country.to_dicts()
    ]

    place = [("il", "İl", "left"), ("ilce", "İlçe", "left")]
    counts = place + [("nufus", "Nüfus (kişi)", "sayi")]

    ozet = [
        {
            "title": "Türkiye — ilçelerin toplamı, yıl yıl",
            "note": "Doğum ilçe düzeyinde 2014'te başlıyor; öncesi boş, sıfır değil.",
            "columns": [
                ("Yıl", "middle"),
                ("Nüfus (kişi)", "sayi"),
                ("Doğum (kişi)", "sayi"),
                ("Ölüm (kişi)", "sayi"),
                ("Doğal artış (kişi)", "eksili"),
                ("Doğum hızı (‰)", "ondalik"),
                ("Ölüm hızı (‰)", "ondalik"),
                ("Doğal artış hızı (‰)", "ondalik"),
            ],
            "rows": country_rows,
        },
        {
            "title": f"{LAST} · en çok doğum olan 10 ilçe",
            **ranked(
                son,
                "dogum",
                counts
                + [
                    ("dogum", "Doğum (kişi)", "sayi"),
                    ("dogum_hiz", "Doğum hızı (‰)", "ondalik"),
                ],
            ),
        },
        {
            "title": f"{LAST} · en çok ölüm olan 10 ilçe",
            **ranked(
                son,
                "olum",
                counts
                + [
                    ("olum", "Ölüm (kişi)", "sayi"),
                    ("olum_hiz", "Ölüm hızı (‰)", "ondalik"),
                ],
            ),
        },
        {
            "title": f"{LAST} · doğal artış hızı en yüksek 10 ilçe",
            "note": "Hız, nüfusa bölünmüş hâli: kalabalık ilçeyi öne çıkarmaz.",
            **ranked(
                son,
                "artis_hiz",
                counts
                + [
                    ("artis", "Doğal artış (kişi)", "eksili"),
                    ("artis_hiz", "Doğal artış hızı (‰)", "ondalik"),
                ],
            ),
        },
        {
            "title": f"{LAST} · doğal artış hızı en düşük 10 ilçe",
            **ranked(
                son,
                "artis_hiz",
                counts
                + [
                    ("artis", "Doğal artış (kişi)", "eksili"),
                    ("artis_hiz", "Doğal artış hızı (‰)", "ondalik"),
                ],
                rising=False,
            ),
        },
        {
            "title": f"{LAST} · doğal artışı kişi olarak en yüksek 10 ilçe",
            **ranked(
                son,
                "artis",
                counts
                + [
                    ("artis", "Doğal artış (kişi)", "eksili"),
                    ("artis_hiz", "Doğal artış hızı (‰)", "ondalik"),
                ],
            ),
        },
        {
            "title": f"{LAST} · doğal artışı kişi olarak en düşük 10 ilçe",
            **ranked(
                son,
                "artis",
                counts
                + [
                    ("artis", "Doğal artış (kişi)", "eksili"),
                    ("artis_hiz", "Doğal artış hızı (‰)", "ondalik"),
                ],
                rising=False,
            ),
        },
    ]

    negatives = son.filter(pl.col("artis") < 0).height
    write(
        ALL_YEARS,
        f"VeriAtlas — ilçelere göre doğum ve ölüm · {olum_years[0]}-{olum_years[-1]}",
        ozet,
        [
            (f"İlçeler {LAST}", son),
            (f"İller {LAST}", iller),
            ("Doğum (kişi)", spread("dogum", dogum_years)),
            ("Ölüm (kişi)", spread("olum", olum_years)),
            ("Ölüm cinsiyete göre (kişi)", sex),
            ("Doğal artış (kişi)", spread("artis", dogum_years)),
            ("Nüfus (kişi)", spread("nufus", olum_years)),
        ],
        [
            "VeriAtlas — ilçelere göre doğum ve ölüm sayısı",
            "",
            "Kaynak: TÜİK MEDAS. Çekim: 2026-08.",
            "Ölçüler: 'İlçelere göre doğum sayısı' ve 'İlçelere göre ölüm sayısı",
            "(İkametgah yeri)'. Nüfus: adrese dayalı nüfus kayıt sistemi, yıl sonu.",
            "",
            "KAPSAM",
            f"· Ölüm {olum_years[0]}-{olum_years[-1]}, doğum {dogum_years[0]}-{dogum_years[-1]}.",
            "  Doğum ilçe düzeyinde 2014'ten önce yayımlanmıyor — eksik değil, yok.",
            "· Doğal artış = doğum − ölüm, yani yalnız ikisinin de bulunduğu yıllarda",
            "  hesaplanabiliyor (2014'ten itibaren).",
            "· İlçe sayısı yıla göre değişiyor: 2009'da 957, 2025'te 973. Yeni kurulan",
            "  ilçenin önceki yılları boştur; sıfır değildir, o yıl o ilçe yoktu.",
            "",
            "İKAMETGAH YERİ",
            "· İkisi de olayın olduğu yere değil, annenin / ölen kişinin ikamet ettiği",
            "  yere göredir. Hastanesi olan ilçe, komşularının doğum ve ölümlerini kayda",
            "  geçirir; nüfusun yanına konabilecek okuma ikametgahtır.",
            "",
            "HIZLAR",
            "· '‰' sütunları bizim bölmemizdir, TÜİK yayını değil: olay sayısı ÷ o yılın",
            "  yıl sonu nüfusu × 1000. TÜİK kendi kaba hızlarında yıl ORTASI nüfusu",
            "  kullanıyor; il düzeyinde ölçülen fark 0,05-0,10 binde.",
            "",
            "DOĞRULAMA",
            "· İlçeler ile toplandığında, TÜİK'in yayımladığı il sayılarıyla 972 ve",
            "  1.377 il-yılın hepsinde birebir aynı; ölümde cinsiyet ayrı ayrı da.",
            "",
            "SÜTUNLAR",
            "· 'Kimlik' bizim alan kimliğimizdir (TR-34-023). Eşleştirme MEDAS kodu ve",
            "  yıl üzerinden yapıldı, ad üzerinden değil.",
            "· Dönem içinde iki ilçe ad değiştirdi: Kazan → Kahramankazan (2017) ve",
            "  Eyüp → Eyüpsultan (2018). Bu sayfalarda tek satır olarak, bugünkü adıyla",
            "  duruyorlar; depo ikisini ayrı tutuyor, çünkü orada sayı o yılın adıyla",
            "  eşleşmek zorunda.",
            f"· {LAST} yılında doğal artışı eksi olan ilçe sayısı: {negatives}.",
        ],
    )


def build_comparison(rows: pl.DataFrame, area: pl.DataFrame) -> None:
    """The two ends side by side: what natural increase was, what it is."""
    table = wide(rows).join(area, on="area_id", how="left")

    def at(year: int) -> pl.DataFrame:
        return table.filter(pl.col("yil") == year).select(
            "area_id",
            *[
                pl.col(name).alias(name + "_" + str(year))
                for name in (
                    "nufus",
                    "dogum",
                    "olum",
                    "artis",
                    "dogum_hiz",
                    "olum_hiz",
                    "artis_hiz",
                )
            ],
        )

    def compare(frame: pl.DataFrame) -> pl.DataFrame:
        return frame.with_columns(
            (pl.col(f"artis_{LAST}") - pl.col(f"artis_{FIRST}")).alias("artis_fark"),
            (pl.col(f"artis_hiz_{LAST}") - pl.col(f"artis_hiz_{FIRST}")).alias(
                "artis_hiz_fark"
            ),
            change(f"dogum_{LAST}", f"dogum_{FIRST}", "dogum_degisim"),
            change(f"olum_{LAST}", f"olum_{FIRST}", "olum_degisim"),
            change(f"nufus_{LAST}", f"nufus_{FIRST}", "nufus_degisim"),
            # The one thing a reader scans this file for, said in words rather than left
            # to be worked out from two signs. A district missing one of the two years is
            # named as such: an unguarded comparison would send a null through the
            # `otherwise` branch and label it as though it had been measured.
            pl.when(
                pl.col(f"artis_{FIRST}").is_null() | pl.col(f"artis_{LAST}").is_null()
            )
            .then(pl.lit("karşılaştırılamaz (yılı eksik)"))
            .when(pl.col(f"artis_{FIRST}") >= 0)
            .then(
                pl.when(pl.col(f"artis_{LAST}") >= 0)
                .then(pl.lit("artıda kaldı"))
                .otherwise(pl.lit("eksiye döndü"))
            )
            .otherwise(
                pl.when(pl.col(f"artis_{LAST}") >= 0)
                .then(pl.lit("artıya döndü"))
                .otherwise(pl.lit("ekside kaldı"))
            )
            .alias("durum"),
        )

    order = [
        "il",
        "ilce",
        f"nufus_{FIRST}",
        f"dogum_{FIRST}",
        f"olum_{FIRST}",
        f"artis_{FIRST}",
        f"artis_hiz_{FIRST}",
        f"nufus_{LAST}",
        f"dogum_{LAST}",
        f"olum_{LAST}",
        f"artis_{LAST}",
        f"artis_hiz_{LAST}",
        "artis_fark",
        "artis_hiz_fark",
        "dogum_degisim",
        "olum_degisim",
        "nufus_degisim",
        "durum",
    ]

    # Every district that has either year, not only the ones that have both. Three were
    # founded after 2014 and an inner join dropped them — which reads as "no such place"
    # rather than "no such year", and they are exactly the districts a reader looking at
    # change would want to see named.
    present = pl.concat(
        [at(FIRST).select("area_id"), at(LAST).select("area_id")]
    ).unique()
    ilceler = (
        compare(
            area.join(present, on="area_id", how="semi")
            .join(at(FIRST), on="area_id", how="left")
            .join(at(LAST), on="area_id", how="left")
        )
        .select(*order, pl.col("area_id").alias("kimlik"))
        .sort("artis_hiz_fark", nulls_last=True)
    )

    rolled = (
        table.filter(pl.col("yil").is_in([FIRST, LAST]))
        .group_by("il", "yil")
        .agg(
            pl.len().alias("ilce_sayisi"),
            pl.col("nufus").sum(),
            pl.col("dogum").sum(),
            pl.col("olum").sum(),
            pl.col("artis").sum(),
        )
        .with_columns(
            *[
                (pl.col(name) / pl.col("nufus") * 1000).alias(name + "_hiz")
                for name in ("dogum", "olum", "artis")
            ]
        )
    )

    def province_at(year: int) -> pl.DataFrame:
        return rolled.filter(pl.col("yil") == year).select(
            "il",
            *[
                pl.col(name).alias(name + "_" + str(year))
                for name in (
                    "nufus",
                    "dogum",
                    "olum",
                    "artis",
                    "dogum_hiz",
                    "olum_hiz",
                    "artis_hiz",
                )
            ],
        )

    iller = (
        compare(province_at(FIRST).join(province_at(LAST), on="il", how="left"))
        .select([c for c in order if c != "ilce"])
        .sort("artis_hiz_fark", nulls_last=True)
    )

    # Türkiye, both years: the summary opens with it and the notes close with it, so it
    # is computed once. Summed from the districts, which is what makes it a check as well
    # as a headline — it comes out equal to the published province and country figures.
    whole = {
        year: table.filter(pl.col("yil") == year)
        .select(
            pl.col("nufus").sum(),
            pl.col("dogum").sum(),
            pl.col("olum").sum(),
            pl.col("artis").sum(),
        )
        .to_dicts()[0]
        for year in (FIRST, LAST)
    }

    place = [("il", "İl", "left"), ("ilce", "İlçe", "left")]
    #: The pair of columns the whole file is about, shown next to every ranking: a place
    #: is nowhere near described by the number it was ranked on.
    both = [
        (f"artis_hiz_{FIRST}", f"Doğal artış hızı {FIRST} (‰)", "ondalik"),
        (f"artis_hiz_{LAST}", f"Doğal artış hızı {LAST} (‰)", "ondalik"),
        ("artis_hiz_fark", "Fark (‰)", "ondalik"),
    ]

    ozet = [
        {
            "title": "Türkiye — ilçelerin toplamı",
            "columns": [
                ("", "left"),
                ("Nüfus (kişi)", "sayi"),
                ("Doğum (kişi)", "sayi"),
                ("Ölüm (kişi)", "sayi"),
                ("Doğal artış (kişi)", "eksili"),
                ("Doğal artış hızı (‰)", "ondalik"),
            ],
            "rows": [
                [
                    str(year),
                    whole[year]["nufus"],
                    whole[year]["dogum"],
                    whole[year]["olum"],
                    whole[year]["artis"],
                    whole[year]["artis"] / whole[year]["nufus"] * 1000,
                ]
                for year in (FIRST, LAST)
            ],
        },
        {
            "title": "İlçelerin durumu",
            "note": f"{FIRST} ve {LAST} karşılaştırıldığında, doğal artışın işareti.",
            "columns": [
                ("Durum", "left"),
                ("İlçe sayısı", "sayi"),
                ("Pay (%)", "yuzde"),
            ],
            "rows": [
                [row["durum"], row["len"], row["len"] / ilceler.height]
                for row in ilceler.group_by("durum")
                .len()
                .sort("len", descending=True)
                .to_dicts()
            ],
        },
        {
            "title": f"{FIRST} · doğal artış hızı en yüksek 10 ilçe",
            **ranked(ilceler, f"artis_hiz_{FIRST}", place + both),
        },
        {
            "title": f"{LAST} · doğal artış hızı en yüksek 10 ilçe",
            **ranked(ilceler, f"artis_hiz_{LAST}", place + both),
        },
        {
            "title": f"{LAST} · doğal artış hızı en düşük 10 ilçe",
            **ranked(ilceler, f"artis_hiz_{LAST}", place + both, rising=False),
        },
        {
            "title": "Doğal artış hızı en çok düşen 10 il",
            "note": "İl düzeyinde; ilçelerin toplamından hesaplandı.",
            **ranked(
                iller,
                "artis_hiz_fark",
                [("il", "İl", "left")] + both,
                rising=False,
            ),
        },
        {
            "title": "Doğal artış hızı en az düşen (ya da artan) 10 il",
            **ranked(iller, "artis_hiz_fark", [("il", "İl", "left")] + both),
        },
        {
            "title": "Doğal artış hızı en çok düşen 10 ilçe",
            **ranked(ilceler, "artis_hiz_fark", place + both, rising=False),
        },
        {
            "title": "Doğal artış hızı en çok artan 10 ilçe",
            **ranked(ilceler, "artis_hiz_fark", place + both),
        },
        {
            "title": "Doğumu oran olarak en çok düşen 10 ilçe",
            **ranked(
                ilceler,
                "dogum_degisim",
                place
                + [
                    (f"dogum_{FIRST}", f"Doğum {FIRST} (kişi)", "sayi"),
                    (f"dogum_{LAST}", f"Doğum {LAST} (kişi)", "sayi"),
                    ("dogum_degisim", "Değişim (%)", "yuzde"),
                ],
                rising=False,
            ),
        },
    ]

    turned = ilceler.filter(pl.col("durum") == "eksiye döndü").height
    stayed = ilceler.filter(pl.col("durum") == "ekside kaldı").height
    back = ilceler.filter(pl.col("durum") == "artıya döndü").height
    write(
        COMPARISON,
        f"VeriAtlas — ilçelere göre doğal nüfus artışı · {FIRST} ↔ {LAST}",
        ozet,
        [("İlçeler", ilceler), ("İller", iller)],
        [
            f"VeriAtlas — ilçelere göre doğal nüfus artışı, {FIRST} ve {LAST}",
            "",
            "Kaynak: TÜİK MEDAS. Çekim: 2026-08.",
            "Doğal artış = doğum − ölüm. Her ikisi de ikametgah yerine göre.",
            "",
            f"NEDEN {FIRST}",
            "· İlçe düzeyinde doğum 2014'ten önce yayımlanmıyor. Ölüm 2009'a kadar var,",
            "  ama doğal artış iki tarafı birden istediği için başlangıç 2014.",
            "  Ölümün tamamı öteki dosyadadır (ilce-dogum-olum.xlsx).",
            "",
            "HIZ NEDİR",
            "· '‰' = olay sayısı ÷ o yılın yıl sonu nüfusu × 1000. Bizim bölmemizdir;",
            "  TÜİK kendi kaba hızlarında yıl ORTASI nüfusu kullanıyor, il düzeyinde",
            "  ölçülen fark 0,05-0,10 binde.",
            "· Kişi sayısı ile hız aynı soruyu sormuyor: kalabalık ilçenin artışı kişi",
            "  olarak büyük çıkar, hız o büyüklüğü bölerek karşılaştırılabilir yapar.",
            "",
            "YÜZDE SÜTUNLARI",
            "· Doğum, ölüm ve nüfus değişimi yüzde olarak verildi. Doğal artış için",
            "  yüzde YOK, bilerek: tabanı eksi olan bir sayının yüzdesi işareti ters",
            "  çevirir (−1.000'den −500'e çıkmak 'yüzde 50 düştü' diye okunurdu). Onun",
            "  yerine kişi farkı ve ‰ farkı var; ikisi de her tabanda doğrudur.",
            "",
            "DURUM SÜTUNU",
            f"· {FIRST}'te artıda olup {LAST}'te eksiye dönen ilçe: {turned}.",
            f"· İki yılda da eksi olan: {stayed}. Eksiden artıya dönen: {back}.",
            "",
            "TOPLAM",
            (
                f"· {FIRST}: {turkish(whole[FIRST]['artis'])} kişi doğal artış, "
                f"{turkish(whole[FIRST]['artis'] / whole[FIRST]['nufus'] * 1000, 2)}‰."
            ),
            (
                f"· {LAST}: {turkish(whole[LAST]['artis'])} kişi, "
                f"{turkish(whole[LAST]['artis'] / whole[LAST]['nufus'] * 1000, 2)}‰."
            ),
            "  (İlçelerin toplamı; il ve Türkiye sayılarıyla birebir tutuyor.)",
            "",
            "SÜTUNLAR",
            "· 'İl' sütunu ayırt etmek için: ilçe adı tek başına ilçeyi tanımlamaz,",
            "  onlarca 'Merkez' var. 'Kimlik' bizim alan kimliğimizdir (TR-34-023).",
            "· Kazan → Kahramankazan (2017) ve Eyüp → Eyüpsultan (2018) ad değiştirdi;",
            "  tek satır olarak, bugünkü adlarıyla duruyorlar.",
            "· 2014'ten sonra kurulan üç ilçe (Artvin/Kemalpaşa, Hakkari/Derecik,",
            "  Aksaray/Sultanhanı) listede duruyor ama 2014 sütunları boş — 'durum'",
            "  sütununda 'karşılaştırılamaz' yazıyor. Boş, sıfır değildir.",
        ],
    )


def main() -> None:
    mapping = renames()
    rows = folded(facts(), mapping)
    # The registry rows for the old names go with them: kept, they would be districts
    # with a name and no numbers.
    area = names().filter(~pl.col("area_id").is_in(list(mapping)))
    build_all_years(rows, area, mapping)
    build_comparison(rows, area)


if __name__ == "__main__":
    main()
