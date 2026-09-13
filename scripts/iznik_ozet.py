"""İznik in one table: what the Endeksa neighbourhood dump says, split urban / rural.

The split is the project's own (K28): the seven central neighbourhoods are urban, the two
former belde and the thirty-seven villages are rural. It is read from the geometry's
`kind`, not guessed from names, and the two former belde are reported separately as well —
they are the ambiguous cases and hiding them inside "rural" would make the reader trust a
line that is really a decision.

Shares are computed from the counts, never averaged from the neighbourhoods' own shares:
an average of ratios weights a village of ninety people like a neighbourhood of nine
thousand.

Run:  uv run python scripts/iznik_ozet.py [TR-16-006]
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))

KENT = {"centre"}
KASABA = {"rural_town"}

TOPLANIR = [
    "PopulationTotal", "PopulationMale", "PopulationFemale", "HouseholdCount",
    "HousingCount", "PopulationYoung", "PopulationMiddle", "PopulationElder",
    "MarriedNever", "Married", "Divorced", "Widow",
    "EduNonLiterated", "EduLiteratedUntutored", "EduPrimarySchool", "EduMiddleSchool",
    "EduHighSchool", "EduLicenseDegree", "EduGraduate", "EducationTotal",
    "SesGroupA", "SesGroupB", "SesGroupC", "SesGroupD",
    "CarCount", "CommercialCount", "PharmacyCount", "AtmCount", "MobileUser",
    "Age_0_4_Total", "Age_5_9_Total", "Age_10_14_Total", "Age_15_19_Total",
    "Age_20_24_Total", "Age_25_29_Total", "Age_30_34_Total", "Age_35_39_Total",
    "Age_40_44_Total", "Age_45_49_Total", "Age_50_54_Total", "Age_55_59_Total",
    "Age_60_64_Total", "Age_65_Total", "Area", "GSYH",
]
AGIRLIKLI = ["HouseIncome", "ExpenseTotal", "SavingTotal"]


def gruplar(district: str) -> dict[str, list[dict]]:
    geo = json.loads(
        (ROOT / "public" / "geo" / "neighbourhoods" / f"{district}.geojson").read_text(
            encoding="utf-8"
        )
    )
    tur = {
        f["properties"]["area_id"]: f["properties"].get("kind", "village")
        for f in geo["features"]
    }
    dump = json.loads(
        (HAM / "endeksa" / "demography" / f"{district}.json").read_text(encoding="utf-8")
    )

    out: dict[str, list[dict]] = {"kent": [], "kasaba": [], "koy": []}
    for area_id, kind in tur.items():
        ident = area_id.split("-")[-1]
        record = dump.get(ident)
        if not record:
            continue
        row = dict(record["demography"])
        row["_ad"] = record["name_tr"]
        if kind in KENT:
            out["kent"].append(row)
        elif kind in KASABA:
            out["kasaba"].append(row)
        else:
            out["koy"].append(row)
    return out


def topla(rows: list[dict]) -> dict:
    """Counts added, money weighted by household — a mean of means is not a mean."""
    out = {k: sum(r.get(k) or 0 for r in rows) for k in TOPLANIR}
    haneler = out.get("HouseholdCount") or 0
    for k in AGIRLIKLI:
        pay = sum((r.get(k) or 0) * (r.get("HouseholdCount") or 0) for r in rows)
        out[k] = pay / haneler if haneler else 0
    out["_sayi"] = len(rows)
    return out


def yuzde(pay: float, toplam: float) -> str:
    return f"%{100 * pay / toplam:.1f}" if toplam else "—"


def tablo(basliklar: list[str], satirlar: list[list[str]]) -> None:
    genis = [max(len(str(s[i])) for s in [basliklar, *satirlar]) for i in range(len(basliklar))]
    print(" | ".join(str(b).ljust(genis[i]) for i, b in enumerate(basliklar)))
    print("-+-".join("-" * g for g in genis))
    for satir in satirlar:
        print(" | ".join(str(c).ljust(genis[i]) for i, c in enumerate(satir)))


def main(district: str = "TR-16-006") -> None:
    parcalar = gruplar(district)
    kent = topla(parcalar["kent"])
    kasaba = topla(parcalar["kasaba"])
    koy = topla(parcalar["koy"])
    kir = topla(parcalar["kasaba"] + parcalar["koy"])
    hepsi = topla(parcalar["kent"] + parcalar["kasaba"] + parcalar["koy"])

    sutunlar = [("Kent", kent), ("Kır", kir), ("· belde", kasaba), ("· köy", koy),
                ("Toplam", hepsi)]
    def fmt(x):
        return f"{round(x):,}".replace(",", ".")

    print(f"\n=== {district} — Endeksa mahalle dökümü (TÜİK ADNKS 2024)\n")
    satirlar = [
        ["Yerleşim sayısı", *[str(c["_sayi"]) for _, c in sutunlar]],
        ["Nüfus", *[fmt(c["PopulationTotal"]) for _, c in sutunlar]],
        ["Hane", *[fmt(c["HouseholdCount"]) for _, c in sutunlar]],
        ["Konut", *[fmt(c["HousingCount"]) for _, c in sutunlar]],
        ["Hane başına kişi",
         *[f"{c['PopulationTotal'] / c['HouseholdCount']:.2f}" if c["HouseholdCount"] else "—"
           for _, c in sutunlar]],
        ["Yüzölçümü (km²)", *[f"{c['Area']:.0f}" for _, c in sutunlar]],
        ["Yoğunluk (kişi/km²)",
         *[f"{c['PopulationTotal'] / c['Area']:.0f}" if c["Area"] else "—" for _, c in sutunlar]],
    ]
    tablo(["", *[ad for ad, _ in sutunlar]], satirlar)

    print("\n--- Yaş ve cinsiyet")
    tablo(["", *[ad for ad, _ in sutunlar]], [
        ["Erkek payı", *[yuzde(c["PopulationMale"], c["PopulationTotal"]) for _, c in sutunlar]],
        ["0-14 payı", *[yuzde(
            c["Age_0_4_Total"] + c["Age_5_9_Total"] + c["Age_10_14_Total"],
            c["PopulationTotal"]) for _, c in sutunlar]],
        ["15-64 payı", *[yuzde(c["PopulationTotal"] - (
            c["Age_0_4_Total"] + c["Age_5_9_Total"] + c["Age_10_14_Total"] + c["Age_65_Total"]),
            c["PopulationTotal"]) for _, c in sutunlar]],
        ["65+ payı", *[yuzde(c["Age_65_Total"], c["PopulationTotal"]) for _, c in sutunlar]],
        ["Yaşlı / çocuk", *[
            f"{c['Age_65_Total'] / (c['Age_0_4_Total'] + c['Age_5_9_Total'] + c['Age_10_14_Total']):.2f}"
            if (c["Age_0_4_Total"] + c["Age_5_9_Total"] + c["Age_10_14_Total"]) else "—"
            for _, c in sutunlar]],
    ])

    print("\n--- Medeni durum (15+)")
    tablo(["", *[ad for ad, _ in sutunlar]], [
        [ad2, *[yuzde(c[alan], c["MarriedNever"] + c["Married"] + c["Divorced"] + c["Widow"])
                for _, c in sutunlar]]
        for ad2, alan in [("Hiç evlenmedi", "MarriedNever"), ("Evli", "Married"),
                          ("Boşandı", "Divorced"), ("Eşi öldü", "Widow")]
    ])

    print("\n--- Eğitim (15+ bitirilen düzey)")
    tablo(["", *[ad for ad, _ in sutunlar]], [
        [ad2, *[yuzde(c[alan], c["EducationTotal"]) for _, c in sutunlar]]
        for ad2, alan in [("Okuma-yazma yok", "EduNonLiterated"),
                          ("Okur-yazar, okulsuz", "EduLiteratedUntutored"),
                          ("İlkokul", "EduPrimarySchool"), ("Ortaokul", "EduMiddleSchool"),
                          ("Lise", "EduHighSchool"), ("Lisans", "EduLicenseDegree"),
                          ("Lisansüstü", "EduGraduate")]
    ])

    print("\n--- Gelir, SES ve varlık")
    tablo(["", *[ad for ad, _ in sutunlar]], [
        ["Hane geliri (TL/ay)", *[fmt(c["HouseIncome"]) for _, c in sutunlar]],
        ["Harcama (TL/ay)", *[fmt(c["ExpenseTotal"]) for _, c in sutunlar]],
        ["Tasarruf (TL/ay)", *[fmt(c["SavingTotal"]) for _, c in sutunlar]],
        *[[ad2, *[yuzde(c[alan], c["SesGroupA"] + c["SesGroupB"] + c["SesGroupC"] + c["SesGroupD"])
                  for _, c in sutunlar]]
          for ad2, alan in [("SES A", "SesGroupA"), ("SES B", "SesGroupB"),
                            ("SES C", "SesGroupC"), ("SES D", "SesGroupD")]],
        ["Hane başına araç",
         *[f"{c['CarCount'] / c['HouseholdCount']:.2f}" if c["HouseholdCount"] else "—"
           for _, c in sutunlar]],
        ["Ticari işletme", *[fmt(c["CommercialCount"]) for _, c in sutunlar]],
        ["Kişi başına GSYH (TL)",
         *[fmt(c["GSYH"] / c["PopulationTotal"]) if c["PopulationTotal"] else "—"
           for _, c in sutunlar]],
    ])

    print("\n--- En büyük beş yerleşim")
    hepsi_liste = sorted(
        parcalar["kent"] + parcalar["kasaba"] + parcalar["koy"],
        key=lambda r: -(r.get("PopulationTotal") or 0),
    )[:5]
    tablo(["Yerleşim", "Nüfus", "Hane", "65+ payı", "Hane geliri"], [
        [r["_ad"], fmt(r["PopulationTotal"]), fmt(r["HouseholdCount"] or 0),
         yuzde(r.get("Age_65_Total") or 0, r["PopulationTotal"]),
         fmt(r.get("HouseIncome") or 0)]
        for r in hepsi_liste
    ])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "TR-16-006")
