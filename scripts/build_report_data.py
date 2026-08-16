"""One JSON payload per area, for the report page to draw.

The report is **one page**, not a thousand: `web/rapor/` reads `#a=TR-34` and fetches that
area's payload. Generating a thousand HTML files would mean a thousand copies of the same
markup, and a change to a heading would be a thousand-file diff.

What goes in a payload is the *answer*, not the data: the page draws a life expectancy
line, it does not hold a life table and work one out. That keeps the arithmetic here —
next to the tests, in the language that has the fact table — and the page honest about
what it can and cannot claim.

Every section is optional. An area that has no death-by-age data has no mortality section
and the page says which level it would need, rather than drawing an empty frame. That is
the whole reason the payload names its sections instead of the page assuming them.

Run:  uv run python scripts/build_report_data.py            # Türkiye
      uv run python scripts/build_report_data.py TR-34 TR-06
      uv run python scripts/build_report_data.py --hepsi     # ülke + bölge + İBBS + il
"""

from __future__ import annotations

import json
import sys
from itertools import pairwise

import polars as pl

sys.path.insert(0, "src")

from veriatlas.areas import load_areas, load_parents
from veriatlas.config import PUBLIC

TARGET = PUBLIC / "rapor"

#: The three broad groups, and the single years that fall in each. Written as a rule
#: rather than a list because the population arrives as single years and the deaths as
#: bands, and the same three names have to come out of both.
BROAD = ("0-14", "15-64", "65+")

#: The death file's own bands, in age order. MEDAS's internal codes are not in age order,
#: so an axis built from the file's row order comes out shuffled.
DEATH_BANDS = (
    "0",
    "1-4",
    "5-9",
    "10-14",
    "15-19",
    "20-24",
    "25-29",
    "30-34",
    "35-39",
    "40-44",
    "45-49",
    "50-54",
    "55-59",
    "60-64",
    "65-69",
    "70-74",
    "75+",
)

MIGRATION_BANDS = (
    "0-4",
    "5-9",
    "10-14",
    "15-19",
    "20-24",
    "25-29",
    "30-34",
    "35-39",
    "40-44",
    "45-49",
    "50-54",
    "55-59",
    "60-64",
    "65+",
)

MARITAL_TR = {
    "never_married": "Hiç evlenmedi",
    "married": "Evli",
    "divorced": "Boşandı",
    "widowed": "Eşi öldü",
    "unknown": "Bilinmeyen",
}


def facts() -> pl.DataFrame:
    return pl.read_parquet(PUBLIC / "fact.parquet").with_columns(
        pl.col("period_start").dt.year().alias("y"),
        pl.col("dims").str.extract(r"age=([^;]+)").alias("age"),
        pl.col("dims").str.extract(r"sex=([^;]+)").alias("sex"),
        pl.col("dims").str.extract(r"marital=([^;]+)").alias("mar"),
    )


def single_years(frame: pl.DataFrame) -> pl.DataFrame:
    """Population rows that are a single year of age, plus the closing band.

    The filter matters: at province level the same indicator also carries `0-17` and
    `18+` at other levels, and summing a distribution together with a coarser reading of
    itself counts those people twice.
    """
    return frame.filter(
        (pl.col("indicator_id") == "population")
        & (pl.col("age").str.contains(r"^\d+$") | (pl.col("age") == "75+"))
    )


def broad_of(age: pl.Expr) -> pl.Expr:
    year = age.cast(pl.Int32, strict=False)
    return (
        pl.when(age == "75+")
        .then(pl.lit("65+"))
        .when(year < 15)
        .then(pl.lit("0-14"))
        .when(year < 65)
        .then(pl.lit("15-64"))
        .otherwise(pl.lit("65+"))
    )


def death_broad(age: pl.Expr) -> pl.Expr:
    return (
        pl.when(age.is_in(["0", "1-4", "5-9", "10-14"]))
        .then(pl.lit("0-14"))
        .when(age.is_in(["65-69", "70-74", "75+"]))
        .then(pl.lit("65+"))
        .otherwise(pl.lit("15-64"))
    )


def series(frame: pl.DataFrame, indicator_id: str) -> dict[int, float]:
    """Year → value, summed across whatever breakdown the indicator carries."""
    rows = (
        frame.filter(pl.col("indicator_id") == indicator_id)
        .group_by("y")
        .agg(pl.col("value").sum())
        .sort("y")
    )
    return {int(y): round(float(v), 4) for y, v in rows.iter_rows()}


def ranked(
    everything: pl.DataFrame, area_id: str, level: str, value: dict[str, float]
) -> dict | None:
    """Where this area stands among its siblings, and among how many.

    A rank is the one thing a report page cannot compute for itself — the page holds one
    area — and it is the first thing a reader asks. Ties take the same rank, so two
    provinces at 16,8% are both 3rd and nothing is 4th.
    """
    if level == "country" or not value:
        return None
    ordered = sorted(value.items(), key=lambda pair: -pair[1])
    for place, (key, _) in enumerate(ordered, start=1):
        if key == area_id:
            return {"sira": place, "icinde": len(ordered)}
    return None


# region Sections


def nufus(frame: pl.DataFrame) -> dict | None:
    """Population, and the two forces that move it: natural increase and the rest."""
    people = single_years(frame).group_by("y").agg(pl.col("value").sum()).sort("y")
    if people.is_empty():
        return None
    total = {int(y): int(v) for y, v in people.iter_rows()}
    natural = series(frame, "natural_increase")

    #: The change a year that natural increase does not account for. Migration is the
    #: name for most of it, but not all — the register is also corrected — so it is
    #: called what it is: the remainder.
    years = sorted(total)
    kalan = {}
    for before, after in pairwise(years):
        if after in natural:
            kalan[after] = int(total[after] - total[before] - natural[after])

    return {
        "toplam": total,
        "dogal": {y: int(v) for y, v in natural.items()},
        "kalan": kalan,
    }


def yas_yapisi(frame: pl.DataFrame) -> dict | None:
    """The pyramid, and the three broad groups over time."""
    people = single_years(frame)
    if people.is_empty():
        return None

    groups = (
        people.with_columns(broad_of(pl.col("age")).alias("g"))
        .group_by("y", "g")
        .agg(pl.col("value").sum())
        .sort("y")
    )
    paylar: dict[str, dict[int, float]] = {g: {} for g in BROAD}
    toplam = {
        int(y): float(v)
        for y, v in groups.group_by("y").agg(pl.col("value").sum()).iter_rows()
    }
    for y, g, v in groups.iter_rows():
        paylar[g][int(y)] = round(float(v) / toplam[int(y)] * 100, 2)

    # The pyramid in five-year bands: seventy-six single years is more bars than a
    # pyramid can show and more numbers than the payload should carry.
    year = pl.col("age").cast(pl.Int32, strict=False)
    band = (
        pl.when(pl.col("age") == "75+")
        .then(pl.lit("75+"))
        .otherwise(
            ((year // 5) * 5).cast(pl.String)
            + "-"
            + ((year // 5) * 5 + 4).cast(pl.String)
        )
    )
    piramit_rows = (
        people.with_columns(band.alias("b"))
        .group_by("y", "b", "sex")
        .agg(pl.col("value").sum())
    )
    piramit: dict[int, dict[str, dict[str, int]]] = {}
    for y, b, sex, v in piramit_rows.iter_rows():
        piramit.setdefault(int(y), {}).setdefault(b, {})[sex] = int(v)

    ortanca = (
        frame.filter(
            (pl.col("indicator_id") == "median_age") & (pl.col("sex") == "total")
        )
        .select("y", "value")
        .sort("y")
    )
    return {
        "paylar": paylar,
        "piramit": piramit,
        "bantlar": [
            b
            for b in sorted(
                {b for yil in piramit.values() for b in yil},
                key=lambda s: int(s.split("-")[0].rstrip("+")),
            )
        ],
        "ortanca_yas": {int(y): round(float(v), 1) for y, v in ortanca.iter_rows()},
    }


def olumluluk(frame: pl.DataFrame, standard: pl.DataFrame) -> dict | None:
    """Crude against age-standardised, and the excess over a fixed-mortality baseline.

    The standard population is Türkiye's own 2009 distribution, passed in rather than
    computed per area: a rate standardised to a different population in every province is
    not comparable between provinces, which is the entire point of standardising.
    """
    deaths = frame.filter(
        (pl.col("indicator_id") == "deaths_by_age") & (pl.col("age") != "unknown")
    )
    if deaths.is_empty():
        return None

    year = pl.col("age").cast(pl.Int32, strict=False)
    band = (
        pl.when(pl.col("age") == "75+")
        .then(pl.lit("75+"))
        .when(year == 0)
        .then(pl.lit("0"))
        .when(year < 5)
        .then(pl.lit("1-4"))
        .otherwise(
            ((year // 5) * 5).cast(pl.String)
            + "-"
            + ((year // 5) * 5 + 4).cast(pl.String)
        )
    )
    people = (
        single_years(frame)
        .with_columns(band.alias("b"))
        .group_by("y", "b", "sex")
        .agg(pl.col("value").sum().alias("p"))
    )
    counts = deaths.group_by("y", pl.col("age").alias("b"), "sex").agg(
        pl.col("value").sum().alias("d")
    )
    paired = counts.join(people, on=["y", "b", "sex"], how="inner").filter(
        pl.col("p") > 0
    )
    if paired.is_empty():
        return None

    weight = standard["sp"].sum()
    std = (
        paired.join(standard, on=["b", "sex"], how="inner")
        .group_by("y")
        .agg((pl.col("d") * pl.col("sp") / pl.col("p")).sum() / weight * 1000)
        .sort("y")
    )
    crude = (
        paired.group_by("y")
        .agg(
            (pl.col("d").sum() / pl.col("p").sum() * 1000).alias("kaba"),
            pl.col("d").sum().alias("olum"),
        )
        .sort("y")
    )

    # Excess: the last pre-pandemic year's own rates, applied to each year's people.
    # Not a forecast — a counterfactual, and it says which year it holds still.
    base_year = 2019
    base = paired.filter(pl.col("y") == base_year).select(
        "b", "sex", (pl.col("d") / pl.col("p")).alias("r")
    )
    excess = (
        paired.join(base, on=["b", "sex"], how="inner")
        .group_by("y")
        .agg(
            (pl.col("p") * pl.col("r")).sum().alias("beklenen"),
            pl.col("d").sum().alias("gerceklesen"),
        )
        .sort("y")
    )

    broad = (
        paired.with_columns(death_broad(pl.col("b")).alias("g"))
        .group_by("y", "g")
        .agg((pl.col("d").sum() / pl.col("p").sum() * 1000).alias("h"))
    )
    gruplar: dict[str, dict[int, float]] = {g: {} for g in BROAD}
    for y, g, h in broad.iter_rows():
        gruplar[g][int(y)] = round(float(h), 2)

    return {
        "kaba": {int(y): round(float(k), 2) for y, k, _ in crude.iter_rows()},
        "sayi": {int(y): int(o) for y, _, o in crude.iter_rows()},
        "standart": {int(y): round(float(v), 2) for y, v in std.iter_rows()},
        "standart_yil": 2009,
        "gruplar": gruplar,
        "fazla_taban": base_year,
        "fazla": {
            int(y): {"beklenen": round(b), "gerceklesen": g}
            for y, b, g in excess.iter_rows()
        },
    }


def dogurganlik(frame: pl.DataFrame) -> dict | None:
    """Births, and births per thousand women of childbearing age.

    Both, never only the first: the count falls while the number of women rises, so the
    two tell different stories and only together tell the true one.
    """
    births = series(frame, "births")
    if not births:
        return None
    year = pl.col("age").cast(pl.Int32, strict=False)
    women = (
        single_years(frame)
        .filter((pl.col("sex") == "female") & (year >= 15) & (year <= 49))
        .group_by("y")
        .agg(pl.col("value").sum())
        .sort("y")
    )
    kadin = {int(y): float(v) for y, v in women.iter_rows()}
    gfr = {y: round(births[y] / kadin[y] * 1000, 2) for y in births if kadin.get(y)}
    return {
        "dogum": {y: int(v) for y, v in births.items()},
        "kadin_15_49": {y: int(v) for y, v in kadin.items()},
        "gdh": gfr,
        "tfr": {y: round(v, 2) for y, v in series(frame, "tfr").items()},
        "bebek_olum": {
            y: round(v, 1) for y, v in series(frame, "infant_mortality").items()
        },
    }


def yasam_suresi(frame: pl.DataFrame) -> dict | None:
    rows = frame.filter(pl.col("indicator_id") == "life_expectancy")
    if rows.is_empty():
        return None
    out: dict[str, dict[str, dict[int, float]]] = {}
    for age, sex, y, value in rows.select("age", "sex", "y", "value").iter_rows():
        out.setdefault(age, {}).setdefault(sex, {})[int(y)] = round(float(value), 1)
    # Only the two ages a reader asks for; the life table's hundred others stay in the
    # warehouse rather than in every payload.
    return {age: out[age] for age in ("0", "65") if age in out} or None


def goc(frame: pl.DataFrame) -> dict | None:
    """Who arrives and who leaves, by age. The answer to a shrinking population."""
    disaridan = series(frame, "migration_from_abroad")
    disariya = series(frame, "migration_to_abroad")
    rows = frame.filter(
        pl.col("indicator_id").is_in(["migration_in_by_age", "migration_out_by_age"])
    )
    if rows.is_empty():
        # Türkiye has no internal migration by definition — a move between provinces is
        # not a move into the country — so at country level the section is the
        # international flow instead of an empty frame where the age profile would be.
        if not disaridan:
            return None
        return {
            "yurtdisi": {
                "gelen": {y: int(v) for y, v in disaridan.items()},
                "giden": {y: int(v) for y, v in disariya.items()},
            }
        }
    by_age = (
        rows.group_by("indicator_id", "y", "age").agg(pl.col("value").sum()).sort("y")
    )
    gelen: dict[int, dict[str, int]] = {}
    giden: dict[int, dict[str, int]] = {}
    for ind, y, age, v in by_age.iter_rows():
        hedef = gelen if ind == "migration_in_by_age" else giden
        hedef.setdefault(int(y), {})[age] = int(v)
    return {
        "gelen": gelen,
        "giden": giden,
        "bantlar": list(MIGRATION_BANDS),
        "net": {y: int(v) for y, v in series(frame, "migration_net").items()},
        "yurtdisi": {
            "gelen": {y: int(v) for y, v in disaridan.items()},
            "giden": {y: int(v) for y, v in disariya.items()},
        },
    }


def evlilik(frame: pl.DataFrame) -> dict | None:
    marriages = series(frame, "marriages")
    if not marriages:
        return None
    people = single_years(frame).group_by("y").agg(pl.col("value").sum())
    total = {int(y): float(v) for y, v in people.iter_rows()}
    divorces = series(frame, "divorces")

    ages: dict[str, dict[int, float]] = {}
    for sex, y, v in (
        frame.filter(pl.col("indicator_id") == "mean_first_marriage_age")
        .select("sex", "y", "value")
        .iter_rows()
    ):
        ages.setdefault(sex, {})[int(y)] = round(float(v), 1)

    marital = frame.filter(pl.col("indicator_id") == "marital_status")
    paylar: dict[str, dict[str, dict[int, float]]] = {}
    if not marital.is_empty():
        counts = marital.group_by("y", "mar", "sex").agg(pl.col("value").sum())
        totals = {
            (int(y), sex): float(v)
            for y, sex, v in counts.group_by("y", "sex")
            .agg(pl.col("value").sum())
            .iter_rows()
        }
        for y, mar, sex, v in counts.iter_rows():
            paylar.setdefault(sex, {}).setdefault(MARITAL_TR[mar], {})[int(y)] = round(
                float(v) / totals[(int(y), sex)] * 100, 2
            )

    return {
        "evlenme": {y: int(v) for y, v in marriages.items()},
        "bosanma": {y: int(v) for y, v in divorces.items()},
        "evlenme_hizi": {
            y: round(v / total[y] * 1000, 2)
            for y, v in marriages.items()
            if total.get(y)
        },
        "bosanma_hizi": {
            y: round(v / total[y] * 1000, 2)
            for y, v in divorces.items()
            if total.get(y)
        },
        "ilk_evlenme_yasi": ages,
        "medeni_pay": paylar,
    }


def hane(frame: pl.DataFrame) -> dict | None:
    size = series(frame, "household_size")
    if not size:
        return None
    return {
        "buyukluk": {y: round(v, 2) for y, v in size.items()},
        "sayi": {y: int(v) for y, v in series(frame, "household_count").items()},
    }


# endregion


def standard_population(fact: pl.DataFrame) -> pl.DataFrame:
    """Türkiye's 2009 age-sex distribution, in the death file's bands.

    One standard for every area, so two provinces' standardised rates mean the same
    thing. Standardising each area to itself would produce eighty-one numbers that
    cannot be put on one map.
    """
    country = fact.filter(pl.col("area_level") == "country")
    year = pl.col("age").cast(pl.Int32, strict=False)
    band = (
        pl.when(pl.col("age") == "75+")
        .then(pl.lit("75+"))
        .when(year == 0)
        .then(pl.lit("0"))
        .when(year < 5)
        .then(pl.lit("1-4"))
        .otherwise(
            ((year // 5) * 5).cast(pl.String)
            + "-"
            + ((year // 5) * 5 + 4).cast(pl.String)
        )
    )
    return (
        single_years(country)
        .filter(pl.col("y") == 2009)
        .with_columns(band.alias("b"))
        .group_by("b", "sex")
        .agg(pl.col("value").sum().alias("sp"))
    )


def payload(fact: pl.DataFrame, standard: pl.DataFrame, area: dict) -> dict:
    frame = fact.filter(pl.col("area_id") == area["area_id"])
    sections = {
        "nufus": nufus(frame),
        "yas": yas_yapisi(frame),
        "olum": olumluluk(frame, standard),
        "dogurganlik": dogurganlik(frame),
        "yasam": yasam_suresi(frame),
        "goc": goc(frame),
        "evlilik": evlilik(frame),
        "hane": hane(frame),
    }
    return {
        "alan": area,
        "bolumler": {name: body for name, body in sections.items() if body},
        "eksik": [name for name, body in sections.items() if not body],
    }


#: The measures a province is ranked on, and which direction is better where a direction
#: exists at all. `yon` is None for the ones that have no better: a high share of over-65s
#: is not a good or a bad thing, it is a fact about a place, and colouring it like a score
#: would be the page inventing a judgement the data does not carry.
SIRALAMALAR = [
    ("nufus", "Nüfus", "kişi", None, 0),
    ("nufus_degisim", "Nüfus değişimi", "%", None, 1),
    ("yasli_pay", "65+ payı", "%", None, 2),
    ("cocuk_pay", "0-14 payı", "%", None, 2),
    ("ortanca_yas", "Ortanca yaş", "yaş", None, 1),
    ("gdh", "Genel doğurganlık hızı", "‰", None, 1),
    ("olum_standart", "Standartlaştırılmış ölüm hızı", "‰", "dusuk", 2),
    ("olum_65", "65+ ölüm hızı", "‰", "dusuk", 2),
    ("olum_0_14", "0-14 ölüm hızı", "‰", "dusuk", 2),
    ("yasam_kadin", "Doğuşta yaşam süresi, kadın", "yıl", "yuksek", 1),
    ("yasam_erkek", "Doğuşta yaşam süresi, erkek", "yıl", "yuksek", 1),
    ("evlenme_hizi", "Kaba evlenme hızı", "‰", None, 2),
    ("bosanma_hizi", "Kaba boşanma hızı", "‰", None, 2),
    ("hane_buyuklugu", "Ortalama hanehalkı", "kişi", None, 2),
]


def son_deger(nesne) -> float | None:
    if not nesne:
        return None
    return nesne[max(nesne)]


def siralama_dosyasi(paketler: dict[str, dict]) -> dict:
    """One file with every province's last-year value for every ranked measure.

    Shared rather than copied into each payload: a rank is a statement about the set, and
    the set is the same for all eighty-one pages. The page computes the rank and the top
    and bottom five from this, so those lists cannot disagree between two pages.
    """
    olcutler = {}
    for anahtar, ad, birim, yon, basamak in SIRALAMALAR:
        degerler = {}
        for area_id, paket in paketler.items():
            if paket["alan"]["duzey"] != "province":
                continue
            deger = olcut_degeri(anahtar, paket["bolumler"])
            if deger is not None:
                degerler[area_id] = round(deger, basamak)
        if degerler:
            olcutler[anahtar] = {
                "ad": ad,
                "birim": birim,
                "yon": yon,
                "basamak": basamak,
                "deger": degerler,
            }
    return olcutler


def olcut_degeri(anahtar: str, b: dict) -> float | None:
    """One measure's last published value, or None where the area does not have it."""
    if anahtar == "nufus":
        return son_deger(b.get("nufus", {}).get("toplam"))
    if anahtar == "nufus_degisim":
        toplam = b.get("nufus", {}).get("toplam")
        if not toplam:
            return None
        yillar = sorted(toplam)
        return (toplam[yillar[-1]] / toplam[yillar[0]] - 1) * 100
    if anahtar == "yasli_pay":
        return son_deger(b.get("yas", {}).get("paylar", {}).get("65+"))
    if anahtar == "cocuk_pay":
        return son_deger(b.get("yas", {}).get("paylar", {}).get("0-14"))
    if anahtar == "ortanca_yas":
        return son_deger(b.get("yas", {}).get("ortanca_yas"))
    if anahtar == "gdh":
        return son_deger(b.get("dogurganlik", {}).get("gdh"))
    if anahtar == "olum_standart":
        return son_deger(b.get("olum", {}).get("standart"))
    if anahtar == "olum_65":
        return son_deger(b.get("olum", {}).get("gruplar", {}).get("65+"))
    if anahtar == "olum_0_14":
        return son_deger(b.get("olum", {}).get("gruplar", {}).get("0-14"))
    if anahtar == "yasam_kadin":
        return son_deger(b.get("yasam", {}).get("0", {}).get("female"))
    if anahtar == "yasam_erkek":
        return son_deger(b.get("yasam", {}).get("0", {}).get("male"))
    if anahtar == "evlenme_hizi":
        return son_deger(b.get("evlilik", {}).get("evlenme_hizi"))
    if anahtar == "bosanma_hizi":
        return son_deger(b.get("evlilik", {}).get("bosanma_hizi"))
    if anahtar == "hane_buyuklugu":
        return son_deger(b.get("hane", {}).get("buyukluk"))
    return None


def main() -> None:
    fact = facts()
    standard = standard_population(fact)

    areas = load_areas()
    parents = load_parents()
    lookup = {
        row["area_id"]: row
        for row in areas.join(parents, on="area_id", how="left").to_dicts()
    }

    wanted = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    if "--hepsi" in sys.argv:
        wanted = [
            row["area_id"]
            for row in areas.to_dicts()
            if row["area_level"] in ("country", "province", "region", "nuts1")
        ]
    if not wanted:
        wanted = ["TR"]

    TARGET.mkdir(parents=True, exist_ok=True)
    paketler: dict[str, dict] = {}
    for area_id in wanted:
        row = lookup.get(area_id)
        if row is None:
            raise SystemExit("bilinmeyen alan: " + area_id)
        body = payload(
            fact,
            standard,
            {
                "area_id": area_id,
                "ad": row["name_tr"],
                "duzey": row["area_level"],
            },
        )
        paketler[area_id] = body
        path = TARGET / (area_id + ".json")
        path.write_text(
            json.dumps(body, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        print(
            "yazildi:",
            path.name,
            len(body["bolumler"]),
            "bolum",
            round(path.stat().st_size / 1024),
            "KB",
            ("eksik: " + ", ".join(body["eksik"]) if body["eksik"] else ""),
        )

    # The menu the page offers is the list of payloads that exist, not the registry: a
    # menu naming a thousand areas would offer nine hundred pages nobody has written.
    dizin = sorted(
        (
            {
                "area_id": path.stem,
                "ad": lookup[path.stem]["name_tr"],
                "duzey": lookup[path.stem]["area_level"],
            }
            for path in TARGET.glob("*.json")
            if path.stem in lookup
        ),
        key=lambda row: (
            ["country", "region", "nuts1", "nuts2", "province", "district"].index(
                row["duzey"]
            ),
            row["ad"],
        ),
    )
    # Rankings need every province in one run; a partial run would rank a province among
    # the three that happened to be rebuilt, so the file is only rewritten when the run
    # covered them all.
    iller = [row for row in dizin if row["duzey"] == "province"]
    if (
        len(iller)
        == len([p for p in paketler.values() if p["alan"]["duzey"] == "province"])
        and len(iller) >= 81
    ):
        olcutler = siralama_dosyasi(paketler)
        (TARGET / "siralama.json").write_text(
            json.dumps(olcutler, ensure_ascii=False), encoding="utf-8"
        )
        print("siralama:", len(olcutler), "olcut ×", len(iller), "il")

    (TARGET / "dizin.json").write_text(
        json.dumps(dizin, ensure_ascii=False), encoding="utf-8"
    )
    print("dizin  :", len(dizin), "alan")


if __name__ == "__main__":
    main()
