r"""Turkcell's digital sales dealer list (PDF) -> one JSON row per dealer, placed.

The PDF (`C:\veri-ham\turkcell\elle\turkcelldijital.pdf`, 195 pages, saved by hand on
2026-09-23) opens with a per-province summary — four columns of "PROVINCE count", read
top to bottom, column by column — and then lists the dealers numbered 1..3.516 in that
same province order, with district, name, type, address and phone but no province.

So the province is assigned by block: the first 105 rows are Adana, the next 28 Adıyaman,
and so on. Three checks make that safe rather than hopeful: the numbers run 1..3.516
without a gap, the summary adds up to 3.516, and the per-type totals the PDF prints on
page 1 (DSNPlus 1.954, DSN 1.185, DSNPlus Extra 372) match the rows. A block that slipped
by one would also show up as districts that do not belong to their province; after
the registry match 31 rows stay unplaced (0,9%), most of them "MERKEZ" in metropolitan
provinces, where the old central district no longer exists.

The district is the row's own label through `areas.resolve_district`; "<PROVINCE>
MERKEZ" becomes "Merkez". A label the registry does not know is left unplaced.

Run:  uv run python scripts/convert_turkcell_pdf.py
"""

from __future__ import annotations

import json
import re
import sys

import pdfplumber

sys.path.insert(0, "src")

from veriatlas.areas import resolve, resolve_district
from veriatlas.config import RAW

FOLDER = RAW / "turkcell" / "elle"
PDF = FOLDER / "turkcelldijital.pdf"
OUT = FOLDER / "turkcelldijital_satirlar.json"
ALIASES = {"AFYON": "AFYONKARAHİSAR"}
EXPECTED = {"DSNPlus": 1954, "DSN": 1185, "DSNPlus EXTRA": 372}


def _title(name: str) -> str:
    words = name.strip().replace("I", "ı").replace("İ", "i").lower().split()
    return " ".join(
        w[:1].replace("i", "İ").replace("ı", "I").upper() + w[1:] for w in words
    )


def main() -> None:
    rows = []
    with pdfplumber.open(PDF) as pdf:
        first = pdf.pages[0].extract_text()
        for page in pdf.pages:
            for table in page.extract_tables():
                for r in table:
                    if r and r[0] and r[0].strip().isdigit():
                        rows.append([(c or "").replace("\n", " ").strip() for c in r])

    summary = first.split("İl Bayi İl Bayi İl Bayi İl Bayi")[1].strip().splitlines()
    columns: list[list[tuple[str, int]]] = [[], [], [], []]
    for line in summary:
        if not re.match(r"^[A-ZÇĞİÖŞÜ]+ \d+( |$)", line):
            continue  # the first dealer rows share the page
        for j, (name, n) in enumerate(re.findall(r"([A-ZÇĞİÖŞÜ]+) (\d+)", line)):
            columns[j].append((name, int(n)))
    order = [pair for column in columns for pair in column]

    numbers = [int(r[0]) for r in rows]
    if numbers != list(range(1, len(rows) + 1)):
        raise SystemExit("sıra numaraları 1..N değil")
    if len(order) != 81 or sum(n for _, n in order) != len(rows):
        raise SystemExit(f"özet {len(order)} il / {sum(n for _, n in order)} bayi")
    kinds = {k: sum(r[3] == k for r in rows) for k in EXPECTED}
    if kinds != EXPECTED:
        raise SystemExit(f"tür toplamları tutmuyor: {kinds}")

    names = [_title(ALIASES.get(name, name)) for name, _ in order]
    provinces = resolve(names, level="province")
    out, start, unplaced = [], 0, 0
    for name, n in order:
        pname = _title(ALIASES.get(name, name))
        pid = provinces[pname]
        for r in rows[start : start + n]:
            label = r[1].strip()
            if label.upper() == "MERKEZ" or label.upper().endswith(" MERKEZ"):
                label = "Merkez"
            try:
                district = resolve_district(pname, _title(label))
            except (KeyError, ValueError):
                district, unplaced = None, unplaced + 1
            out.append(
                {
                    "no": int(r[0]),
                    "il": pid,
                    "ilce_ham": r[1],
                    "ilce": district,
                    "ad": r[2],
                    "tur": r[3],
                    "adres": r[4],
                    "tel": r[5],
                }
            )
        start += n
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"{len(out)} bayi, {unplaced} ilçesiz -> {OUT}")


if __name__ == "__main__":
    main()
