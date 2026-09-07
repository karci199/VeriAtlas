"""Income inequality *inside* districts, and what income travels with.

A district's average income says little about living in it: two districts with the same
mean can be uniform or split in half. So this measures the spread between a district's own
neighbourhoods —

    p90 / p10   the ninetieth against the tenth percentile of neighbourhood income,
                percentiles taken over households rather than over neighbourhoods, so a
                hamlet of forty does not count as much as a neighbourhood of nine thousand
    kent − kır  the gap between the central neighbourhoods and the villages, which is a
                different question and often the larger one

and then asks what income moves with: household size, the elderly share, university
education, car ownership, commerce.

Only districts with enough neighbourhoods are ranked: a spread computed from three
settlements is arithmetic, not a finding.

Run:  uv run python scripts/gelir_esitsizlik.py [--n=20] [--enaz=8]
"""

from __future__ import annotations

import csv
import json
import math
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
DEM = HAM / "endeksa" / "demography"
GEO = ROOT / "public" / "geo" / "neighbourhoods"
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


def tur_haritasi(district: str) -> dict[str, str]:
    path = GEO / f"{district}.geojson"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    # Only where the file actually carries a classification. Defaulting the missing ones
    # to "village" made every settlement rural and the density fallback never ran.
    return {
        f["properties"]["area_id"].split("-")[-1]: f["properties"]["kind"]
        for f in data.get("features", [])
        if f["properties"].get("area_id") and f["properties"].get("kind")
    }


def mahalleler(district: str) -> list[dict]:
    path = DEM / f"{district}.json"
    if not path.exists():
        return []
    try:
        dump = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    tur = {k: v for k, v in tur_haritasi(district).items() if v in ("centre", "village", "rural_town")}
    out = []
    for ident, record in dump.items():
        dem = record.get("demography") or {}
        nufus = dem.get("PopulationTotal") or 0
        hane = dem.get("HouseholdCount") or 0
        gelir = dem.get("HouseIncome") or 0
        if nufus < 100 or hane < 30 or not gelir:
            continue
        out.append(
            {
                "ad": record.get("name_tr") or "",
                # Urban / rural: the legal split is not available country-wide — after the
                # 2012 law every settlement in a metropolitan province is a "belediye
                # mahallesi", and Endeksa labels them all that way. So density stands in
                # for it: a thousand people per km² is roughly where a village stops
                # looking like one. Where the pilot's own classification exists it wins.
                "tur": tur.get(ident)
                or ("centre" if (dem.get("PopulationDensity") or 0) >= 1000 else "village"),
                "nufus": nufus,
                "hane": hane,
                "gelir": gelir,
                "hane_kisi": nufus / hane,
                "yasli": (dem.get("Age_65_Total") or 0) / nufus,
                "lisans": (dem.get("EduLicenseDegree") or 0) / (dem.get("EducationTotal") or 1),
                "arac": (dem.get("CarCount") or 0) / hane,
                "ticari": (dem.get("CommercialCount") or 0) / nufus * 1000,
            }
        )
    return out


def yuzdelik(rows: list[dict], oran: float) -> float:
    """Percentile of neighbourhood income, over households."""
    sirali = sorted(rows, key=lambda r: r["gelir"])
    hedef = oran * sum(r["hane"] for r in sirali)
    birikim = 0.0
    for row in sirali:
        birikim += row["hane"]
        if birikim >= hedef:
            return row["gelir"]
    return sirali[-1]["gelir"] if sirali else 0.0


def ortalama(rows: list[dict], alan: str) -> float:
    w = sum(r["hane"] for r in rows)
    return sum(r[alan] * r["hane"] for r in rows) / w if w else 0.0


def korelasyon(rows: list[dict], x: str, y: str) -> float:
    w = sum(r["hane"] for r in rows)
    if not w:
        return float("nan")
    mx = sum(r[x] * r["hane"] for r in rows) / w
    my = sum(r[y] * r["hane"] for r in rows) / w
    sxy = sum(r["hane"] * (r[x] - mx) * (r[y] - my) for r in rows)
    sxx = sum(r["hane"] * (r[x] - mx) ** 2 for r in rows)
    syy = sum(r["hane"] * (r[y] - my) ** 2 for r in rows)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else float("nan")


def main(argv: list[str]) -> None:
    n = int(next((a.split("=")[1] for a in argv if a.startswith("--n=")), 15))
    enaz = int(next((a.split("=")[1] for a in argv if a.startswith("--enaz=")), 8))
    iller, ilceler = adlar()

    ilce_satirlari = []
    hepsi: list[dict] = []
    for path in sorted(DEM.glob("TR-*.json")):
        rows = mahalleler(path.stem)
        hepsi.extend(rows)
        if len(rows) < enaz:
            continue
        kent = [r for r in rows if r["tur"] == "centre"]
        kir = [r for r in rows if r["tur"] != "centre"]
        p10, p50, p90 = (yuzdelik(rows, x) for x in (0.1, 0.5, 0.9))
        ilce_satirlari.append(
            {
                "ilce": ilceler.get(path.stem, path.stem),
                "il": iller.get(path.stem[:5], ""),
                "mahalle": len(rows),
                "hane": sum(r["hane"] for r in rows),
                "ortalama": ortalama(rows, "gelir"),
                "p10": p10,
                "p50": p50,
                "p90": p90,
                "makas": p90 / p10 if p10 else float("nan"),
                "kent": ortalama(kent, "gelir") if kent else float("nan"),
                "kir": ortalama(kir, "gelir") if kir else float("nan"),
            }
        )

    print(
        f"kapsam: {len(list(DEM.glob('TR-*.json')))} ilçe dosyası · "
        f"{len(hepsi):,} mahalle · sıralanan {len(ilce_satirlari)} ilçe (en az {enaz} mahalle)"
    )
    if not ilce_satirlari:
        return

    baslik = (
        f"{'İlçe':16}{'İl':12}{'Mah.':>6}{'Ortalama':>10}"
        f"{'p10':>9}{'p90':>9}{'p90/p10':>9}{'Kent':>9}{'Kır':>9}"
    )

    def yaz(rows: list[dict]) -> None:
        print(baslik)
        for r in rows:
            kent = f"{r['kent']:>9,.0f}" if r["kent"] == r["kent"] else f"{'—':>9}"
            kir = f"{r['kir']:>9,.0f}" if r["kir"] == r["kir"] else f"{'—':>9}"
            print(
                f"{r['ilce'][:15]:16}{r['il'][:11]:12}{r['mahalle']:>6}"
                f"{r['ortalama']:>10,.0f}{r['p10']:>9,.0f}{r['p90']:>9,.0f}"
                f"{r['makas']:>9.2f}{kent}{kir}"
            )

    print("\n=== İç eşitsizliği en yüksek ilçeler (p90 / p10)")
    yaz(sorted(ilce_satirlari, key=lambda r: -r["makas"])[:n])

    print("\n=== En türdeş ilçeler (p90 / p10 en düşük)")
    yaz(sorted(ilce_satirlari, key=lambda r: r["makas"])[:n])

    makasli = [r for r in ilce_satirlari if r["kent"] == r["kent"] and r["kir"] == r["kir"]]
    print("\n=== Kent–kır makası en büyük ilçeler (kent / kır)")
    yaz(sorted(makasli, key=lambda r: -(r["kent"] / r["kir"] if r["kir"] else 0))[:n])

    print("\n=== Gelirin birlikte hareket ettiği şeyler (mahalle düzeyi, hane ağırlıklı)")
    for etiket, alan in [
        ("lisans payı", "lisans"),
        ("hane başına araç", "arac"),
        ("bin kişiye ticari işletme", "ticari"),
        ("65+ payı", "yasli"),
        ("hane büyüklüğü", "hane_kisi"),
    ]:
        print(f"  gelir × {etiket:26} {korelasyon(hepsi, 'gelir', alan):+.3f}")

    kent = [r for r in hepsi if r["tur"] == "centre"]
    kir = [r for r in hepsi if r["tur"] != "centre"]
    print("\n=== Kent ve kır, ülke toplamı (yoğunluk ölçütü: 1.000 kişi/km²)")
    print(f"{'':22}{'Kent':>12}{'Kır':>12}")
    for etiket, alan in [
        ("hane geliri", "gelir"),
        ("hane büyüklüğü", "hane_kisi"),
        ("65+ payı", "yasli"),
        ("lisans payı", "lisans"),
        ("hane başına araç", "arac"),
    ]:
        a, b = ortalama(kent, alan), ortalama(kir, alan)
        bicim = ",.0f" if alan == "gelir" else ".2f"
        print(f"  {etiket:20}{format(a, bicim):>12}{format(b, bicim):>12}")


if __name__ == "__main__":
    main(sys.argv[1:])
