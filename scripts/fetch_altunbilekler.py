r"""Altunbilekler's stores, from the one page that lists them.

`altunbilekler.com/magazalar` prints a block per store: an `<h…>` with the store's name,
then the address on its own line ending `İlçe/Ankara`, then a phone. The `.com.tr`
domain serves a 3 KB shell with nothing in it — the list is only on `.com`.

The maps under each store are `<iframe>` embeds with no coordinate in the URL, so there
is no point to place: the district comes from the address, resolved by
`veriatlas.addresses`.

**The first block is the warehouse, not a store.** `Ana Depo Altunbilekler` is the
chain's distribution centre and `Hal Altunbilekler` is its stand at the wholesale
produce market; neither sells to shoppers. They are written out with a `kind` of
`depo` rather than dropped, because a reader counting stores should be able to see what
was excluded and why.

Run:  uv run python scripts/fetch_altunbilekler.py
Out:  C:\veri-ham\altunbilekler\magazalar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import re
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/altunbilekler")
PAGE = "https://www.altunbilekler.com/magazalar"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = ["name", "kind", "address", "phone"]

HEADING = re.compile(r"<h\d[^>]*>\s*([^<]{4,80}?)\s*</h\d>", re.IGNORECASE)
ADDRESS = re.compile(
    r"([A-ZÇĞİÖŞÜ][^<>]{10,120}?/\s*[A-Za-zÇĞİÖŞÜçğıöşü]+)\s*<", re.DOTALL
)
PHONE = re.compile(r"T:\s*([\d()\s]{9,20})")

#: Blocks that are not shops. Matched on the heading, which is where the page says so.
NOT_A_SHOP = re.compile(r"(?:Ana\s*Depo|^Hal\b)", re.IGNORECASE)

#: 46 store blocks on 2026-09-20.
MINIMUM = 20


def clean(text: str) -> str:
    return " ".join(html.unescape(text).split())


def stores() -> list[dict[str, str]]:
    request = urllib.request.Request(
        PAGE, headers={"User-Agent": BROWSER, "Accept-Language": "tr"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        page = response.read().decode("utf-8", "replace")

    # Split on the headings so each store's address cannot be read out of the next
    # store's block: the page has no container per store, only a run of siblings.
    parts = HEADING.split(page)
    rows = []
    for index in range(1, len(parts) - 1, 2):
        name = clean(parts[index])
        if "Altunbilekler" not in name:
            continue
        block = parts[index + 1]
        address = ADDRESS.search(block)
        if address is None:
            continue
        phone = PHONE.search(block)
        rows.append(
            {
                "name": name,
                "kind": "depo" if NOT_A_SHOP.search(name) else "magaza",
                "address": clean(address.group(1)),
                "phone": clean(phone.group(1)) if phone else "",
            }
        )
    if len(rows) < MINIMUM:
        raise ValueError(f"yalnız {len(rows)} blok okundu, en az {MINIMUM} bekleniyor")
    return rows


def main() -> None:
    rows = stores()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"magazalar_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    shops = sum(1 for row in rows if row["kind"] == "magaza")
    print(f"{shops} mağaza + {len(rows) - shops} depo  -> {path}")


if __name__ == "__main__":
    main()
