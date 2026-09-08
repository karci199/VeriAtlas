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


def main(vote: str, wanted: str, year: str = "-") -> None:
    """Check one fetched vote. `year` "-" skips the year check.

    Not every table prints its year: the candidate list is headed "Milletvekili Genel
    Seçimine katılan adaylar" and nothing more, so demanding a year there fails a fetch
    that is in fact correct. Where the heading carries no year, `esler` below is what
    catches a year that did not take — two years whose files are identical came from one
    year asked for twice.
    """
    folder = HAM / vote
    files = sorted(folder.glob("*.html")) if folder.exists() else []
    print(f"{vote}: {len(files)} dosya")
    if not files:
        raise SystemExit(f"{vote}: hic dosya inmedi")

    sample = files[len(files) // 2]
    body = cells(sample)
    heading = next((c for c in body if "göre" in c or "adaylar" in c.lower()), "")
    veri = [
        c for c in body if 2 < len(c) < 60 and "function" not in c and "var " not in c
    ]
    print("  ornek:", sample.name)
    print("  baslik:", heading[:100] or "(bulunamadi)")
    print("  veri hucresi:", len(veri))

    if wanted.lower() not in heading.lower():
        raise SystemExit(f"  YANLIS TABLO — baslikta '{wanted}' yok")
    if year != "-" and year not in heading:
        raise SystemExit(f"  YANLIS YIL — baslikta '{year}' yok")
    if len(veri) < 20:
        raise SystemExit("  RAPOR BOS — 20'den az veri hucresi")
    print("  dogrulandi")


def esler(vote_a: str, vote_b: str) -> None:
    """Two vote folders must not hold the same bytes.

    A year radio that did not take leaves the previous year selected, and the second fetch
    writes the first year's report under the second year's name. Nothing in the file says
    so. Comparing the two folders does.
    """
    a, b = HAM / vote_a, HAM / vote_b
    ortak = {f.name for f in a.glob("*.html")} & {f.name for f in b.glob("*.html")}
    if not ortak:
        print(f"  {vote_a}/{vote_b}: ortak dosya yok, karsilastirilmadi")
        return
    ayni = sum(1 for n in ortak if (a / n).read_bytes() == (b / n).read_bytes())
    print(f"  {vote_a} vs {vote_b}: {len(ortak)} ortak, {ayni} birebir ayni")
    if ayni > len(ortak) // 2:
        raise SystemExit("  YIL UYGULANMAMIS — iki yil ayni raporlari tasiyor")


if __name__ == "__main__":
    if sys.argv[1] == "--esler":
        esler(sys.argv[2], sys.argv[3])
    else:
        main(*sys.argv[1:])
