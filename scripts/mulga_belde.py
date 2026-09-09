"""The beldeler that were closed, recovered from the population file that still names them.

The 2008 and 2012 metropolitan laws abolished thousands of belde belediyeleri; their
neighbourhoods went under the district and no current table records which town they came
from. Hasanoğlan, Saray, Altınova are still places people name, and nothing official says
what they consist of any more.

But the MEDAS extract of 2007-2012 does. Its rows are written
`İl(İlçe/Belde Bel./Mahalle)-<id>`, and the id is the same id today's neighbourhood series
carries. So the composition of every closed belde is recoverable exactly -- not guessed
from name prefixes, which only works where the neighbourhoods were renamed after the town
(Saray) and fails where they were not (Altınova, whose Yıldırım Beyazıt and Peçenek keep
their own names and belong to no visible group).

Population is today's, summed over those same ids: what the town would be if it still
existed.

Run:  uv run python scripts/mulga_belde.py                 # Ankara
      uv run python scripts/mulga_belde.py --il=BURSA --kod=TR-16
"""

from __future__ import annotations

import collections
import csv
import gzip
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
TUIK = ROOT / "public" / "population-neighbourhood.csv.gz"
#: A belde that became a village rather than a neighbourhood is in the other file.
KOY = ROOT / "public" / "population-village.csv.gz"

#: `Ankara(Elmadağ/Hasanoğlan Bel./Bahçelievler Mah.)-2085`
ROW = re.compile(r"^\|?[^(]+\(([^/]+)/([^/]+?)\s+Bel\./([^)]+)\)-(\d+)")


def beldeler(province: str) -> dict[tuple[str, str], list[str]]:
    """{(district, belde): [neighbourhood ids]} from the 2007-2012 extract."""
    path = HAM / "medas" / "mahalle" / f"nufus-mahalle-{province}-2007_2012.csv"
    if not path.exists():
        raise SystemExit(f"{path} yok")
    out: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            found = ROW.match(line.strip())
            if not found:
                continue
            district, belde, _mahalle, ident = found.groups()
            out[(district.strip(), belde.strip())].add(ident)
    return {k: sorted(v) for k, v in out.items()}


def population(code: str, year: str) -> dict[str, tuple[str, int, int]]:
    """{id: (name, population, under 18)} for one province in one year."""
    out: dict[str, list] = {}
    for path in (TUIK, KOY):
        if not path.exists():
            continue
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if not row["area_id"].startswith(code + "-") or row["year"] != year:
                    continue
                ident = row["area_id"].rsplit("-", 1)[-1]
                value = int(float(row["value"]))
                bag = out.setdefault(ident, [row["area"], 0, 0])
                bag[1] += value
                if row["age"] == "0-17":
                    bag[2] += value
    return {k: (v[0], v[1], v[2]) for k, v in out.items()}


def main(argv: list[str]) -> None:
    province = next((a.split("=")[1] for a in argv if a.startswith("--il=")), "ANKARA")
    code = next((a.split("=")[1] for a in argv if a.startswith("--kod=")), "TR-06")
    year = next((a.split("=")[1] for a in argv if a.startswith("--yil=")), "2025")
    floor = int(next((a.split("=")[1] for a in argv if a.startswith("--min=")), 0))

    towns = beldeler(province)
    people = population(code, year)
    rows = []
    missing = 0
    for (district, belde), idents in towns.items():
        # A row where the belde carries the district's own name is the district
        # municipality, not a town that was closed.
        if belde.casefold() == district.casefold():
            continue
        total = child = found = 0
        for ident in idents:
            row = people.get(ident)
            if not row:
                missing += 1
                continue
            total += row[1]
            child += row[2]
            found += 1
        if total >= floor:
            rows.append((total, belde, district, child, found, len(idents)))
    rows.sort(reverse=True)
    print(
        f"{province} · kapatılmış belde: {len(towns)} · {year} nüfusuyla · "
        f"bugün bulunamayan mahalle {missing}"
    )
    print(f"\n{'Belde (ilçe)':<38}{'mahalle':>9}{'nüfus':>10}{'çocuk%':>9}")
    for total, belde, district, child, found, all_of in rows:
        count = f"{found}/{all_of}" if found != all_of else str(found)
        print(
            f"{belde + ' (' + district + ')':<38}{count:>9}{total:>10,}"
            f"{100 * child / total if total else 0:>8.1f}%"
        )
    print(f"\nToplam: {sum(r[0] for r in rows):,} kişi")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
