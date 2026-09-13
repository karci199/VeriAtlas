"""How many people share one pharmacy, one ATM, one bank branch — by district.

The counts come from the Endeksa neighbourhood dump and are summed to the district, then
turned upside down: people per outlet rather than outlets per person, because "one
pharmacy per 3.400 people" is a sentence and "0,00029 pharmacies per person" is not.

Two cautions the numbers cannot carry themselves:

  * a district with none of something shows as "—", not as infinity, and it is listed
    separately — an empty district is a finding, not a rank
  * the ratio is residence-based. A district centre serves the villages around it, so the
    market town looks well supplied and its hinterland looks empty; both readings are
    about where the counter stands, not where the customer lives

Run:  uv run python scripts/hizmet_erisimi.py [--n=15] [--enaz=20000]
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

HIZMETLER = [
    ("Eczane", "PharmacyCount"),
    ("ATM", "AtmCount"),
    ("Banka şubesi", "BankBranchCount"),
]


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


def ilceler_verisi() -> list[dict]:
    iller, ilce_adlari = adlar()
    out = []
    for path in sorted(DEM.glob("TR-*.json")):
        try:
            dump = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        toplam = {"nufus": 0, "hane": 0, "gelir_pay": 0.0}
        for _, alan in HIZMETLER:
            toplam[alan] = 0.0
        for record in dump.values():
            dem = record.get("demography") or {}
            nufus = dem.get("PopulationTotal") or 0
            hane = dem.get("HouseholdCount") or 0
            if not nufus:
                continue
            toplam["nufus"] += nufus
            toplam["hane"] += hane
            toplam["gelir_pay"] += (dem.get("HouseIncome") or 0) * hane
            for _, alan in HIZMETLER:
                toplam[alan] += dem.get(alan) or 0
        if not toplam["nufus"]:
            continue
        toplam["ilce"] = ilce_adlari.get(path.stem, path.stem)
        toplam["il"] = iller.get(path.stem[:5], "")
        toplam["gelir"] = toplam["gelir_pay"] / toplam["hane"] if toplam["hane"] else 0
        out.append(toplam)
    return out


def basina(row: dict, alan: str) -> float | None:
    sayi = row[alan]
    return row["nufus"] / sayi if sayi else None


def yaz(baslik: str, rows: list[dict], alan: str, n: int, tersten: bool) -> None:
    olan = [r for r in rows if r[alan]]
    olan.sort(key=lambda r: basina(r, alan), reverse=tersten)
    print(f"\n=== {baslik}")
    print(f"{'İlçe':17}{'İl':13}{'Nüfus':>10}{'Adet':>7}{'Kişi/adet':>11}{'Hane geliri':>13}")
    for row in olan[:n]:
        print(
            f"{row['ilce'][:16]:17}{row['il'][:12]:13}{row['nufus']:>10,}"
            f"{row[alan]:>7,.0f}{basina(row, alan):>11,.0f}{row['gelir']:>13,.0f}"
        )


def main(argv: list[str]) -> None:
    n = int(next((a.split("=")[1] for a in argv if a.startswith("--n=")), 12))
    enaz = int(next((a.split("=")[1] for a in argv if a.startswith("--enaz=")), 20000))
    rows = [r for r in ilceler_verisi() if r["nufus"] >= enaz]
    print(
        f"kapsam: {len(rows)} ilçe (nüfus ≥ {enaz:,}) · "
        f"{sum(r['nufus'] for r in rows):,} kişi"
    )
    if not rows:
        return

    for etiket, alan in HIZMETLER:
        toplam_sayi = sum(r[alan] for r in rows)
        toplam_nufus = sum(r["nufus"] for r in rows)
        print(
            f"\n\n########## {etiket} — toplam {toplam_sayi:,.0f}, "
            f"ortalama {toplam_nufus / toplam_sayi:,.0f} kişiye bir tane"
            if toplam_sayi
            else f"\n\n########## {etiket} — kayıt yok"
        )
        yaz(f"{etiket} başına en çok kişi (en seyrek)", rows, alan, n, True)
        yaz(f"{etiket} başına en az kişi (en yoğun)", rows, alan, n, False)
        yok = [r for r in rows if not r[alan]]
        if yok:
            print(f"\n{etiket} hiç görünmeyen ilçeler ({len(yok)}):")
            print(
                "  "
                + ", ".join(f"{r['ilce']} ({r['il']})" for r in sorted(yok, key=lambda r: -r["nufus"])[:12])
                + ("…" if len(yok) > 12 else "")
            )

    print("\n\n=== Hizmet yoğunluğu ile gelir ilişkisi (ilçe düzeyi, nüfus ağırlıklı)")
    for etiket, alan in HIZMETLER:
        olan = [r for r in rows if r[alan]]
        if len(olan) < 10:
            continue
        w = sum(r["nufus"] for r in olan)
        mx = sum(r["gelir"] * r["nufus"] for r in olan) / w
        my = sum((r[alan] / r["nufus"] * 10000) * r["nufus"] for r in olan) / w
        sxy = sum(
            r["nufus"] * (r["gelir"] - mx) * (r[alan] / r["nufus"] * 10000 - my) for r in olan
        )
        sxx = sum(r["nufus"] * (r["gelir"] - mx) ** 2 for r in olan)
        syy = sum(r["nufus"] * (r[alan] / r["nufus"] * 10000 - my) ** 2 for r in olan)
        korelasyon = sxy / (sxx * syy) ** 0.5 if sxx and syy else float("nan")
        print(f"  on binde {etiket:14} × hane geliri   {korelasyon:+.3f}")


if __name__ == "__main__":
    main(sys.argv[1:])
