"""Hasanoğlan — a former belde read as one place, from TÜİK and Endeksa together.

Hasanoğlan was a belde of its own until the 2008 metropolitan law closed it; its six
neighbourhoods then went under Elmadağ directly. It still works as one settlement -- one
postal code, one centre, its own name in daily use -- so the six are added back together
here and set against the rest of Elmadağ.

Two sources, and they do not measure the same thing:

    TÜİK    the registered population, by year, 2007-2025, split at eighteen
    Endeksa a single modelled vintage with income, schooling, tenure and prices

Endeksa's figures are estimates built from other data, not a count: they are read for the
*differences between places*, which they capture, and not as totals, which they do not
guarantee. Where the two disagree on population, TÜİK is the one that counts.

Run:  uv run python scripts/hasanoglan.py
"""

from __future__ import annotations

import collections
import csv
import gzip
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
DEM = HAM / "endeksa" / "demography"
MEDAS = HAM / "medas" / "mahalle" / "nufus-mahalle-ANKARA-2007_2012.csv"
TUIK = ROOT / "public" / "population-neighbourhood.csv.gz"
TILES = ROOT / "public" / "tiles"

DISTRICT = "TR-06-009"
#: The six neighbourhoods of the old belde, by the id both sources carry.
SEMT = {
    "2085": "Bahçelievler",
    "2086": "Fatih",
    "2087": "Havuzbaşı",
    "2088": "İstasyon",
    "2089": "Muzaffer Ekşi",
    "2090": "Şehitlik",
}


def tuik_series() -> dict[str, tuple[int, int]]:
    """{year: (population, under 18)} for the semt, 2007-2025.

    Two files, because TÜİK's neighbourhood series begins in 2013. The years before it
    come from the MEDAS extract, where the same neighbourhood ids appear -- under
    "Hasanoğlan Bel." in 2007 and under Elmadağ from 2008, since the belde was closed.
    Matching on the id rather than the name is what carries the series across that break.
    """
    out: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    year = None
    with MEDAS.open(encoding="utf-8-sig") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("|")
            if parts and re.fullmatch(r"\d{4}", parts[0].strip()):
                year = parts[0].strip()
            if len(parts) < 4 or not year:
                continue
            found = re.search(r"-(\d+)$", parts[1].strip())
            if not found or found.group(1) not in SEMT:
                continue
            try:
                adult, child = float(parts[2]), float(parts[3])
            except ValueError:
                continue
            out[year][0] += int(adult + child)
            out[year][1] += int(child)

    with gzip.open(TUIK, "rt", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            ident = row["area_id"].rsplit("-", 1)[-1]
            if not row["area_id"].startswith(DISTRICT) or ident not in SEMT:
                continue
            value = int(float(row["value"]))
            out[row["year"]][0] += value
            if row["age"] == "0-17":
                out[row["year"]][1] += value
    return {k: (v[0], v[1]) for k, v in sorted(out.items())}


def endeksa() -> tuple[dict, dict]:
    """(semt totals, rest-of-district totals) from the Endeksa record."""
    table = json.loads((DEM / f"{DISTRICT}.json").read_text(encoding="utf-8"))
    semt: dict[str, float] = collections.defaultdict(float)
    rest: dict[str, float] = collections.defaultdict(float)
    for ident, record in table.items():
        dem = record.get("demography") or {}
        target = semt if ident in SEMT else rest
        for key, value in dem.items():
            if isinstance(value, (int, float)):
                target[key] += value
        target["_n"] += 1
    return semt, rest


def rate(bag: dict, field: str, base: str = "PopulationTotal") -> float:
    """A share rebuilt from its parts, never an average of shares."""
    return 100 * bag.get(field, 0) / bag[base] if bag.get(base) else 0.0


def main() -> None:
    series = tuik_series()
    print("HASANOĞLAN — nüfus ve çocuk oranı (TÜİK)")
    print(f"{'Yıl':<6}{'nüfus':>9}{'0-17':>8}{'çocuk%':>9}")
    for year, (total, child) in series.items():
        print(f"{year:<6}{total:>9,}{child:>8,}{100 * child / total:>8.1f}%")

    semt, rest = endeksa()
    head = f"{'':26}{'Hasanoğlan':>14}{'Elmadağ kalanı':>18}"
    print(f"\nENDEKSA · semt {int(semt['_n'])} mahalle, kalan {int(rest['_n'])} birim")
    print(head)
    for label, field, form in (
        ("Nüfus", "PopulationTotal", "{:,.0f}"),
        ("Hane", "HouseholdCount", "{:,.0f}"),
        ("Konut", "HousingCount", "{:,.0f}"),
        ("Ev sahibi %", "OwnerShare", "{:.1f}"),
        ("Kiracı %", "RentedShare", "{:.1f}"),
    ):
        if label.endswith("%"):
            # A share is stored per neighbourhood; summing them is meaningless.
            a = semt.get(field, 0) / semt["_n"]
            b = rest.get(field, 0) / rest["_n"]
            print(f"{label:<26}{a:>14.1f}{b:>18.1f}")
            continue
        print(
            f"{label:<26}{form.format(semt.get(field, 0)):>14}"
            f"{form.format(rest.get(field, 0)):>18}"
        )

    # Endeksa stores some fields as a rate already: household income is a monthly figure
    # per neighbourhood, the square-metre prices likewise. Adding those up and dividing by
    # households gives 58 lira a month. They are weighted instead -- income by households,
    # prices by dwellings -- and a zero price means "no listing here", not a free house,
    # so it is left out rather than dragging the average down.
    def weighted(bag: dict, field: str, weight: str) -> float:
        table = json.loads((DEM / f"{DISTRICT}.json").read_text(encoding="utf-8"))
        top = bottom = 0.0
        for ident, record in table.items():
            if (ident in SEMT) != (bag is semt):
                continue
            dem = record.get("demography") or {}
            value, mass = dem.get(field) or 0, dem.get(weight) or 0
            if value and mass:
                top += value * mass
                bottom += mass
        return top / bottom if bottom else 0.0

    for label, field, weight in (
        ("Hane geliri (aylık TL)", "HouseIncome", "HouseholdCount"),
        ("Konut m2 satış (TL)", "HouseUnitPriceForSale", "HousingCount"),
        ("Konut m2 kira (TL)", "HouseUnitPriceForRent", "HousingCount"),
    ):
        print(
            f"{label:<26}{weighted(semt, field, weight):>14,.0f}"
            f"{weighted(rest, field, weight):>18,.0f}"
        )
    for label, field, base, scale in (
        ("Kişi başı GSYH ($)", "GSYH", "PopulationTotal", 1),
        ("Araç (bin kişide)", "VehicleCount", "PopulationTotal", 1000),
    ):
        a = semt.get(field, 0) / semt[base] * scale if semt.get(base) else 0
        b = rest.get(field, 0) / rest[base] * scale if rest.get(base) else 0
        print(f"{label:<26}{a:>14,.0f}{b:>18,.0f}")

    print(f"\n{'Eğitim':<26}{'Hasanoğlan':>14}{'Elmadağ kalanı':>18}")
    for label, fields in (
        ("okuma yazma bilmeyen", ("EduNonLiterated",)),
        ("ilkokul", ("EduPrimarySchool",)),
        ("ortaokul", ("EduMiddleSchool",)),
        ("lise", ("EduHighSchool",)),
        ("üniversite", ("EduLicenseDegree",)),
        ("yüksek lisans + doktora", ("EduGraduate", "EduDoctorate")),
    ):
        a = sum(rate(semt, f, "EducationTotal") for f in fields)
        b = sum(rate(rest, f, "EducationTotal") for f in fields)
        print(f"  {label:<24}{a:>13.1f}%{b:>17.1f}%")

    print(f"\n{'Gelir grubu (SES)':<26}{'Hasanoğlan':>14}{'Elmadağ kalanı':>18}")
    for label, fields in (
        ("A+ / A", ("SesGroupAPlus", "SesGroupA")),
        ("B", ("SesGroupB",)),
        ("C", ("SesGroupC",)),
        ("D", ("SesGroupD",)),
    ):
        a = sum(rate(semt, f) for f in fields)
        b = sum(rate(rest, f) for f in fields)
        print(f"  {label:<24}{a:>13.1f}%{b:>17.1f}%")

    path = TILES / "secim-mv2023-mahalle-TR-06.json"
    if not path.exists():
        return
    table = json.loads(path.read_text(encoding="utf-8"))
    bag = {"semt": collections.Counter(), "rest": collections.Counter()}
    for area, row in table.items():
        if not area.startswith(DISTRICT) or area.count("-") != 3:
            continue
        key = "semt" if area.rsplit("-", 1)[-1] in SEMT else "rest"
        for party, count in (row.get("v") or {}).items():
            bag[key][party.upper()] += count
    if not sum(bag["semt"].values()):
        return
    print(f"\n{'2023 milletvekili oyu':<26}{'Hasanoğlan':>14}{'Elmadağ kalanı':>18}")
    for party in ("AK PARTİ", "CHP", "MHP", "İYİ PARTİ", "YEŞİL SOL", "ZAFER"):
        a, b = bag["semt"], bag["rest"]
        sa = 100 * sum(v for k, v in a.items() if party in k) / sum(a.values())
        sb = 100 * sum(v for k, v in b.items() if party in k) / sum(b.values())
        print(f"  {party:<24}{sa:>13.1f}%{sb:>17.1f}%")


if __name__ == "__main__":
    sys.exit(main())
