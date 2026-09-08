"""Check that a fetched election report is the table we think it is.

File size does not tell a wrong table from a right one: a report for the wrong year, or a
province list where a candidate list was meant, arrives the same size and the run reports
success. So one file is opened and read: the table's own heading, the year printed in it,
and how many data rows it carries.

Run:  uv run python scripts/dogrula_secim.py aday2023 "adaylar" 2023
"""

from __future__ import annotations

import pathlib
import re
import sys

HAM = pathlib.Path("C:/veri-ham/secim")


def cells(path: pathlib.Path) -> list[str]:
    html = path.read_bytes().decode("iso-8859-9", "replace")
    text = re.sub("<[^>]+>", "|", html).replace("&nbsp;", " ")
    return [c.strip() for c in re.sub(r"\|+", "|", text).split("|") if c.strip()]


def main(vote: str, wanted: str, year: str) -> None:
    folder = HAM / vote
    files = sorted(folder.glob("*.html")) if folder.exists() else []
    print(f"{vote}: {len(files)} dosya")
    if not files:
        raise SystemExit(f"{vote}: hic dosya inmedi")

    sample = files[len(files) // 2]
    body = cells(sample)
    heading = next((c for c in body if "göre" in c or "adaylar" in c.lower()), "")
    rows = [c for c in body if re.fullmatch(r"[\d.]{2,12}", c)]
    print("  ornek:", sample.name)
    print("  baslik:", heading[:100] or "(bulunamadi)")
    print("  sayisal hucre:", len(rows))

    if wanted.lower() not in heading.lower():
        raise SystemExit(f"  YANLIS TABLO — baslikta '{wanted}' yok")
    if year not in heading:
        raise SystemExit(f"  YANLIS YIL — baslikta '{year}' yok")
    if len(rows) < 20:
        raise SystemExit("  RAPOR BOS — 20'den az sayisal hucre")
    print("  dogrulandi")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
