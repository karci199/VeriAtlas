r"""Gimsa's stores, from the one page that lists them.

`magazalar.php` renders every store as a card: `<h3>` with the name, then a paragraph
whose marker icon is followed by the address, broken across a `<br>` — street on one
line, `İlçe/İL` on the next. Stripping the tags first and reading the whole paragraph is
what keeps the two halves together; a regex that expects the district to sit on the same
line as the street finds nothing here, which is how this page first looked empty.

Each card also holds a Google Maps `<div>`, but they all share the id `googleMap` and
carry no coordinate — the map is drawn from a script the page does not include. So there
is no point to place and the district comes from the address, resolved by
`veriatlas.addresses`.

Gimsa is an Ankara chain; the count is regional and should not be read as national
coverage.

Run:  uv run python scripts/fetch_gimsa.py
Out:  C:\veri-ham\gimsa\magazalar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import re
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/gimsa")
PAGE = "https://www.gimsa.com.tr/magazalar.php"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = ["name", "address", "phone"]

#: The page marks each card with a comment of its own, which is a cleaner boundary than
#: the nested `<div>`s.
CARD = re.compile(
    r"<!--\s*Mağaza Başlangıç\s*-->(.*?)<!--\s*Mağaza Bitiş\s*-->", re.DOTALL
)
NAME = re.compile(r"<h3>(.*?)</h3>", re.DOTALL)
ADDRESS = re.compile(r"map-marker-alt[^>]*></i>(.*?)</p>", re.DOTALL)
PHONE = re.compile(r"Telefon:\s*<a[^>]*>(.*?)</a>", re.DOTALL)

#: Gimsa had 11 stores on 2026-09-20.
MINIMUM = 6


def clean(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def stores() -> list[dict[str, str]]:
    request = urllib.request.Request(
        PAGE, headers={"User-Agent": BROWSER, "Accept-Language": "tr"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        page = response.read().decode("utf-8", "replace")

    rows = []
    for card in CARD.findall(page):
        name = NAME.search(card)
        address = ADDRESS.search(card)
        if not (name and address):
            continue
        phone = PHONE.search(card)
        rows.append(
            {
                "name": clean(name.group(1)),
                "address": clean(address.group(1)),
                "phone": clean(phone.group(1)) if phone else "",
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
    print(f"{len(rows)} mağaza  -> {path}")


if __name__ == "__main__":
    main()
