"""One row per neighbourhood: ADNKS 2024 counts from the Endeksa dump + 2023 general election.

Demography: C:/veri-ham/endeksa/demography/TR-*.json (research copy, not for publication).
Only the ADNKS-derived counts are used (population, sex, age bands, marital status,
education); Endeksa's model fields are left out. Age bands are kept only where they add
up to the population within 2 % (docs/endeksa.md: they often do not).

Election: public/tiles/secim-mv2023-mahalle-TR-<plate>.json, keyed
TR-<plate>-<district>-<Endeksa neighbourhood id>. k registered, o voted, g valid.
A place where more voted than were registered holds an institution's ballot box (prison,
barracks); `institutional` marks it (memory: cezaevi-sandiklari).

Run from the main checkout root. Output: C:/veri-ham/analiz/mahalle_sapma/table.parquet.
"""

import glob
import json
import re
from pathlib import Path

import polars as pl

DEMO = "C:/veri-ham/endeksa/demography/TR-*.json"
TILES = Path("public/tiles")
OUT = Path("C:/veri-ham/analiz/mahalle_sapma")

AGES = [
    "0_4", "5_9", "10_14", "15_19", "20_24", "25_29", "30_34",
    "35_39", "40_44", "45_49", "50_54", "55_59", "60_64", "65",
]  # fmt: skip
EDU = {
    "illiterate": ["EduNonLiterated"],
    "no_school": ["EduLiteratedUntutored"],
    "primary": ["EduPrimarySchool", "EduPrimaryEducation"],
    "middle": ["EduMiddleSchool"],
    "high": ["EduHighSchool"],
    "university": ["EduLicenseDegree", "EduGraduate", "EduDoctorate"],
}
MARITAL = {
    "never": "MarriedNever",
    "married": "Married",
    "divorced": "Divorced",
    "widowed": "Widow",
}
PARTIES = {
    "akp": ["AK PARTİ"],
    "chp": ["CHP"],
    "mhp": ["MHP"],
    "iyi": ["İYİ PARTİ"],
    "ysp": ["YEŞİL SOL PARTİ"],
    "yrp": ["YENİDEN REFAH"],
    "zafer": ["ZAFER PARTİSİ"],
    "tip": ["TİP"],
    "bbp": ["BÜYÜK BİRLİK"],
}


def demography() -> pl.DataFrame:
    rows = []
    for path in sorted(glob.glob(DEMO)):
        plate, county = re.search(r"TR-(\d+)-(\d+)", path).groups()
        for mid, rec in json.load(open(path, encoding="utf-8")).items():
            d = rec.get("demography") or {}
            pop = d.get("PopulationTotal") or 0
            if not pop:
                continue
            ages = {a: d.get(f"Age_{a}_Total") or 0 for a in AGES}
            age_ok = abs(sum(ages.values()) - pop) <= 0.02 * pop
            r = {
                "plate": plate,
                "county": county,
                "id": mid,
                "name": rec.get("name_tr"),
                "pop": pop,
                "male": d.get("PopulationMale") or 0,
                "female": d.get("PopulationFemale") or 0,
                "age_ok": age_ok,
            }
            for a, v in ages.items():
                r["age_" + a] = v if age_ok else None
            for k, keys in EDU.items():
                r["edu_" + k] = sum(d.get(x) or 0 for x in keys)
            for k, key in MARITAL.items():
                r["mar_" + k] = d.get(key) or 0
            rows.append(r)
    return pl.DataFrame(rows)


def election() -> pl.DataFrame:
    rows = []
    for path in sorted(TILES.glob("secim-mv2023-mahalle-TR-*.json")):
        for key, v in json.load(open(path, encoding="utf-8")).items():
            if not re.fullmatch(r"TR-\d+-\d+-\d+", key):
                continue
            r = {"key": key, "id": key.rsplit("-", 1)[1], "reg": v["k"],
                 "voted": v["o"], "valid": v["g"]}  # fmt: skip
            for p, names in PARTIES.items():
                r["v_" + p] = sum(v["v"].get(n, 0) for n in names)
            rows.append(r)
    return pl.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    demo = demography()
    vote = election()
    edu_total = pl.sum_horizontal([pl.col("edu_" + k) for k in EDU])
    mar_total = pl.sum_horizontal([pl.col("mar_" + k) for k in MARITAL])
    t = demo.join(vote, on="id", how="left").with_columns(
        (pl.col("male") / pl.col("pop") * 100).alias("male_pct"),
        (
            (pl.col("age_0_4") + pl.col("age_5_9") + pl.col("age_10_14"))
            / pl.col("pop")
            * 100
        ).alias("child_pct"),
        (pl.col("age_65") / pl.col("pop") * 100).alias("elder_pct"),
        ((pl.col("age_20_24") + pl.col("age_25_29")) / pl.col("pop") * 100).alias(
            "young_adult_pct"
        ),
        (pl.col("edu_university") / edu_total * 100).alias("uni_pct"),
        ((pl.col("edu_illiterate") + pl.col("edu_no_school")) / edu_total * 100).alias(
            "no_school_pct"
        ),
        edu_total.alias("edu_total"),
        (pl.col("mar_never") / mar_total * 100).alias("never_married_pct"),
        (pl.col("mar_divorced") / mar_total * 100).alias("divorced_pct"),
        (pl.col("mar_widowed") / mar_total * 100).alias("widowed_pct"),
        mar_total.alias("mar_total"),
        (pl.col("voted") > pl.col("reg")).alias("institutional"),
        (pl.col("voted") / pl.col("reg") * 100).alias("turnout"),
        *[(pl.col("v_" + p) / pl.col("valid") * 100).alias(p) for p in PARTIES],
    )
    t.write_parquet(OUT / "table.parquet")
    print("neighbourhoods:", t.height, " with votes:", t["valid"].is_not_null().sum())
    print(
        "age bands usable:",
        t["age_ok"].sum(),
        " institutional boxes:",
        t["institutional"].sum(),
    )


if __name__ == "__main__":
    main()
