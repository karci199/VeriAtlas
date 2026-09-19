r"""Maritime statistics from the Ministry of Transport's own portal.

`denizcilikistatistikleri.uab.gov.tr` publishes cargo handled, containers, ship calls,
cruise passengers and Ro-Ro vehicles as Excel workbooks, one page per year. The cut that
matters here is **liman başkanlıkları bazında** — by port authority, which is a place, so
it carries to provinces; the rest (by country, by cargo group, by month) is Türkiye-wide.

robots.txt allows the pages and blocks `/api` and `/web-api`, so the files are taken from
the page links, never from the site's own API.

The file names carry a hash, not a meaning — `aylar-bazinda-yuk-ellecleme-69803fe7eb88b.xls`
— and the same page holds sixty of them. They are saved under the year and the slug that
precedes the hash, numbered in page order, so a re-run overwrites rather than accumulates.

Run:  uv run python scripts/fetch_uab_denizcilik.py
Out:  C:\veri-ham\uab\<konu>-<yil>\<slug>-<n>.xls
"""

from __future__ import annotations

import re
import sys
import time

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

BASE = "https://denizcilikistatistikleri.uab.gov.tr"
OUT = RAW / "uab"
PAUSE = 1.0

#: The five statistics published one page per year. 2020 is the portal's floor.
TOPICS = ("yuk", "konteyner", "gemi", "kruvaziyer", "ro-ro-arac")
YEARS = range(2020, 2027)

#: Sections that hold every year on a single page rather than one page per year. The
#: archive is where the pre-2020 port tables live, and the straits page is the only count
#: of Bosphorus and Dardanelles transits anywhere.
SINGLE_PAGES = (
    "arsiv",
    "filo-istatistikleri",
    "kabotaj-istatistikleri",
    "turk-bogazlari-gemi-gecis-istatistikleri",
    "diger-istatistikler",
)

FILE = re.compile(r'href="(https://[^"]+\.xlsx?)"')
#: The two magic numbers a workbook starts with: BIFF (.xls) and zip (.xlsx).
XLS, XLSX = b"\xd0\xcf", b"PK"


def slug_of(url: str) -> str:
    """`.../liman-baskanliklari-bazinda-yuk-ellecleme-6980abc.xls` → the slug."""
    name = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return name.rsplit("-", 1)[0]


def main() -> None:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; VeriAtlas/1.0)"}
    saved = skipped = 0
    with httpx.Client(
        base_url=BASE,
        headers=headers,
        timeout=90,
        follow_redirects=True,
        verify=False,
    ) as client:
        for topic in TOPICS:
            for year in YEARS:
                page = f"/{topic}-istatistikleri-{year}"
                response = client.get(page)
                if response.status_code != 200:
                    skipped += 1
                    continue
                links = list(dict.fromkeys(FILE.findall(response.text)))
                folder = OUT / f"{topic}-{year}"
                folder.mkdir(parents=True, exist_ok=True)
                counts: dict[str, int] = {}
                for url in links:
                    slug = slug_of(url)
                    counts[slug] = counts.get(slug, 0) + 1
                    target = folder / f"{slug}-{counts[slug]:02d}.xls"
                    if target.exists():
                        continue
                    data = client.get(url)
                    if data.status_code != 200 or not data.content[:2] in (
                        b"\xd0\xcf",
                        b"PK",
                    ):
                        # A page that answers 200 with HTML is not a workbook; an error is
                        # never data, so nothing is written under a name that claims it is.
                        print(page, slug, data.status_code, "atlandi")
                        continue
                    target.write_bytes(data.content)
                    saved += 1
                    time.sleep(PAUSE)
                print(f"{topic}-{year}: {len(links)} bağlantı")
                time.sleep(PAUSE)
        for page_name in SINGLE_PAGES:
            response = client.get("/" + page_name)
            if response.status_code != 200:
                skipped += 1
                continue
            links = list(dict.fromkeys(FILE.findall(response.text)))
            folder = OUT / page_name
            folder.mkdir(parents=True, exist_ok=True)
            counts = {}
            for url in links:
                slug = slug_of(url)
                counts[slug] = counts.get(slug, 0) + 1
                target = folder / f"{slug}-{counts[slug]:02d}.xls"
                if target.exists():
                    continue
                data = client.get(url)
                if data.status_code != 200 or data.content[:2] not in (XLS, XLSX):
                    print(page_name, slug, data.status_code, "atlandi")
                    continue
                target.write_bytes(data.content)
                saved += 1
                time.sleep(PAUSE)
            print(f"{page_name}: {len(links)} bağlantı")
            time.sleep(PAUSE)

    print("indirilen", saved, "| bulunmayan sayfa", skipped)


if __name__ == "__main__":
    main()
