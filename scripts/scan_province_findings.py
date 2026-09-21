import sys

sys.path.insert(0, "src")
import json

import polars as pl

from veriatlas.areas import load_areas

nm = load_areas().select("area_id", pl.col("name_tr").alias("il"))
f = (
    pl.read_parquet("public/fact.parquet")
    .filter(pl.col("area_level") == "province")
    .with_columns(
        pl.col("period_start").dt.year().alias("y"),
        pl.col("dims").str.extract(r"age=([^;]+)").alias("age"),
        pl.col("dims").str.extract(r"sex=([^;]+)").alias("sex"),
    )
)
P = lambda i: f.filter(pl.col("indicator_id") == i)
yr = pl.col("age").cast(pl.Int32, strict=False)
pop = P("population").filter(
    pl.col("age").str.contains(r"^\d+$") | (pl.col("age") == "75+")
)
tot = pop.group_by("area_id", "y").agg(pl.col("value").sum().alias("n"))


def yaz(baslik, frame, n=6):
    print("\n== " + baslik)
    for row in frame.head(n).join(nm, on="area_id", how="left").to_dicts():
        print(
            "  ",
            json.dumps(
                {
                    k: (round(v, 2) if isinstance(v, float) else v)
                    for k, v in row.items()
                    if k != "area_id"
                },
                ensure_ascii=False,
            ),
        )


# 1. Genç göçü: 20-29 yaş net göç, o yaştaki nüfusa oranla
gelen = P("migration_in_by_age").filter(pl.col("age").is_in(["20-24", "25-29"]))
giden = P("migration_out_by_age").filter(pl.col("age").is_in(["20-24", "25-29"]))
g = gelen.group_by("area_id", "y").agg(pl.col("value").sum().alias("gelen"))
k = giden.group_by("area_id", "y").agg(pl.col("value").sum().alias("giden"))
genc_nufus = (
    pop.filter((yr >= 20) & (yr <= 29))
    .group_by("area_id", "y")
    .agg(pl.col("value").sum().alias("p"))
)
genc = (
    g.join(k, on=["area_id", "y"])
    .join(genc_nufus, on=["area_id", "y"])
    .with_columns(
        ((pl.col("gelen") - pl.col("giden")) / pl.col("p") * 1000).alias("net_binde")
    )
    .filter(pl.col("y") >= 2019)
    .group_by("area_id")
    .agg(pl.col("net_binde").mean().round(1).alias("yillik_net_binde"))
)
yaz(
    "20-29 yasta net goc, binde (2019-2025 ortalamasi) - EN COK KAYBEDEN",
    genc.sort("yillik_net_binde"),
)
yaz("... EN COK KAZANAN", genc.sort("yillik_net_binde", descending=True))

# 2. Gidenin cinsiyeti
cins = (
    P("migration_out_by_age")
    .filter(pl.col("y") >= 2019)
    .group_by("area_id", "sex")
    .agg(pl.col("value").sum())
    .pivot(values="value", index="area_id", on="sex")
    .with_columns(
        (pl.col("male") / pl.col("female") * 100).round(1).alias("erkek_yuz_kadin")
    )
)
yaz(
    "Gidenlerde erkek/100 kadin - EN ERKEK",
    cins.sort("erkek_yuz_kadin", descending=True).select("area_id", "erkek_yuz_kadin"),
)
yaz("... EN KADIN", cins.sort("erkek_yuz_kadin").select("area_id", "erkek_yuz_kadin"))

# 3. Standartlastirilmis olum hizi ve kaba hiz sirasi farki
band = (
    pl.when(pl.col("age") == "75+")
    .then(pl.lit("75+"))
    .when(yr == 0)
    .then(pl.lit("0"))
    .when(yr < 5)
    .then(pl.lit("1-4"))
    .otherwise(
        ((yr // 5) * 5).cast(pl.String) + "-" + ((yr // 5) * 5 + 4).cast(pl.String)
    )
)
p2 = (
    pop.with_columns(band.alias("b"))
    .group_by("area_id", "y", "b", "sex")
    .agg(pl.col("value").sum().alias("p"))
)
d = (
    P("deaths_by_age")
    .filter(pl.col("age") != "unknown")
    .group_by("area_id", "y", pl.col("age").alias("b"), "sex")
    .agg(pl.col("value").sum().alias("d"))
)
m = d.join(p2, on=["area_id", "y", "b", "sex"]).filter(pl.col("p") > 0)
std_pop = (
    pl.read_parquet("public/fact.parquet")
    .filter(
        (pl.col("area_level") == "country") & (pl.col("indicator_id") == "population")
    )
    .with_columns(
        pl.col("period_start").dt.year().alias("y"),
        pl.col("dims").str.extract(r"age=([^;]+)").alias("age"),
        pl.col("dims").str.extract(r"sex=([^;]+)").alias("sex"),
    )
    .filter(
        (pl.col("y") == 2009)
        & (pl.col("age").str.contains(r"^\d+$") | (pl.col("age") == "75+"))
    )
    .with_columns(band.alias("b"))
    .group_by("b", "sex")
    .agg(pl.col("value").sum().alias("sp"))
)
agirlik = std_pop["sp"].sum()
son = m.filter(pl.col("y") == 2025)
std = (
    son.join(std_pop, on=["b", "sex"])
    .group_by("area_id")
    .agg(
        ((pl.col("d") * pl.col("sp") / pl.col("p")).sum() / agirlik * 1000)
        .round(2)
        .alias("standart")
    )
)
kaba = son.group_by("area_id").agg(
    (pl.col("d").sum() / pl.col("p").sum() * 1000).round(2).alias("kaba")
)
ikisi = std.join(kaba, on="area_id")
ikisi = ikisi.with_columns(
    pl.col("kaba").rank(descending=True).cast(pl.Int32).alias("kaba_sira"),
    pl.col("standart").rank(descending=True).cast(pl.Int32).alias("std_sira"),
).with_columns((pl.col("kaba_sira") - pl.col("std_sira")).alias("sira_farki"))
yaz(
    "Kaba hizda yuksek, standartta dusuk (yaslanma yaniltiyor)",
    ikisi.sort("sira_farki", descending=True).select(
        "area_id", "kaba", "standart", "kaba_sira", "std_sira", "sira_farki"
    ),
)
yaz(
    "Tersi: kaba dusuk ama gercek olumluluk yuksek",
    ikisi.sort("sira_farki").select(
        "area_id", "kaba", "standart", "kaba_sira", "std_sira", "sira_farki"
    ),
)

# 4. Pandemi fazla olumu, ile gore
base = m.filter(pl.col("y") == 2019).select(
    "area_id", "b", "sex", (pl.col("d") / pl.col("p")).alias("r")
)
fazla = (
    m.filter(pl.col("y").is_in([2020, 2021]))
    .join(base, on=["area_id", "b", "sex"])
    .group_by("area_id")
    .agg(
        (pl.col("d").sum()).alias("gercek"),
        (pl.col("p") * pl.col("r")).sum().alias("beklenen"),
    )
    .with_columns(
        ((pl.col("gercek") / pl.col("beklenen") - 1) * 100)
        .round(1)
        .alias("fazla_yuzde"),
        (pl.col("gercek") - pl.col("beklenen")).round(0).alias("fazla_kisi"),
    )
)
yaz(
    "2020-21 fazla olum, % - EN AGIR",
    fazla.sort("fazla_yuzde", descending=True).select(
        "area_id", "fazla_yuzde", "fazla_kisi"
    ),
)
yaz(
    "... EN HAFIF",
    fazla.sort("fazla_yuzde").select("area_id", "fazla_yuzde", "fazla_kisi"),
)

# 5. Yasam suresi makasi
ys = P("life_expectancy").filter(pl.col("age") == "0")
sonyil = ys["y"].max()
ys = ys.filter(pl.col("y") == sonyil).pivot(values="value", index="area_id", on="sex")
ys = ys.with_columns((pl.col("female") - pl.col("male")).round(1).alias("makas"))
yaz(
    f"Dogusta yasam suresi {sonyil} - EN UZUN (kadin)",
    ys.sort("female", descending=True),
)
yaz("... EN KISA (erkek)", ys.sort("male"))
yaz("Kadin-erkek makasi EN GENIS", ys.sort("makas", descending=True))
yaz("... EN DAR", ys.sort("makas"))

# 6. Cocuk nufusu
cocuk = (
    pop.filter(yr < 15).group_by("area_id", "y").agg(pl.col("value").sum().alias("c"))
)
c2 = (
    cocuk.filter(pl.col("y") == 2007)
    .select("area_id", pl.col("c").alias("c07"))
    .join(
        cocuk.filter(pl.col("y") == 2025).select("area_id", pl.col("c").alias("c25")),
        on="area_id",
    )
)
c2 = c2.with_columns(
    ((pl.col("c25") / pl.col("c07") - 1) * 100).round(1).alias("degisim")
)
yaz("0-14 nufusu en cok DUSEN", c2.sort("degisim"))
yaz("0-14 nufusu ARTAN", c2.sort("degisim", descending=True))

# 7. Bosanma ve ilk evlenme yasi
ev = P("divorces").group_by("area_id", "y").agg(pl.col("value").sum().alias("b"))
ev = ev.join(tot, on=["area_id", "y"]).with_columns(
    (pl.col("b") / pl.col("n") * 1000).round(2).alias("hiz")
)
yaz(
    "Kaba bosanma hizi 2025 - EN YUKSEK",
    ev.filter(pl.col("y") == 2025)
    .sort("hiz", descending=True)
    .select("area_id", "hiz"),
)
yaz("... EN DUSUK", ev.filter(pl.col("y") == 2025).sort("hiz").select("area_id", "hiz"))

iev = (
    P("mean_first_marriage_age")
    .filter(pl.col("y") == 2025)
    .pivot(values="value", index="area_id", on="sex")
)
iev = iev.with_columns((pl.col("male") - pl.col("female")).round(1).alias("yas_farki"))
yaz("Ilk evlenme yasi 2025, kadin EN GENC", iev.sort("female"))
yaz("Es yas farki EN BUYUK", iev.sort("yas_farki", descending=True))

# 8. Hanehalki
hh = (
    P("household_size")
    .filter(pl.col("y") == 2025)
    .select("area_id", pl.col("value").round(2).alias("hane"))
)
yaz("Ortalama hanehalki 2025 - EN BUYUK", hh.sort("hane", descending=True))
yaz("... EN KUCUK", hh.sort("hane"))
