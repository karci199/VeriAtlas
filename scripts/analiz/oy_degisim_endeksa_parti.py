import glob
import json
import re
import sys

import numpy as np

sys.path.insert(0, "scripts")
from parse_secim import fold

T = "public/tiles/"


def load(v):
    out = {}
    for f in glob.glob(T + f"secim-{v}-mahalle-TR-*.json"):
        out.update(json.load(open(f, encoding="utf-8")))
    return out


a = load("mv2015k")
b = load("mv2023")
B = {
    "akp": (r"^AK PART", r"^AK PART"),
    "chp": (r"^CHP$", r"^CHP$"),
    "mhp": (r"^MHP$", r"^MHP$"),
    "hdp": (r"^HDP$", r"^YE[ŞS][İI]L SOL"),
}


def sh(r, p):
    return (
        100
        * sum(n for c, n in r["v"].items() if re.search(p, c, re.IGNORECASE))
        / r["g"]
        if r.get("g")
        else None
    )


# endeksa by (district, folded name)
E = {}
for f in glob.glob("C:/veri-ham/endeksa/demography/TR-*.json"):
    dist = f.split("\\")[-1].split("/")[-1][:-5]
    for code, rec in json.load(open(f, encoding="utf-8")).items():
        E.setdefault((dist, fold(rec["name_tr"])), rec["demography"])
rows = []
for k in a:
    if k not in b or "~" in k:
        continue
    ra, rb = a[k], b[k]
    if (ra.get("k") or 0) < 300 or (rb.get("k") or 0) < 300:
        continue
    d = E.get((k[:9], fold(rb.get("ad", ""))))
    if not d or not d.get("PopulationTotal"):
        continue
    edu = d.get("EducationTotal") or 0
    pop = d["PopulationTotal"]
    mar = (
        (d.get("MarriedNever") or 0)
        + (d.get("Married") or 0)
        + (d.get("Divorced") or 0)
        + (d.get("Widow") or 0)
    )
    uni = (
        (
            (d.get("EduLicenseDegree") or 0)
            + (d.get("EduGraduate") or 0)
            + (d.get("EduDoctorate") or 0)
        )
        / edu
        * 100
        if edu
        else np.nan
    )
    low = (
        (
            (d.get("EduNonLiterated") or 0)
            + (d.get("EduLiteratedUntutored") or 0)
            + (d.get("EduPrimarySchool") or 0)
        )
        / edu
        * 100
        if edu
        else np.nan
    )
    rows.append(
        dict(
            id=k,
            ad=rb["ad"],
            il=k[:5],
            secmen=rb["k"],
            **{f"d_{p}": sh(rb, y) - sh(ra, x) for p, (x, y) in B.items()},
            cumhur15=sh(ra, B["akp"][0]),
            nufus=pop,
            universite=uni,
            dusuk_egitim=low,
            yasli=d.get("PopulationElderRatio"),
            genc=d.get("PopulationYoungRatio"),
            evli=(d.get("Married") or 0) / mar * 100 if mar else np.nan,
            bekar=(d.get("MarriedNever") or 0) / mar * 100 if mar else np.nan,
            boşanmış=(d.get("Divorced") or 0) / mar * 100 if mar else np.nan,
            ses_ab=d.get("SesGroupABRatio"),
            gelir=d.get("HouseIncome"),
            kira=d.get("RentedShare"),
            konut_m2=d.get("HouseUnitPriceForSale"),
            belediye=1 if d.get("IsMunicipality") else 0,
            koy=1 if "KÖY" in (d.get("DistrictType") or "") else 0,
        )
    )
print("eslesen mahalle:", len(rows), "/ ortak", sum(1 for k in a if k in b))
import polars as pl

df = pl.DataFrame(rows).fill_nan(None)

pl.Config.set_tbl_rows(40)
pl.Config.set_tbl_cols(20)
pl.Config.set_tbl_width_chars(250)


def wm(c):
    return (
        (
            (pl.col(c) * pl.col("secmen")).sum()
            / pl.col("secmen").filter(pl.col(c).is_not_null()).sum()
        )
        .round(2)
        .alias(c)
    )


print(df.select(wm("d_akp"), wm("d_chp"), wm("d_mhp"), wm("d_hdp")))
for var in ["universite", "ses_ab", "genc", "kira"]:
    x = df.filter(pl.col(var).is_not_null()).with_columns(
        ((pl.col(var).rank("ordinal") - 1) * 10 / pl.len())
        .floor()
        .cast(pl.Int32)
        .alias("dilim")
        + 1
    )
    print(f"## {var} (1=en dusuk)")
    print(
        x.group_by("dilim")
        .agg(
            pl.col(var).min().round(1).alias("alt"),
            pl.col(var).max().round(1).alias("ust"),
            wm("d_akp"),
            wm("d_chp"),
            wm("d_mhp"),
            wm("d_hdp"),
            pl.len().alias("n"),
        )
        .sort("dilim")
    )

print("## korelasyon")
for t in ["d_akp", "d_chp", "d_mhp", "d_hdp"]:
    print(
        t,
        {
            v: round(df.drop_nulls([t, v]).select(pl.corr(t, v)).item(), 2)
            for v in [
                "universite",
                "dusuk_egitim",
                "yasli",
                "genc",
                "bekar",
                "ses_ab",
                "gelir",
                "kira",
                "cumhur15",
            ]
        },
    )
