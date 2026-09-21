r"""Turkcell's digital sales points, from the list the company publishes as a PDF.

The store finder on `turkcell.com.tr/hakkimizda/iletisim-merkezi` is a React app whose
dealer endpoint is not reachable from outside the page: the province list is prefetched
into the page state under the key `/dealer/address/v10/cities`, but that path answers 404
when requested on its own, and the search call only fires from a custom dropdown. What
the same page links, in one line of small print, is a PDF of the whole network — which
is the list this script reads.

**This is one kind of outlet, not the whole chain.** The file is titled *Turkcell Dijital
Satış Noktaları* and its `BAYİ TİPİ` column says so for every row (`DSNPlus EXTRA` and
its siblings). Turkcell's own store finder offers five categories — Kurumsal Çözüm
Merkezi, Turkcell Mağazaları, Rampalı Mağazalar, Afet Bölgesi-Konteyner, Engelsiz
Mağazalar — and this file is not their union. The type is carried per row and the count
must never be read as "Turkcell's stores", the same distinction Vodafone's four types
and Türk Telekom's eight force.

Seven columns, in the order the PDF lays them out: trade name, dealer name, dealer type,
address, phone, province, district. Province and district are given as their own fields,
so the district needs no address reading at all.

574 pages on 2026-09-20. The extraction is slow (a minute or two) because each page is
laid out as a table and `pdfplumber` has to reconstruct it; there is no faster path that
keeps the columns aligned.

Run:  uv run python scripts/fetch_turkcell.py
Out:  C:\veri-ham\turkcell\bayiler_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import re
import urllib.request
from pathlib import Path

import pdfplumber

OUT = Path("C:/veri-ham/turkcell")
PDF_URL = (
    "https://s.turkcell.com.tr/SiteAssets/Hakkimizda/tim/"
    "Turkcell%20Dijital%20Sat%C4%B1%C5%9F%20Noktalar%C4%B1.pdf"
)
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = ["trade_name", "name", "kind", "address", "phone", "province", "district"]

#: The header row repeats on every page and is not a dealer.
HEADER = re.compile(
    r"BAY[İI]\s*/?\s*F[İI]RMA|BAY[İI]\s*KODU|BAY[İI]\s*TIP", re.IGNORECASE
)

#: Below this the PDF has changed shape or the download was truncated.
MINIMUM = 2000


def download() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "dijital_satis_noktalari.pdf"
    if not path.exists():
        request = urllib.request.Request(PDF_URL, headers={"User-Agent": BROWSER})
        with urllib.request.urlopen(request, timeout=300) as response:
            path.write_bytes(response.read())
    return path


def clean(cell: str | None) -> str:
    return " ".join((cell or "").split())


def dealers(path: Path) -> list[dict[str, str]]:
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    cells = [clean(c) for c in row]
                    # Seven columns exactly; a short row is a wrapped fragment and a
                    # long one is two dealers the extractor failed to split.
                    if len(cells) != len(COLUMNS):
                        continue
                    if HEADER.search(cells[0]) or not cells[5]:
                        continue
                    rows.append(dict(zip(COLUMNS, cells, strict=True)))
    if len(rows) < MINIMUM:
        raise ValueError(f"yalnız {len(rows)} bayi okundu, en az {MINIMUM} bekleniyor")
    return rows


def main() -> None:
    found = dealers(download())
    path = OUT / f"bayiler_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(found)
    kinds = {row["kind"] for row in found}
    provinces = {row["province"] for row in found}
    print(f"{len(found)} bayi  {len(provinces)} il  {len(kinds)} tür  -> {path}")


if __name__ == "__main__":
    main()
