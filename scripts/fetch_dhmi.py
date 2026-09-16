r"""Download DHMİ's airport statistics workbooks.

dhmi.gov.tr/Sayfalar/Istatistikler.aspx shows one "Tümünü İndir" workbook per month, but the
year tabs are filled by JavaScript, so only the current year's links are in the HTML. The
files themselves sit at a flat path — `/Lists/Istatislikler/Attachments/<id>/TÜMÜ.xlsx` —
and each workbook says which period it holds in its own header, so the archive is found by
walking the ids and reading the header.

Writes the workbooks to `C:\veri-ham\dhmi\<id>.xlsx` and an index of their headers to
`C:\veri-ham\dhmi\index.json`. 212 files answered in 2026-09: periods 2009-2 … 2026-8.
"""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path

import httpx
import openpyxl

FOLDER = Path("C:/veri-ham/dhmi")
URL = (
    "https://www.dhmi.gov.tr/Lists/Istatislikler/Attachments/{}/"
    + urllib.parse.quote("TÜMÜ.xlsx")
)


def main(last_id: int = 470) -> None:
    FOLDER.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"}, timeout=90, follow_redirects=True
    )
    index: dict[str, list[str]] = {}
    for attachment in range(1, last_id):
        url = URL.format(attachment)
        try:
            if client.head(url).status_code != 200:
                continue
        except httpx.HTTPError:
            continue
        target = FOLDER / f"{attachment}.xlsx"
        if not target.exists():
            target.write_bytes(client.get(url).content)
        book = openpyxl.load_workbook(target, read_only=True, data_only=True)
        sheet = book[book.sheetnames[0]]
        header = next(sheet.iter_rows(min_row=2, max_row=2, values_only=True))
        index[str(attachment)] = [str(cell) for cell in header[:8]]
        book.close()
        print(attachment, index[str(attachment)][1:5], flush=True)
    (FOLDER / "index.json").write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8"
    )
    print(len(index), "dosya")


if __name__ == "__main__":
    main()
