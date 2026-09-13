"""From "Evet" in 2017 to Erdoğan in 2023, settlement by settlement.

The 2017 referendum and the 2023 presidential first round ask the same voters about the
same thing from two directions: the office and the man who holds it. Six years apart, in
the same settlements, the gap between the two shares is a clean measure of where the bloc
held and where it thinned.

    fark = Erdoğan 2023 (%) − Evet 2017 (%)

Both are shares of valid votes, so turnout differences do not enter. Everything is
weighted by 2023 valid votes; shares are summed counts, never averaged shares.

Two settlements are compared only when both years exist for the same area id. Village
names changed after 2014 in metropolitan provinces, so the older referendums (2010, 2007)
cannot be matched this way at all — that is a property of the source, not a bug to fix.

Run:  uv run python scripts/evet_erdogan.py [--n=12]
"""

from __future__ import annotations

import csv
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
TILES = ROOT / "public" / "tiles"
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


def tablo(vote: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in TILES.glob(f"secim-{vote}-mahalle-TR-*.json"):
        for area_id, row in json.loads(path.read_text(encoding="utf-8")).items():
            if area_id.count("-") == 3:
                out[area_id] = row
    return out


def pay(row: dict, parca: str) -> float | None:
    gecerli = row.get("g") or sum(row.get("v", {}).values())
    if not gecerli:
        return None
    return sum(v for k, v in row.get("v", {}).items() if parca in k.upper()) / gecerli


def gelir_tablosu() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(DEM.glob("TR-*.json")):
        try:
            dump = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for ident, record in dump.items():
            dem = record.get("demography") or {}
            nufus = dem.get("PopulationTotal") or 0
            egitim = dem.get("EducationTotal") or 0
            if not nufus or not egitim:
                continue
            out[f"{path.stem}-{ident}"] = {
                "gelir": dem.get("HouseIncome") or 0,
                "lisans": (dem.get("EduLicenseDegree") or 0) / egitim,
                "yasli": (dem.get("Age_65_Total") or 0) / nufus,
            }
    return out


def main(argv: list[str]) -> None:
    n = int(next((a.split("=")[1] for a in argv if a.startswith("--n=")), 12))
    iller, ilceler = adlar()
    ho = tablo("ho2017")
    cb = tablo("cb2023t1")
    gelir = gelir_tablosu()

    rows = []
    for area_id, eski in ho.items():
        yeni = cb.get(area_id)
        if not yeni:
            continue
        evet = pay(eski, "EVET")
        erdogan = pay(yeni, "ERDO")
        gecerli = yeni.get("g") or sum(yeni.get("v", {}).values())
        if evet is None or erdogan is None or gecerli < 300:
            continue
        rows.append(
            {
                "ad": yeni.get("ad") or eski.get("ad") or "",
                "ilce": ilceler.get(area_id[:9], area_id[:9]),
                "il": iller.get(area_id[:5], ""),
                "agirlik": gecerli,
                "evet": evet,
                "erdogan": erdogan,
                "fark": erdogan - evet,
                **gelir.get(area_id, {}),
            }
        )

    toplam = sum(r["agirlik"] for r in rows)
    print(
        f"{len(rows):,} yerleşim eşleşti (2017 halkoylaması ∩ 2023 CB 1. tur) · "
        f"{toplam:,.0f} geçerli oy"
    )
    if not rows:
        return
    ort_evet = sum(r["evet"] * r["agirlik"] for r in rows) / toplam
    ort_rte = sum(r["erdogan"] * r["agirlik"] for r in rows) / toplam
    print(
        f"bu kesitte: Evet %{100 * ort_evet:.1f} → Erdoğan %{100 * ort_rte:.1f} "
        f"({100 * (ort_rte - ort_evet):+.1f} puan)"
    )

    def yaz(baslik: str, sirali: list[dict]) -> None:
        print(f"\n=== {baslik}")
        print(
            f"{'Mahalle':22}{'İlçe':15}{'İl':11}{'geçerli':>9}"
            f"{'Evet 17':>9}{'RTE 23':>9}{'fark':>8}"
        )
        for r in sirali[:n]:
            print(
                f"{r['ad'][:21]:22}{r['ilce'][:14]:15}{r['il'][:10]:11}{r['agirlik']:>9,}"
                f"{100 * r['evet']:>9.1f}{100 * r['erdogan']:>9.1f}{100 * r['fark']:>+8.1f}"
            )

    yaz("En çok kazanılan yerler (Erdoğan, Evet'in çok üstünde)", sorted(rows, key=lambda r: -r["fark"]))
    yaz("En çok kaybedilen yerler (Erdoğan, Evet'in altında)", sorted(rows, key=lambda r: r["fark"]))

    print("\n=== 2017 Evet düzeyine göre (eşit seçmenli beşte birlik dilimler)")
    sirali = sorted(rows, key=lambda r: r["evet"])
    hedef = toplam / 5
    gruplar, dilim, birikim = [], [], 0.0
    for row in sirali:
        dilim.append(row)
        birikim += row["agirlik"]
        if birikim >= hedef and len(gruplar) < 4:
            gruplar.append(dilim)
            dilim, birikim = [], 0.0
    gruplar.append(dilim)
    print(f"{'Dilim':8}{'Evet 17':>10}{'RTE 23':>10}{'fark':>9}{'yerleşim':>10}")
    for i, grup in enumerate(gruplar, 1):
        w = sum(r["agirlik"] for r in grup)
        e = sum(r["evet"] * r["agirlik"] for r in grup) / w
        rte = sum(r["erdogan"] * r["agirlik"] for r in grup) / w
        print(f"{i:<8}{100 * e:>10.1f}{100 * rte:>10.1f}{100 * (rte - e):>+9.1f}{len(grup):>10,}")

    print("\n=== İl bazında (en az 20 yerleşim), farkın uçları")
    il_gruplari: dict[str, list[dict]] = {}
    for row in rows:
        il_gruplari.setdefault(row["il"], []).append(row)
    il_satirlari = []
    for il, grup in il_gruplari.items():
        if len(grup) < 20:
            continue
        w = sum(r["agirlik"] for r in grup)
        il_satirlari.append(
            {
                "il": il,
                "n": len(grup),
                "evet": sum(r["evet"] * r["agirlik"] for r in grup) / w,
                "rte": sum(r["erdogan"] * r["agirlik"] for r in grup) / w,
            }
        )
    for satir in il_satirlari:
        satir["fark"] = satir["rte"] - satir["evet"]
    sirali_il = sorted(il_satirlari, key=lambda r: -r["fark"])
    print(f"{'İl':16}{'yerleşim':>10}{'Evet 17':>10}{'RTE 23':>10}{'fark':>9}")
    for satir in sirali_il[:6] + [None] + sirali_il[-6:]:
        if satir is None:
            print("  …")
            continue
        print(
            f"{satir['il'][:15]:16}{satir['n']:>10,}{100 * satir['evet']:>10.1f}"
            f"{100 * satir['rte']:>10.1f}{100 * satir['fark']:>+9.1f}"
        )

    gelirli = [r for r in rows if r.get("gelir")]
    if len(gelirli) > 200:
        print(f"\n=== Farkın demografiyle ilişkisi ({len(gelirli):,} yerleşimde gelir var)")
        for etiket, alan in [("hane geliri", "gelir"), ("lisans payı", "lisans"), ("65+ payı", "yasli")]:
            w = sum(r["agirlik"] for r in gelirli)
            mx = sum(r[alan] * r["agirlik"] for r in gelirli) / w
            my = sum(r["fark"] * r["agirlik"] for r in gelirli) / w
            sxy = sum(r["agirlik"] * (r[alan] - mx) * (r["fark"] - my) for r in gelirli)
            sxx = sum(r["agirlik"] * (r[alan] - mx) ** 2 for r in gelirli)
            syy = sum(r["agirlik"] * (r["fark"] - my) ** 2 for r in gelirli)
            print(f"  fark × {etiket:14}{sxy / (sxx * syy) ** 0.5:>+8.3f}")


if __name__ == "__main__":
    main(sys.argv[1:])
