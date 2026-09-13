"""Income rankings by neighbourhood, from the Endeksa dump.

Two readings of the same field, because they answer different questions and disagree:

    hane geliri      what a household earns — the figure Endeksa publishes
    kişi başına      that income spread over the people in it (gelir × hane / nüfus)

A crowded neighbourhood can lead on the first and fall on the second; a small-household
one does the opposite. Ranking on only one of them hides that.

Small places are excluded by a floor (population and household count) rather than trusted:
a modelled income for a hamlet of forty is noise with a decimal point.

Run:  uv run python scripts/gelir_siralamasi.py                # Türkiye, inen iller
      uv run python scripts/gelir_siralamasi.py TR-16-006      # tek ilçe
      uv run python scripts/gelir_siralamasi.py --n=25 --min=1000
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


def satirlar(desen: str, en_az_nufus: int, en_az_hane: int) -> list[dict]:
    iller, ilceler = adlar()
    out: list[dict] = []
    for path in sorted(DEM.glob(desen)):
        try:
            dump = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for record in dump.values():
            dem = record.get("demography") or {}
            nufus = dem.get("PopulationTotal") or 0
            hane = dem.get("HouseholdCount") or 0
            gelir = dem.get("HouseIncome") or 0
            if nufus < en_az_nufus or hane < en_az_hane or not gelir:
                continue
            out.append(
                {
                    "ad": record.get("name_tr") or "",
                    "ilce": ilceler.get(path.stem, path.stem),
                    "il": iller.get(path.stem[:5], ""),
                    "nufus": nufus,
                    "hane": hane,
                    "gelir": gelir,
                    "kisi": gelir * hane / nufus,
                    "hane_kisi": nufus / hane,
                }
            )
    return out


def yaz(baslik: str, rows: list[dict], anahtar: str, n: int) -> None:
    print(f"\n=== {baslik}")
    print(f"{'Mahalle':26}{'İlçe':16}{'İl':13}{'Hane geliri':>13}{'Kişi başı':>12}{'Hane/kişi':>11}")
    for row in sorted(rows, key=lambda r: -r[anahtar])[:n]:
        print(
            f"{row['ad'][:24]:26}{row['ilce'][:14]:16}{row['il'][:11]:13}"
            f"{row['gelir']:>13,.0f}{row['kisi']:>12,.0f}{row['hane_kisi']:>11.2f}"
        )


def main(argv: list[str]) -> None:
    hedef = next((a for a in argv if a.startswith("TR-")), None)
    n = int(next((a.split("=")[1] for a in argv if a.startswith("--n=")), 15))
    en_az_nufus = int(next((a.split("=")[1] for a in argv if a.startswith("--min=")), 500))
    en_az_hane = max(50, en_az_nufus // 4)

    desen = f"{hedef}.json" if hedef else "TR-*.json"
    rows = satirlar(desen, en_az_nufus, en_az_hane)
    kapsam = len(list(DEM.glob(desen)))
    print(
        f"kapsam: {kapsam} ilçe dosyası · {len(rows):,} mahalle "
        f"(nüfus ≥ {en_az_nufus}, hane ≥ {en_az_hane})"
    )
    if not rows:
        return
    yaz("Hane geliri en yüksek", rows, "gelir", n)
    yaz("Kişi başına gelir en yüksek", rows, "kisi", n)

    print("\n=== İl ortalaması (hane ağırlıklı), en yüksek 15")
    iller: dict[str, list[dict]] = {}
    for row in rows:
        iller.setdefault(row["il"], []).append(row)
    ortalama = [
        (
            sum(r["gelir"] * r["hane"] for r in grup) / sum(r["hane"] for r in grup),
            il,
            len(grup),
        )
        for il, grup in iller.items()
        if sum(r["hane"] for r in grup)
    ]
    for gelir, il, sayi in sorted(ortalama, reverse=True)[:15]:
        print(f"  {il[:16]:18}{gelir:>10,.0f} TL/ay   {sayi:>5,} mahalle")


if __name__ == "__main__":
    main(sys.argv[1:])
