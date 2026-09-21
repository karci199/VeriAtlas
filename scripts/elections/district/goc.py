"""Did the left collapse in inner Anatolia because people left, or changed vote?

Two measures per district, both relative to the country so the national swing
drops out:
  * lean  - left share minus the national left share (from egilim.py)
  * growth - the district's electorate indexed against national electorate
    growth over the same span. Below 100 means the district lost weight, which
    for a rural district is net out-migration.

If the left fell because its voters moved away, the two move together: shrinking
districts lose the left. If the left fell among people who stayed, there is no
such relationship.

The Alevi district list is NOT data. TUIK publishes no figures on sect, so the
list is an outside approximation assembled from where Alevi populations are
commonly documented, and it is coarse: districts are mixed, and the boundary
cases are judgement calls. Treat every Alevi-labelled result as indicative.
"""

import collections
import csv
import importlib.util
import pathlib
import statistics

BASE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("egilim", BASE / "egilim.py")
eg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eg)
dg, blok = eg.dg, eg.blok

ALEVI = {
    # Tunceli (whole province)
    "tunceli-merkez",
    "cemisgezek",
    "hozat",
    "mazgirt",
    "nazimiye",
    "ovacik",
    "pertek",
    "pulumur",
    # Sivas
    "divrigi",
    "kangal",
    "zara",
    "imranli",
    "hafik",
    "yildizeli",
    "sarkisla",
    "gurun",
    # Malatya
    "arapgir",
    "arguvan",
    "hekimhan",
    "kuluncak",
    "yesilyurt",
    "dogansehir",
    "akcadag",
    # Erzincan
    "kemah",
    "refahiye",
    "tercan",
    "cayirli",
    "ilic",
    "kemaliye",
    "otlukbeli",
    # Erzurum / Mus / Bingol
    "hinis",
    "tekman",
    "varto",
    "kigi",
    "yayladere",
    "adakli",
    "karliova",
    # Kahramanmaras / Adiyaman
    "pazarcik",
    "elbistan",
    "ekinozu",
    "gerger",
    # Karadeniz / Ic Anadolu
    "mesudiye",
    "sebinkarahisar",
    "alucra",
    "almus",
    "gumushacikoy",
    "hamamozu",
    "alaca",
    "mecitozu",
    "sariz",
    "hacibektas",
}


def secmen():
    """(year, district) -> registered voters, on the same keys egilim uses."""
    first, cells = blok.load()
    acc = collections.Counter()
    for (y, il, cevre, birim), v in cells.items():
        if birim == first[(y, cevre)] or blok.SKIP.search(blok.tr_lower(birim)):
            continue
        n = dg.norm(birim)
        if n == dg.norm(il):
            continue
        key = dg.norm(il) + "-merkez" if n == "merkez" or n.endswith("merkez") else n
        acc[(y, key)] += v.get("Kayıtlı seçmen sayısı", 0)
    return acc


def main():
    ser, _ = eg.seriler()
    lean = ser["ilce"]
    sec = secmen()
    y1, y2 = "1977", "2018"

    ulke1 = sum(v for (y, k), v in sec.items() if y == y1)
    ulke2 = sum(v for (y, k), v in sec.items() if y == y2)
    ulke_kat = ulke2 / ulke1

    rows = []
    for k, d in lean.items():
        a, b = eg.donem_ort(d, "1961-77"), eg.donem_ort(d, "1999-23")
        s1, s2 = sec.get((y1, k), 0), sec.get((y2, k), 0)
        if a is None or b is None or s1 < 3000 or s2 < 3000:
            continue
        # The 2013 metropolitan reform redrew districts in 30 provinces; a
        # district that grew several times faster than the country absorbed
        # territory and is no longer the same place.
        if 100 * (s2 / s1) / ulke_kat > 250:
            continue
        rows.append(
            {
                "ilce": k,
                "lean1": a,
                "lean2": b,
                "kayma": b - a,
                "secmen77": s1,
                "secmen18": s2,
                "buyume": 100 * (s2 / s1) / ulke_kat,
                "alevi": k in ALEVI,
            }
        )

    print(f"ülke kayıtlı seçmen {y1}→{y2}: {ulke1:,} → {ulke2:,}  ({ulke_kat:.2f} kat)")
    print(
        f"karşılaştırılan ilçe: {len(rows)}  (Alevi etiketli: {sum(r['alevi'] for r in rows)})"
    )

    ka = [r["kayma"] for r in rows]
    bu = [r["buyume"] for r in rows]
    print(
        f"\nkayma ↔ göreli büyüme korelasyonu: r = {statistics.correlation(ka, bu):+.2f}"
    )

    ale = [r for r in rows if r["alevi"]]
    dig = [r for r in rows if not r["alevi"]]
    print(
        f"\n{'grup':22}{'n':>5}{'ort kayma':>11}{'ort büyüme':>12}{'lean 61-77':>12}{'lean 99-23':>12}"
    )
    for ad, g in (("Alevi yoğun ilçeler", ale), ("diğer ilçeler", dig)):
        print(
            f"{ad:22}{len(g):>5}{statistics.fmean(r['kayma'] for r in g):>+11.1f}"
            f"{statistics.fmean(r['buyume'] for r in g):>12.0f}"
            f"{statistics.fmean(r['lean1'] for r in g):>+12.1f}"
            f"{statistics.fmean(r['lean2'] for r in g):>+12.1f}"
        )

    print("\n### Alevi etiketli ilçeler — tek tek")
    print(
        f"{'':22}{'lean 61-77':>11}{'lean 99-23':>11}{'kayma':>8}{'büyüme':>9}{'seçmen 77':>11}{'seçmen 18':>11}"
    )
    for r in sorted(ale, key=lambda r: r["kayma"]):
        print(
            f"  {r['ilce']:20}{r['lean1']:>+11.1f}{r['lean2']:>+11.1f}{r['kayma']:>+8.1f}"
            f"{r['buyume']:>9.0f}{r['secmen77']:>11,}{r['secmen18']:>11,}"
        )

    dest = BASE / "goc_lean.csv"
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["kayma"]))
    print(f"\n-> {dest}")


if __name__ == "__main__":
    main()
