r"""Download Muhasebat's provincial budget revenue workbooks.

muhasebat.hmb.gov.tr is a React front end over a WordPress API: `portal/v2/pages?slug=` returns
the page with a tree of folders (`data-name`, `data-id`), and `portal/v2/files?name=&id=` a
folder's file list. The page "Genel Bütçe Gelirlerinin İller İtibarıyla Tahakkuk ve Tahsilatı"
has one folder a year (2004-2026), each with one workbook per province plus 00-Merkez.

Files go to `C:\veri-ham\muhasebat\<page>\<year>\` with `index.tsv` (year, name, url).
Existing files are not fetched again.
"""

from __future__ import annotations

import html
import re
import sys
import time
from pathlib import Path

import httpx

API = "https://muhasebat.hmb.gov.tr/portal/v2/"
OUT = Path("C:/veri-ham/muhasebat")
PAGES = {
    "genel_butce_gelirleri": "genel-butce-gelirlerinin-iller-itibariyle-tahakkuk-ve-tahsilati-2004-2026",
    "merkezi_yonetim_butcesi": "iller-itibariyle-merkezi-yonetim-butce-istatistikleri-2004-2026",
    "mahalli_yonetim_butcesi": "iller-itibariyle-mahalli-yonetim-butce-istatistikleri-2006-2026",
}


def main() -> None:
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"}, timeout=120, verify=False
    )
    for key, slug in PAGES.items():
        folder = OUT / key
        folder.mkdir(parents=True, exist_ok=True)
        page = client.get(API + "pages", params={"slug": slug}).json()[0]
        nodes = re.findall(
            r'data-name="([^"]+)" data-id="(\d+)"', page["content"]["rendered"]
        )
        index = []
        year = None
        for name, node in nodes:
            name = html.unescape(name)
            found = re.match(r"(\d{4}) Yılı", name)
            if found:
                year = found.group(1)
                continue
            listing = client.get(
                API + "files", params={"name": name, "id": node}
            ).json()
            if not listing:
                continue
            for url, label in re.findall(
                r'href="([^"]+)"[^>]*>([^<]+)</a>',
                listing["content"].replace(r"\/", "/"),
            ):
                target = folder / year / url.rsplit("/", 1)[-1]
                index.append((year, html.unescape(label), url))
                if target.exists():
                    continue
                target.parent.mkdir(exist_ok=True)
                for attempt in range(3):
                    try:
                        data = client.get(url).raise_for_status().content
                        break
                    except httpx.HTTPError:
                        time.sleep(5 * (attempt + 1))
                else:
                    print("HATA", url, flush=True)
                    continue
                target.write_bytes(data)
            print(key, year, name, len(index), flush=True)
        (folder / "index.tsv").write_text(
            "".join("\t".join(r) + "\n" for r in index), encoding="utf-8"
        )
        print(key, "bitti", len(index), "dosya", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
