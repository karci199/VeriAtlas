"""Age structure against the vote, neighbourhood by neighbourhood.

Same shape as `gelir_oy.py`, with age where income was. Three orderings, because they are
three different questions and they do not agree:

  * **median age** — interpolated from Endeksa's five-year bands. One number for the whole
    distribution, but blind to shape: a place with many children and many elderly has the
    same median as a place with neither.
  * **share aged 0-14** — the children, who do not vote. This asks how the vote looks where
    fertility is high, not how the young vote.
  * **share aged 65+** — the elderly, who do.

Settlements are cut into groups holding an equal number of *voters*, not an equal number
of settlements, so five hundred emptying villages cannot outweigh one Esenyurt. Every
share is computed from summed counts and weighted by valid votes.

This is ecological. It describes places, not people: a neighbourhood where the young and
the old vote alike cannot be told from one where they cancel out.

Run:  uv run python scripts/yas_oy.py [cb2023t1] [--olcut=ortanca|cocuk|yasli] [--dilim=10]
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
DEM = HAM / "endeksa" / "demography"
TILES = ROOT / "public" / "tiles"

BANDS = [(0, 4), (5, 9), (10, 14), (15, 19), (20, 24), (25, 29), (30, 34),
         (35, 39), (40, 44), (45, 49), (50, 54), (55, 59), (60, 64)]
KEYS = [f"Age_{lo}_{hi}_Total" for lo, hi in BANDS] + ["Age_65_Total"]

ADAYLAR = [
    ("Erdoğan", "ERDOĞAN"),
    ("Kılıçdaroğlu", "KILIÇDAROĞLU"),
    ("Oğan", "SİNAN OĞAN"),
    ("İnce", "İNCE"),
]

OLCUTLER = {
    "ortanca": ("ortanca yas", "ortanca"),
    "cocuk": ("0-14 payi %", "cocuk"),
    "yasli": ("65+ payi %", "yasli"),
}


def median_age(counts: list[float]) -> float | None:
    total = sum(counts)
    if total <= 0:
        return None
    half, running = total / 2, 0.0
    for index, count in enumerate(counts):
        if running + count >= half:
            if index == len(counts) - 1:
                return None
            return BANDS[index][0] + 5 * (half - running) / count if count else None
        running += count
    return None


def oy_tablosu(vote: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in TILES.glob(f"secim-{vote}-mahalle-TR-*.json"):
        for area_id, row in json.loads(path.read_text(encoding="utf-8")).items():
            if area_id.count("-") == 3:
                out[area_id] = row
    return out


def yas_tablosu() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(DEM.glob("TR-*.json")):
        try:
            dump = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for ident, record in dump.items():
            dem = record.get("demography") or {}
            counts = [float(dem.get(k) or 0) for k in KEYS]
            nufus = sum(counts)
            if nufus < 100:
                continue
            ortanca = median_age(counts)
            if ortanca is None:
                continue
            out[f"{path.stem}-{ident}"] = {
                "ad": record.get("name_tr") or "",
                "nufus": nufus,
                "ortanca": ortanca,
                "cocuk": 100 * sum(counts[:3]) / nufus,
                "yasli": 100 * counts[-1] / nufus,
            }
    return out


def pay(row: dict, parca: str) -> float:
    gecerli = row.get("g") or sum(row.get("v", {}).values())
    if not gecerli:
        return 0.0
    return 100 * sum(v for k, v in row.get("v", {}).items() if parca in k.upper()) / gecerli


def dilimler(rows: list[dict], anahtar: str, adet: int) -> list[list[dict]]:
    """Groups holding an equal number of voters, not an equal number of settlements."""
    rows = sorted(rows, key=lambda r: r[anahtar])
    toplam = sum(r["gecerli"] for r in rows)
    hedef = toplam / adet
    gruplar, simdiki, biriken = [], [], 0.0
    for row in rows:
        simdiki.append(row)
        biriken += row["gecerli"]
        if biriken >= hedef and len(gruplar) < adet - 1:
            gruplar.append(simdiki)
            simdiki, biriken = [], 0.0
    if simdiki:
        gruplar.append(simdiki)
    return gruplar


def main(argv: list[str]) -> None:
    vote = next((a for a in argv if not a.startswith("--")), "cb2023t1")
    olcut = next((a.split("=")[1] for a in argv if a.startswith("--olcut=")), "ortanca")
    adet = int(next((a.split("=")[1] for a in argv if a.startswith("--dilim=")), 10))
    if olcut not in OLCUTLER:
        raise SystemExit(f"olcut: {', '.join(OLCUTLER)}")
    baslik, anahtar = OLCUTLER[olcut]

    oylar, yaslar = oy_tablosu(vote), yas_tablosu()
    rows = []
    for area_id, yas in yaslar.items():
        oy = oylar.get(area_id)
        if not oy:
            continue
        gecerli = oy.get("g") or sum(oy.get("v", {}).values())
        if not gecerli:
            continue
        row = dict(yas)
        row["gecerli"] = gecerli
        for etiket, parca in ADAYLAR:
            row[etiket] = pay(oy, parca)
        rows.append(row)

    print(f"{vote} · eslesen yerlesim: {len(rows):,} / {len(yaslar):,} Endeksa · "
          f"gecerli oy: {int(sum(r['gecerli'] for r in rows)):,}")
    print(f"olcut: {baslik}\n")
    basliklar = " ".join(f"{e:>14}" for e, _ in ADAYLAR)
    print(f"{'dilim':>5} {baslik:>13} {'yerlesim':>9} {'gecerli oy':>12} {basliklar}")
    for index, grup in enumerate(dilimler(rows, anahtar, adet), 1):
        gecerli = sum(r["gecerli"] for r in grup)
        orta = sum(r[anahtar] * r["gecerli"] for r in grup) / gecerli
        paylar = " ".join(
            f"{sum(r[e] * r['gecerli'] for r in grup) / gecerli:13.1f}%" for e, _ in ADAYLAR
        )
        print(f"{index:5} {orta:13.1f} {len(grup):9,} {int(gecerli):12,} {paylar}")


if __name__ == "__main__":
    main(sys.argv[1:])
