r"""Download the "aylar itibariyle mükellef sayıları" tables of the Revenue Administration (GİB).

gib.gov.tr/kurumsal/planlar-ve-raporlar/istatistikler is a Next.js page whose topic and
year boxes are filled from a catalogue compiled into one JS chunk: `{year, title, links:
[{title, url}]}`. The chunk's name carries a build hash, so it is found from the page's
own script tags rather than hard-coded. Each year of "AYLAR İTİBARİYLE MÜKELLEF
SAYILARI" has twelve tables: active taxpayers by month, Türkiye (odd) and by province
(even) for income tax, income withholding, rental income (GMSİ), simple-method income
tax, corporate tax and VAT. 2002-2003 number them 45-52.

The other catalogue topics (income/corporate tax top-100 and provincial "rekortmen"
lists, Türkiye-wide declaration summaries) are not fetched: the first are named
individuals, the second have no provincial breakdown.

Writes `C:\veri-ham\gib\mukellef\<year>\<file>` and the catalogue beside it
(`catalog.json`); already downloaded files are skipped.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx

FOLDER = Path("C:/veri-ham/gib")
PAGE = "https://www.gib.gov.tr/kurumsal/planlar-ve-raporlar/istatistikler"
FILE_URL = "https://cdn.gib.gov.tr/api/"
TOPIC = "AYLAR İTİBARİYLE MÜKELLEF SAYILARI"


def catalogue(client: httpx.Client) -> list[dict]:
    html = client.get(PAGE).text
    chunks = sorted(set(re.findall(r"/_next/static/chunks/[\w./-]+\.js", html)))
    for path in chunks:
        text = client.get("https://www.gib.gov.tr" + path).text
        if TOPIC not in text:
            continue
        groups = []
        for year, title, links in re.findall(
            r'\{year:"([^"]*)",title:"([^"]*)",links:\[(.*?)\]\}', text
        ):
            groups.append(
                {
                    "year": year,
                    "title": title,
                    "links": [
                        {"title": t, "url": u}
                        for t, u in re.findall(r'title:"([^"]*)",url:"([^"]*)"', links)
                    ],
                }
            )
        return groups
    raise RuntimeError("GİB: katalog parçası bulunamadı")


def main() -> None:
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"}, timeout=120, follow_redirects=True
    )
    groups = catalogue(client)
    FOLDER.mkdir(parents=True, exist_ok=True)
    (FOLDER / "catalog.json").write_text(
        json.dumps(groups, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    for group in groups:
        if group["title"] != TOPIC:
            continue
        folder = FOLDER / "mukellef" / group["year"]
        folder.mkdir(parents=True, exist_ok=True)
        for link in group["links"]:
            target = folder / link["url"].rsplit("/", 1)[1]
            if target.exists():
                continue
            # The CDN answers 429 after about 150 quick requests: pace them and back off.
            for wait in (1, 30, 60, 120, 300):
                time.sleep(wait)
                response = client.get(FILE_URL + link["url"])
                if response.status_code != 429:
                    break
            # An error comes back as a small JSON/HTML body, never as a workbook.
            if response.status_code != 200 or not response.content.startswith(
                (b"\xd0\xcf\x11\xe0", b"PK")
            ):
                print(
                    group["year"], target.name, "HATA", response.status_code, flush=True
                )
                continue
            target.write_bytes(response.content)
        print(group["year"], len(list(folder.iterdir())), "dosya", flush=True)


if __name__ == "__main__":
    main()
