r"""Seyhanlar's stores, from the one page that lists them.

`/magazalar` prints one `<article class="store-card" data-district="…">` per store: the
branch name in an `<h2>`, the address in a `<p>` ending `İlçe/Bursa`, the opening hours,
and a "Yol Tarifi" link to `google.com/maps?q=<lat>,<lng>`. The coordinate is in that
link, so this chain lands in the coordinate family — the `data-district` attribute and
the address are saved beside it, not used to place anything.

The article boundary is what makes the parse right. Reading the page as flat text and
splitting on branch names found 4 of 25 stores: the cards run into one another with no
punctuation once the tags are stripped, so the address of one store fell inside the
block of the next and most blocks ended up with no address at all.

**This fetcher turns off TLS certificate verification, deliberately and only here.**
`seyhanlar.com` serves a certificate that does not validate (`CERTIFICATE_VERIFY_FAILED`,
self-signed; all three of `www.seyhanlar.com`, `seyhanlar.com` and the plain-http form
fail the same way). Verification off means we cannot tell the chain's own page from
anything standing between us and it, so it is not a default and not a helper other
fetchers can reach for: the exception is named on this one host, at the user's explicit
instruction (2026-09-20), for a page that carries no credential and no personal data.

If the certificate is ever fixed, delete `INSECURE` and the context with it rather than
leaving a switch that nobody remembers is on.

Seyhanlar is a Bursa chain; the count is regional.

Run:  uv run python scripts/fetch_seyhanlar.py
Out:  C:\veri-ham\seyhanlar\magazalar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import re
import ssl
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/seyhanlar")
PAGE = "https://www.seyhanlar.com/magazalar"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = ["name", "source_district", "address", "hours", "lat", "lng"]

#: See the module docstring. One host, one page, by explicit instruction.
INSECURE = ssl.create_default_context()
INSECURE.check_hostname = False
INSECURE.verify_mode = ssl.CERT_NONE

CARD = re.compile(
    r'<article class="store[^"]*"[^>]*data-district="([^"]*)"(.*?)</article>', re.DOTALL
)
NAME = re.compile(r"<h2[^>]*>(.*?)</h2>", re.DOTALL)
ADDRESS = re.compile(r"<p>(.*?)</p>", re.DOTALL)
HOURS = re.compile(r'store-card-hours"[^>]*>(.*?)<', re.DOTALL)
POINT = re.compile(r"maps\?q=(-?\d+\.\d+),(-?\d+\.\d+)")

#: 25 stores on 2026-09-20.
MINIMUM = 12


def clean(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def stores() -> list[dict[str, str]]:
    request = urllib.request.Request(
        PAGE, headers={"User-Agent": BROWSER, "Accept-Language": "tr"}
    )
    with urllib.request.urlopen(request, timeout=60, context=INSECURE) as response:
        page = response.read().decode("utf-8", "replace")

    rows = []
    for district, card in CARD.findall(page):
        name = NAME.search(card)
        address = ADDRESS.search(card)
        point = POINT.search(card)
        hours = HOURS.search(card)
        if not (name and address):
            continue
        rows.append(
            {
                "name": clean(name.group(1)),
                "source_district": district,
                "address": clean(address.group(1)),
                "hours": clean(hours.group(1)) if hours else "",
                "lat": point.group(1) if point else "",
                "lng": point.group(2) if point else "",
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
