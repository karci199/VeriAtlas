r"""Seç Market's dealer list, in one request.

The store page renders nothing server-side, but it loads its data from
`/magazalar/storedata`, which answers with the whole network at once — every province in
one payload, no paging, no key. The response is not plain JSON: it opens with
`var storeData=` and ends with a semicolon, because the page evaluates it as a script
rather than parsing it. The assignment is stripped before decoding.

The payload is keyed by a lowercase province slug (`adana`, `istanbul`, ...) and each key
holds a `data` list of stores with `Name`, `Address`, `City`, `Town` and two phone
numbers. **There is no coordinate**, which is the whole difference between this chain and
the ones `chain_stores` already counts: their district comes from the point falling inside
a boundary, and this one's would have to come from the source's own `Town` label matched
against the registry. That matching is a separate job and is deliberately not done here —
this script saves what the source says and nothing more.

`City` and `Town` arrive upper-case and ASCII-folded in places (`ISTANBUL`, `MUGLA`), so
they are written out verbatim; folding them back is the matcher's problem, not the
fetcher's, and guessing here would hide the ambiguity from whoever does it.

Run:  uv run python scripts/fetch_sec_market.py
Out:  C:\veri-ham\sec_market\magazalar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/sec_market")
PAGE = "https://www.secmarket.com.tr/magazalar"
DATA = "https://www.secmarket.com.tr/magazalar/storedata"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = ["name", "province", "district", "region", "address", "phone"]

#: The endpoint answers only with the store page as referer.
HEADERS = {"User-Agent": BROWSER, "Accept-Language": "tr", "Referer": PAGE}

#: Below this the response is a stub or an error page, not the network: the list held
#: 2.257 stores on 2026-09-20 and a chain does not lose four fifths of itself overnight.
MINIMUM = 500


def payload() -> dict:
    request = urllib.request.Request(DATA, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8", "replace")
    if "storeData=" not in body:
        raise ValueError(f"beklenen 'storeData=' yok; gelen ilk 200: {body[:200]!r}")
    return json.loads(body.split("storeData=", 1)[1].strip().rstrip(";"))


def stores() -> list[dict[str, str]]:
    rows = []
    for group in payload().values():
        for store in group.get("data", []):
            rows.append(
                {
                    "name": store["Name"],
                    "province": store["City"],
                    "district": store["Town"],
                    "region": store["Region"],
                    "address": store["Address"],
                    "phone": store["Phone1"],
                }
            )
    if len(rows) < MINIMUM:
        raise ValueError(f"yalnız {len(rows)} mağaza döndü, en az {MINIMUM} bekleniyor")
    return rows


def main() -> None:
    rows = stores()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"magazalar_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    provinces = {row["province"] for row in rows}
    districts = {(row["province"], row["district"]) for row in rows}
    print(
        f"{len(rows)} mağaza  {len(provinces)} il  {len(districts)} il-ilçe  -> {path}"
    )


if __name__ == "__main__":
    main()
