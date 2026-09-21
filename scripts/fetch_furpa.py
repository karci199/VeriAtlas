r"""Furpa's stores, from the one page that lists them.

`/magazalarimiz` renders a card per store: the district as a small label, the store's
name as a heading, the address, and a Google Maps `<iframe>`. The iframe URL carries the
store's coordinate in Google's `!2d<lng>!3d<lat>` form, which is why this chain lands in
the coordinate family rather than the label one — a Bursa address naming `Osmangazi` is
easy to read, but the point is the thing that decides.

`!2d` is longitude and `!3d` latitude, in that order. Reading them the other way round
puts every Bursa store in the Indian Ocean, and the bounding-box check in the adapter
would drop the lot as "abroad" — a silent zero rather than an error, which is why the
order is written down here.

Furpa is a Bursa chain; the count is regional.

Run:  uv run python scripts/fetch_furpa.py
Out:  C:\veri-ham\furpa\magazalar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import re
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/furpa")
PAGE = "https://www.furpa.com.tr/magazalarimiz"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = ["name", "source_district", "address", "lat", "lng"]

#: One iframe per store, and the store's text follows it. Splitting on the iframe keeps
#: each card's address with its own coordinate.
IFRAME = re.compile(r"<iframe[^>]*!2d(-?\d+\.\d+)!3d(-?\d+\.\d+)[^>]*>", re.IGNORECASE)
CARD_TEXT = re.compile(
    r"<h\d[^>]*>\s*([^<]{3,40}?)\s*</h\d>\s*<h\d[^>]*>\s*([^<]{3,60}?)\s*</h\d>(.{0,400}?)<",
    re.DOTALL,
)
ADDRESS = re.compile(r"((?:Furpa|[A-ZÇĞİÖŞÜ])[^<>]{15,200})", re.DOTALL)

#: 57 stores on 2026-09-20.
MINIMUM = 30


def clean(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def stores() -> list[dict[str, str]]:
    request = urllib.request.Request(
        PAGE, headers={"User-Agent": BROWSER, "Accept-Language": "tr"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        page = response.read().decode("utf-8", "replace")

    rows = []
    # Each store's block runs from its iframe to the next one; the last runs to the end.
    cuts = [match for match in IFRAME.finditer(page)]
    for index, match in enumerate(cuts):
        start = match.end()
        end = cuts[index + 1].start() if index + 1 < len(cuts) else len(page)
        block = page[start:end]
        heads = re.findall(r"<h\d[^>]*>\s*([^<]{3,60}?)\s*</h\d>", block)
        text = clean(block)
        address = ADDRESS.search(text)
        rows.append(
            {
                "name": clean(heads[1])
                if len(heads) > 1
                else (clean(heads[0]) if heads else ""),
                "source_district": clean(heads[0]) if heads else "",
                "address": clean(address.group(1))[:200] if address else "",
                # !2d is longitude, !3d is latitude.
                "lat": match.group(2),
                "lng": match.group(1),
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
    districts = {row["source_district"] for row in rows if row["source_district"]}
    print(f"{len(rows)} mağaza  {len(districts)} ilçe etiketi  -> {path}")


if __name__ == "__main__":
    main()
