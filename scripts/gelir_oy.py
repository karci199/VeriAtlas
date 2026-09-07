"""Income against the vote, neighbourhood by neighbourhood.

Two tables that must be read together:

  * **deciles of income** — settlements sorted by household income and cut into ten groups
    holding an equal number of *voters*, not an equal number of settlements. A group of
    equal settlement counts would let five hundred villages outweigh Çankaya.
  * **within district** — the same comparison after each settlement is measured against
    its own district's mean. Income is higher in the west and the west votes differently,
    so the raw gradient partly measures geography; the within-district version asks the
    narrower question "among neighbours, does the richer one vote differently".

Everything is weighted by valid votes. Shares are computed from summed counts, never
averaged from the settlements' own shares.

This is an ecological reading: it describes settlements, not people. A neighbourhood where
rich and poor vote alike is indistinguishable from one where they cancel out.

Income is Endeksa's modelled household income, not a measurement — it is a good ordering
of places and a poor statement about any one of them.

Run:  uv run python scripts/gelir_oy.py [cb2023t1] [--dilim=10]
"""

from __future__ import annotations

import json
import math
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
DEM = HAM / "endeksa" / "demography"
TILES = ROOT / "public" / "tiles"

#: (etiket, adın ayırt edici parçası). Parçalar özellikle seçildi: "OĞAN" hem SİNAN OĞAN'a
#: hem ERDOĞAN'a uyuyor ve Oğan sütununa Erdoğan'ın oylarını yazıyordu.
ADAYLAR = [
    ("Erdoğan", "ERDO"),
    ("Kılıçdaroğlu", "KILI"),
    ("Oğan", "SİNAN"),
    ("İnce", "MUHARREM"),
]


def oy_tablosu(vote: str) -> dict[str, dict]:
    """{area_id: {k, o, g, v}} for every settlement, from the per-province detail files."""
    out: dict[str, dict] = {}
    for path in TILES.glob(f"secim-{vote}-mahalle-TR-*.json"):
        for area_id, row in json.loads(path.read_text(encoding="utf-8")).items():
            if area_id.count("-") == 3:
                out[area_id] = row
    return out


def gelir_tablosu() -> dict[str, dict]:
    """{area_id: {gelir, nufus, hane, ...}} from the Endeksa dump."""
    out: dict[str, dict] = {}
    for path in sorted(DEM.glob("TR-*.json")):
        try:
            dump = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for ident, record in dump.items():
            dem = record.get("demography") or {}
            nufus = dem.get("PopulationTotal") or 0
            hane = dem.get("HouseholdCount") or 0
            gelir = dem.get("HouseIncome") or 0
            if not (nufus and hane and gelir):
                continue
            out[f"{path.stem}-{ident}"] = {
                "ad": record.get("name_tr") or "",
                "ilce": path.stem,
                "gelir": gelir,
                "kisi": gelir * hane / nufus,
                "nufus": nufus,
                "yasli": (dem.get("Age_65_Total") or 0) / nufus,
                "lisans": (dem.get("EduLicenseDegree") or 0)
                / (dem.get("EducationTotal") or 1),
            }
    return out


def pay(row: dict, parca: str) -> float:
    gecerli = row.get("g") or sum(row.get("v", {}).values())
    if not gecerli:
        return 0.0
    toplam = sum(v for k, v in row.get("v", {}).items() if parca in k.upper())
    return toplam / gecerli


def agirlikli_korelasyon(rows: list[dict], x: str, y: str) -> float:
    """Pearson, weighted by valid votes."""
    w = sum(r["agirlik"] for r in rows)
    if not w:
        return float("nan")
    mx = sum(r[x] * r["agirlik"] for r in rows) / w
    my = sum(r[y] * r["agirlik"] for r in rows) / w
    sxy = sum(r["agirlik"] * (r[x] - mx) * (r[y] - my) for r in rows)
    sxx = sum(r["agirlik"] * (r[x] - mx) ** 2 for r in rows)
    syy = sum(r["agirlik"] * (r[y] - my) ** 2 for r in rows)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else float("nan")


def dilimler(rows: list[dict], anahtar: str, adet: int) -> list[list[dict]]:
    """Groups holding an equal number of voters, ordered by `anahtar`."""
    sirali = sorted(rows, key=lambda r: r[anahtar])
    toplam = sum(r["agirlik"] for r in sirali)
    hedef = toplam / adet
    out: list[list[dict]] = [[]]
    birikim = 0.0
    for row in sirali:
        out[-1].append(row)
        birikim += row["agirlik"]
        if birikim >= hedef and len(out) < adet:
            out.append([])
            birikim = 0.0
    return out


def ozet(grup: list[dict]) -> dict:
    oy = sum(r["agirlik"] for r in grup)
    return {
        "n": len(grup),
        "oy": oy,
        "gelir": sum(r["gelir"] * r["agirlik"] for r in grup) / oy if oy else 0,
        "katilim": sum(r["katilim"] * r["agirlik"] for r in grup) / oy if oy else 0,
        **{
            ad: sum(r[ad] * r["agirlik"] for r in grup) / oy if oy else 0
            for ad, _ in ADAYLAR
        },
    }


def main(argv: list[str]) -> None:
    vote = next((a for a in argv if not a.startswith("--")), "cb2023t1")
    adet = int(next((a.split("=")[1] for a in argv if a.startswith("--dilim=")), 10))

    oylar = oy_tablosu(vote)
    gelirler = gelir_tablosu()
    rows: list[dict] = []
    for area_id, gelir in gelirler.items():
        oy = oylar.get(area_id)
        if not oy:
            continue
        gecerli = oy.get("g") or sum(oy.get("v", {}).values())
        if gecerli < 100:
            continue
        rows.append(
            {
                **gelir,
                "agirlik": gecerli,
                "katilim": (oy.get("o") or 0) / (oy.get("k") or 1),
                **{ad: pay(oy, parca) for ad, parca in ADAYLAR},
            }
        )

    print(
        f"{vote}: {len(rows):,} yerleşim eşleşti "
        f"({len(gelirler):,} gelirli, {len(oylar):,} oylu) · "
        f"{sum(r['agirlik'] for r in rows):,.0f} geçerli oy"
    )
    if len(rows) < 50:
        print("çok az eşleşme — Endeksa çekimi ilerleyince tekrar çalıştır")
        return

    baslik = f"{'Dilim':7}{'Hane geliri':>13}{'Katılım':>9}" + "".join(
        f"{ad:>15}" for ad, _ in ADAYLAR
    )
    print("\n=== Hane gelirine göre onda birlik dilimler (eşit sayıda seçmen)")
    print(baslik)
    for i, grup in enumerate(dilimler(rows, "gelir", adet), 1):
        s = ozet(grup)
        print(
            f"{i:<7}{s['gelir']:>13,.0f}{100 * s['katilim']:>8.1f}%"
            + "".join(f"{100 * s[ad]:>14.1f}%" for ad, _ in ADAYLAR)
        )

    # Within district: each settlement against its own district's vote-weighted mean.
    ilce_ortalama: dict[str, dict] = {}
    for row in rows:
        acc = ilce_ortalama.setdefault(row["ilce"], {"w": 0.0, "gelir": 0.0, **{ad: 0.0 for ad, _ in ADAYLAR}})
        acc["w"] += row["agirlik"]
        acc["gelir"] += row["gelir"] * row["agirlik"]
        for ad, _ in ADAYLAR:
            acc[ad] += row[ad] * row["agirlik"]
    fark_rows = []
    for row in rows:
        acc = ilce_ortalama[row["ilce"]]
        if acc["w"] < 1000:
            continue
        fark_rows.append(
            {
                "agirlik": row["agirlik"],
                "gelir": row["gelir"] - acc["gelir"] / acc["w"],
                **{ad: row[ad] - acc[ad] / acc["w"] for ad, _ in ADAYLAR},
            }
        )

    print("\n=== İlçe ortalamasından sapma (aynı ilçenin mahalleleri arasında)")
    print(f"{'Dilim':7}{'Gelir farkı':>13}" + "".join(f"{ad:>15}" for ad, _ in ADAYLAR))
    for i, grup in enumerate(dilimler(fark_rows, "gelir", adet), 1):
        oy = sum(r["agirlik"] for r in grup)
        print(
            f"{i:<7}{sum(r['gelir'] * r['agirlik'] for r in grup) / oy:>+13,.0f}"
            + "".join(
                f"{100 * sum(r[ad] * r['agirlik'] for r in grup) / oy:>+14.1f}%"
                for ad, _ in ADAYLAR
            )
        )

    print("\n=== Ağırlıklı korelasyon (oy ağırlıklı)")
    for ad, _ in ADAYLAR:
        ham = agirlikli_korelasyon(rows, "gelir", ad)
        ic = agirlikli_korelasyon(fark_rows, "gelir", ad)
        print(f"  gelir × {ad:14} ham {ham:+.3f}   ilçe içi {ic:+.3f}")
    print(f"  gelir × {'katılım':14} ham {agirlikli_korelasyon(rows, 'gelir', 'katilim'):+.3f}")
    print(f"  gelir × {'65+ payı':14} ham {agirlikli_korelasyon(rows, 'gelir', 'yasli'):+.3f}")
    print(f"  gelir × {'lisans payı':14} ham {agirlikli_korelasyon(rows, 'gelir', 'lisans'):+.3f}")


if __name__ == "__main__":
    main(sys.argv[1:])
