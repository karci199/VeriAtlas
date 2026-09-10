"""Data-quality flags for neighbourhoods, so an average is not taken over a prison.

Three of Endeksa's fields are ratios of things counted separately — population, households,
dwellings — and where those three do not describe an ordinary residential place the ratios
go somewhere no household ever goes. Each such place is a real settlement with real votes
in it, so it cannot simply be dropped; it has to be named, and the analysis decides.

    kurumsal   people per household above 8 and men above 85% — a prison, barracks,
               dormitory or construction camp. Population is counted, households are not.
    paylasimli people per household above 8 but children below 12% and men not dominant —
               shared housing: seasonal farm labour, student flats.
    ticari     people per household below 2 with no children — an address register full of
               offices. Asmalı Mescit has 417 residents and 247 "households".
    bosalmis   the same, but in a village or where a quarter of the residents are over 65 —
               the house is still standing and the family has gone.
    ikinci_ev  dwellings per household above 3 with a summer-resort share — the coast and
               the yayla, where most of the housing stock is empty most of the year.
    bos_kirsal dwellings per household above 3 in a village with no summer resorts — the
               houses outlived the village.
    stok       the same in a town — housing built and not yet sold. Dursunköy has 77
               dwellings per household and not one summer resort.
    yikim      dwellings per household below 0.7 — the housing is gone and the households
               are still on the register. Every one of these is in the earthquake zone.

The thresholds are read off the distributions rather than chosen: the ordinary range is
2-8 people and 0.7-3 dwellings per household, and what falls outside is a different kind of
place, not an extreme example of the same kind.

Run:  uv run python scripts/mahalle_bayrak.py [--yaz]   # --yaz: public/tiles/mahalle-bayrak.json
"""

from __future__ import annotations

import collections
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
DEM = HAM / "endeksa" / "demography"
OUT = ROOT / "public" / "tiles" / "mahalle-bayrak.json"


def bayrakla(dem: dict) -> list[str]:
    """The flags this neighbourhood earns. Empty list is the ordinary case."""
    nufus = dem.get("PopulationTotal") or 0
    hane = dem.get("HouseholdCount") or 0
    konut = dem.get("HousingCount") or 0
    if nufus < 100 or hane < 20:
        return ["kucuk"]

    kisi = nufus / hane
    erkek = 100 * (dem.get("PopulationMale") or 0) / nufus
    cocuk = 100 * sum(
        (dem.get(f"Age_{a}_{b}_Total") or 0) for a, b in ((0, 4), (5, 9), (10, 14))
    ) / nufus
    yazlik = 100 * (dem.get("SummerResortCount") or 0) / konut if konut else 0
    yasli = 100 * (dem.get("Age_65_Total") or 0) / nufus
    # Village or town: the same ratio means different things in each, and the source says
    # which it is. A village with two people per household is emptying; a city centre with
    # two people per household is full of offices.
    # `DistrictType` is filled for municipal quarters and left empty for villages, so it
    # cannot be tested for "KÖY" — `IsMunicipality` is the field that actually separates
    # them, and it agrees with the name ending in every record checked.
    koy = not dem.get("IsMunicipality")

    out = []
    if kisi > 8:
        out.append("kurumsal" if erkek > 85 else "paylasimli")
    elif kisi < 2 and cocuk < 5:
        # Few people per household and no children is either an emptied village, where
        # the remaining residents are old, or a business district, where they are not.
        out.append("bosalmis" if (koy or yasli > 25) else "ticari")
    if konut and hane:
        oran = konut / hane
        if oran > 3:
            if yazlik >= 5:
                out.append("ikinci_ev")
            elif koy:
                out.append("bos_kirsal")  # the village's houses outlive the village
            else:
                out.append("stok")
        elif oran < 0.7:
            out.append("yikim")
    return out


def main(argv: list[str]) -> None:
    bayrak: dict[str, list[str]] = {}
    sayac = collections.Counter()
    ornek = collections.defaultdict(list)
    toplam = 0
    for path in sorted(DEM.glob("TR-*.json")):
        for ident, kayit in json.loads(path.read_text(encoding="utf-8")).items():
            dem = kayit.get("demography") or {}
            if not dem:
                continue
            toplam += 1
            isaret = bayrakla(dem)
            if not isaret:
                continue
            area = f"{path.stem}-{ident}"
            bayrak[area] = isaret
            for ad in isaret:
                sayac[ad] += 1
                if len(ornek[ad]) < 6:
                    ornek[ad].append(
                        f"{kayit.get('name_tr', '')[:18]}/{dem.get('CountyName', '')[:12]}"
                        f" ({dem.get('CityName', '')[:10]})"
                    )

    print(f"mahalle: {toplam:,} · isaretli: {len(bayrak):,} "
          f"(%{100 * len(bayrak) / toplam:.1f})")
    for ad, adet in sayac.most_common():
        print(f"\n{ad:11} {adet:6,}  %{100 * adet / toplam:4.1f}")
        print("   " + " · ".join(ornek[ad]))

    if "--yaz" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(bayrak, ensure_ascii=False), encoding="utf-8")
        print(f"\nyazildi: {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main(sys.argv[1:])
