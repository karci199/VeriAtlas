r"""Peynirci Baba's stores, from the list the store finder renders.

`/magazalarimiz` draws a map and, beside it, a scrollable list where every store is one
`<div class="storeTab" …>` carrying its own data attributes: country, city, district,
a slug, and `data-lat` / `data-lng`. Nothing has to be parsed out of prose — the page
publishes the fields.

**The chain has stores outside Türkiye** and they sit in the same list, told apart only
by `data-country`. They are written out with the country they belong to rather than
dropped, so a reader can see the whole network and the adapter can take the Turkish part
without the count silently changing meaning. The map's own clusters show stores in
Azerbaijan among others.

`data-district` is the source's own label and is saved as `source_district`. The
coordinate is what places a store, as everywhere else.

Run:  uv run python scripts/fetch_peynircibaba.py
Out:  C:\veri-ham\peynircibaba\magazalar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import re
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/peynircibaba")
PAGE = "https://www.peynircibaba.com.tr/magazalarimiz"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = [
    "name",
    "code",
    "country",
    "province",
    "source_district",
    "address",
    "lat",
    "lng",
]

CARD = re.compile(
    r'<div class="storeTab[^"]*"([^>]*)>(.*?)(?=<div class="storeTab|</div>\s*</div>\s*</div>)',
    re.DOTALL,
)
ATTR = re.compile(r'data-([a-z-]+)="([^"]*)"')
NAME = re.compile(r'<h1 class="title[^"]*">(.*?)</h1>', re.DOTALL)
#: The address follows the pin icon; it is the first paragraph-ish run of text after it.
ADDRESS = re.compile(r"</svg>\s*<(?:p|span|div)[^>]*>(.*?)</(?:p|span|div)>", re.DOTALL)

#: 178 stores on 2026-09-20, Türkiye and abroad together. The page mentions each
#: coordinate twice — once in the list, once for the map marker — so a count of the
#: coordinates alone says 357 and is not the store count.
MINIMUM = 150


def clean(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def stores() -> list[dict[str, str]]:
    request = urllib.request.Request(
        PAGE, headers={"User-Agent": BROWSER, "Accept-Language": "tr"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        page = response.read().decode("utf-8", "replace")

    rows = []
    for attributes, body in CARD.findall(page):
        data = dict(ATTR.findall(attributes))
        if not (data.get("lat") and data.get("lng")):
            continue
        name = NAME.search(body)
        address = ADDRESS.search(body)
        rows.append(
            {
                "name": clean(name.group(1)) if name else data.get("code", ""),
                "code": data.get("code", ""),
                "country": data.get("country", ""),
                "province": data.get("city", ""),
                "source_district": data.get("district", ""),
                "address": clean(address.group(1))[:200] if address else "",
                "lat": data["lat"],
                "lng": data["lng"],
            }
        )
    if len(rows) < MINIMUM:
        raise ValueError(
            f"yalnız {len(rows)} mağaza okundu, en az {MINIMUM} bekleniyor"
        )
    return rows


def main() -> None:
    rows = stores()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"magazalar_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    turkiye = sum(1 for row in rows if row["country"] == "turkiye")
    print(f"{len(rows)} mağaza ({turkiye} Türkiye)  -> {path}")


if __name__ == "__main__":
    main()
