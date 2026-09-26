"""Registered voters by province, 2002 general election against 2023 (domestic only).

2002 comes from the raw TÜİK report rows "İl toplamı" (C:/veri-ham/secim/mv2002/*.html);
İstanbul, Ankara and İzmir print one total per constituency ("nolu seçim çevresi
toplamı"), summed here. 2023 comes from the district tile.

The district tiles copy a split district's result onto each successor and flag the copy
`eski` (parse_secim.py). A sum that does not skip those rows counts Antalya Merkez three
times. The tile sum for 2002, skipping them, is printed next to the raw figure as a check.

Run from the repository root.
"""

import collections
import csv
import glob
import html
import json
import re
from pathlib import Path

RAW = Path("C:/veri-ham/secim/mv2002")
TILES = Path("public/tiles")
AREAS = Path("src/veriatlas/data/areas_tr.csv")
FILE_PROVINCE = {"Afyon": "Afyonkarahisar", "K.Maraş": "Kahramanmaraş"}
METROS = {"istanbul": "İstanbul", "ankara": "Ankara", "izmir": "İzmir"}


def text(path: str) -> str:
    t = open(path, encoding="cp1254", errors="replace").read()
    t = re.sub(r"<script.*?</script>", " ", t, flags=re.DOTALL)
    t = html.unescape(re.sub(r"<[^>]+>", "|", t))
    return re.sub(r"(\|\s*)+", "|", re.sub(r"\s+", " ", t))


def raw_2002() -> dict[str, int]:
    out: dict[str, int] = {}
    for path in sorted(glob.glob(str(RAW / "*.html"))):
        for m in re.finditer(r"\|\d+\|([^|]+)\|İl toplamı[^|]*\|(\d+)\|", text(path)):
            name = m.group(1).strip()
            out[FILE_PROVINCE.get(name, name)] = int(m.group(2))
    for stem, name in METROS.items():
        per_constituency = {}
        for path in glob.glob(str(RAW / f"{stem}_*.html")):
            part = Path(path).stem.split("__")[0]
            for m in re.finditer(
                r"\|nolu seçim çevresi toplamı[^|]*\|(\d+)\|", text(path)
            ):
                per_constituency[part] = int(m.group(1))
        out[name] = sum(per_constituency.values())
    return out


def tile(election: str) -> dict[str, int]:
    data = json.loads(
        (TILES / f"secim-{election}-ilce.json").read_text(encoding="utf-8")
    )
    out: collections.Counter = collections.Counter()
    for key, row in data.items():
        if "eski" not in row:
            out[key[3:5]] += row["k"]
    return out


def main() -> None:
    names = {
        r["area_id"][3:5]: r["name_tr"]
        for r in csv.DictReader(AREAS.open(encoding="utf-8"))
        if r["area_level"] == "province"
    }
    r02 = raw_2002()
    t02, t23 = tile("mv2002"), tile("mv2023")
    rows = []
    for plate, name in names.items():
        rows.append(
            (
                name,
                r02[name],
                t02[plate],
                t23[plate],
                (t23[plate] / r02[name] - 1) * 100,
            )
        )
    rows.sort(key=lambda r: -r[4])
    off = [r for r in rows if abs(r[2] - r[1]) > 0.01 * r[1]]
    total02, total23 = sum(r[1] for r in rows), sum(r[3] for r in rows)
    print(
        f"Türkiye  2002 {total02:,}  2023 {total23:,}  {(total23 / total02 - 1) * 100:+.1f} %"
    )
    print(f"tile vs raw 2002, provinces off by > 1 %: {len(off)}", [r[0] for r in off])
    print(f"\n{'province':16}{'2002':>12}{'2023':>12}{'change %':>10}")
    for name, a, _, b, pct in rows:
        print(f"{name:16}{a:>12,}{b:>12,}{pct:>10.1f}")


if __name__ == "__main__":
    main()
