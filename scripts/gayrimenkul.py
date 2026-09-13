"""Housing seen from the neighbourhood: what it costs, what it earns, who owns it.

Four questions the Endeksa dump can answer, each with its own coverage:

    ulaşılabilirlik   100 m²'nin fiyatı, yıllık hane gelirine bölünür — "kaç yıllık gelir"
    kira çarpanı      satış fiyatı / yıllık kira — kaç yılda kendini amorti eder
    mülkiyet          ev sahipliği oranı, gelir dilimlerine göre
    yazlık            ikinci konut payı, kıyı ilçelerinin işareti

Coverage is the catch and it is not random: sale and rent prices exist only where there
are listings — 18% and 13% of settlements, almost all urban. So every price table here is
a statement about neighbourhoods with a market, not about the country. Land price (70%)
and ownership (60%) reach much further and are reported separately for that reason.

Run:  uv run python scripts/gayrimenkul.py [--n=12] [--m2=100]
"""

from __future__ import annotations

import csv
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
DEM = HAM / "endeksa" / "demography"
DATA = ROOT / "src" / "veriatlas" / "data"


def adlar() -> tuple[dict[str, str], dict[str, str]]:
    iller = {
        row["area_id"]: row["name_tr"]
        for row in csv.DictReader((DATA / "areas_tr.csv").open(encoding="utf-8"))
        if row.get("area_level") == "province"
    }
    ilceler = {
        row["area_id"]: row["name_tr"]
        for row in csv.DictReader((DATA / "areas_tr_districts.csv").open(encoding="utf-8"))
    }
    return iller, ilceler


def mahalleler() -> list[dict]:
    iller, ilceler = adlar()
    out: list[dict] = []
    for path in sorted(DEM.glob("TR-*.json")):
        try:
            dump = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for record in dump.values():
            dem = record.get("demography") or {}
            nufus = dem.get("PopulationTotal") or 0
            hane = dem.get("HouseholdCount") or 0
            gelir = dem.get("HouseIncome") or 0
            if nufus < 300 or hane < 100 or not gelir:
                continue
            out.append(
                {
                    "ad": record.get("name_tr") or "",
                    "ilce": ilceler.get(path.stem, path.stem),
                    "il": iller.get(path.stem[:5], ""),
                    "nufus": nufus,
                    "hane": hane,
                    "gelir": gelir,
                    "konut": dem.get("HousingCount") or 0,
                    "satis_m2": dem.get("HouseUnitPriceForSale") or 0,
                    "kira_m2": dem.get("HouseUnitPriceForRent") or 0,
                    "arsa_m2": dem.get("PlotUnitPriceForSale") or 0,
                    "arazi_m2": dem.get("LandPrice") or 0,
                    "sahip": dem.get("OwnerShare") or 0,
                    "kirаci": dem.get("RentedShare") or 0,
                    "yazlik": dem.get("SummerResortCount") or 0,
                    "ilan_suresi": dem.get("HouseListingPeriodForSale") or 0,
                    "satis_2024": dem.get("Total_BB_Sale_2024") or 0,
                }
            )
    return out


def yaz(baslik: str, rows: list[dict], sutunlar: list[tuple[str, str, str]], n: int) -> None:
    print(f"\n=== {baslik}")
    print(f"{'Mahalle':22}{'İlçe':15}{'İl':11}" + "".join(f"{ad:>14}" for ad, _, _ in sutunlar))
    for row in rows[:n]:
        print(
            f"{row['ad'][:21]:22}{row['ilce'][:14]:15}{row['il'][:10]:11}"
            + "".join(f"{format(row[alan], bicim):>14}" for _, alan, bicim in sutunlar)
        )


def main(argv: list[str]) -> None:
    n = int(next((a.split("=")[1] for a in argv if a.startswith("--n=")), 12))
    m2 = int(next((a.split("=")[1] for a in argv if a.startswith("--m2=")), 100))
    rows = mahalleler()
    fiyatli = [r for r in rows if r["satis_m2"] and r["gelir"]]
    kiralik = [r for r in fiyatli if r["kira_m2"]]
    print(
        f"kapsam: {len(rows):,} mahalle · satış fiyatı olan {len(fiyatli):,} "
        f"(%{100 * len(fiyatli) / len(rows):.0f}) · kira da olan {len(kiralik):,}"
    )
    if not fiyatli:
        return

    for row in fiyatli:
        row["yil"] = row["satis_m2"] * m2 / (row["gelir"] * 12)
    for row in kiralik:
        row["carpan"] = row["satis_m2"] / (row["kira_m2"] * 12)

    sut = [("m² satış", "satis_m2", ",.0f"), ("hane geliri", "gelir", ",.0f"),
           (f"{m2} m² / yıl", "yil", ".1f")]
    yaz(
        f"En ulaşılamaz: {m2} m² kaç yıllık hane geliri",
        sorted(fiyatli, key=lambda r: -r["yil"]),
        sut,
        n,
    )
    yaz(
        "En ulaşılabilir (piyasası olan mahalleler içinde)",
        sorted(fiyatli, key=lambda r: r["yil"]),
        sut,
        n,
    )

    if kiralik:
        sut2 = [("m² satış", "satis_m2", ",.0f"), ("m² kira", "kira_m2", ",.0f"),
                ("amortisman yıl", "carpan", ".1f")]
        yaz(
            "Kira getirisi en yüksek (amortisman süresi en kısa)",
            sorted(kiralik, key=lambda r: r["carpan"]),
            sut2,
            n,
        )
        yaz(
            "Kira getirisi en düşük (en uzun amortisman)",
            sorted(kiralik, key=lambda r: -r["carpan"]),
            sut2,
            n,
        )

    yazlikli = [r for r in rows if r["konut"] and r["yazlik"]]
    if yazlikli:
        for row in yazlikli:
            row["yazlik_pay"] = 100 * row["yazlik"] / row["konut"]
        yaz(
            "İkinci konut (yazlık) payı en yüksek",
            sorted(yazlikli, key=lambda r: -r["yazlik_pay"]),
            [("konut", "konut", ",.0f"), ("yazlık", "yazlik", ",.0f"),
             ("yazlık payı %", "yazlik_pay", ".1f")],
            n,
        )

    sahipli = [r for r in rows if r["sahip"]]
    if sahipli:
        print("\n=== Ev sahipliği, gelir dilimlerine göre (hane ağırlıklı)")
        sirali = sorted(sahipli, key=lambda r: r["gelir"])
        toplam = sum(r["hane"] for r in sirali)
        dilim, birikim, gruplar = [], 0.0, []
        for row in sirali:
            dilim.append(row)
            birikim += row["hane"]
            if birikim >= toplam / 5 and len(gruplar) < 4:
                gruplar.append(dilim)
                dilim, birikim = [], 0.0
        gruplar.append(dilim)
        print(f"{'Dilim':8}{'Hane geliri':>13}{'Ev sahibi %':>13}{'Kiracı %':>11}{'Mahalle':>9}")
        for i, grup in enumerate(gruplar, 1):
            w = sum(r["hane"] for r in grup)
            gelir = sum(r["gelir"] * r["hane"] for r in grup) / w
            sahip = sum(r["sahip"] * r["hane"] for r in grup) / w
            kiraci = sum(r["kirаci"] * r["hane"] for r in grup) / w
            print(f"{i:<8}{gelir:>13,.0f}{sahip:>13.1f}{kiraci:>11.1f}{len(grup):>9}")

    print("\n=== Fiyatın gelirle ilişkisi (mahalle düzeyi, hane ağırlıklı)")
    for etiket, alan in [("m² satış", "satis_m2"), ("m² kira", "kira_m2"),
                         ("arsa m²", "arsa_m2"), ("ev sahipliği", "sahip")]:
        veri = [r for r in rows if r.get(alan)]
        if len(veri) < 30:
            continue
        w = sum(r["hane"] for r in veri)
        mx = sum(r["gelir"] * r["hane"] for r in veri) / w
        my = sum(r[alan] * r["hane"] for r in veri) / w
        sxy = sum(r["hane"] * (r["gelir"] - mx) * (r[alan] - my) for r in veri)
        sxx = sum(r["hane"] * (r["gelir"] - mx) ** 2 for r in veri)
        syy = sum(r["hane"] * (r[alan] - my) ** 2 for r in veri)
        korelasyon = sxy / (sxx * syy) ** 0.5 if sxx and syy else float("nan")
        print(f"  gelir × {etiket:14}{korelasyon:>+8.3f}   ({len(veri):,} mahalle)")


if __name__ == "__main__":
    main(sys.argv[1:])
