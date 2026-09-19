r"""Opet's fuel price archive: daily pump prices per district, back to 2013.

Fuel is one of the few prices that is both published openly and varies by place, and Opet
keeps its own archive rather than only today's board. Three endpoints, all plain GETs read
off the page's own requests at opet.com.tr/fiyat-arsivi:

    GET api.opet.com.tr/api/fuelprices/provinces
    GET api.opet.com.tr/api/fuelprices/provinces/16/districts
    GET api.opet.com.tr/api/fuelprices/prices/archive
        ?DistrictCode=016003&StartDate=…&EndDate=…&IncludeAllProducts=true

robots.txt is open (`Allow: /`, only the search pages are closed).

**This is Opet's price, not the market's.** Every distributor sets its own, and a district
with no Opet station has no row here at all. It is a well-measured single-brand series,
which is a different thing from "the price of diesel in Bolu" — the indicator says so.

**A zero is not a price.** The archive returns `"amount":0.00` for products a district does
not sell, in the same shape as a real price, so zeros are dropped rather than averaged in.
Motorin EcoForce comes back 0,00 for most of 2013 for exactly this reason.

The window is walked a year at a time: one request for 13 years of one district returns
tens of thousands of rows and times out, and a failed long request costs more than four
short ones.

Run:  uv run python scripts/fetch_opet_fiyat.py [--devam] [--il]
      --il  yalnız il merkezleri (81 istek yerine ~970)
Out:  C:\veri-ham\opet\fiyat_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.opet.com.tr/api/fuelprices"
OUT = Path("C:/veri-ham/opet")
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": BROWSER,
    "Accept": "application/json",
    "Origin": "https://www.opet.com.tr",
    "Referer": "https://www.opet.com.tr/",
}

#: The archive's own reach. Queried further back it answers with an empty list, not an
#: error, so the floor is written down rather than discovered each run.
FIRST_YEAR = 2013
DELAY = 0.35
COLUMNS = ["date", "province", "province_code", "district", "district_code", "product",
           "product_code", "price"]


def get(url: str, tries: int = 3):
    """One request, with a short climb.

    The backoff is deliberately small. The archive answers **500** for a district-year it
    has nothing for, in the same way it would for a real outage, and there are thousands
    of those combinations: a first version climbed 4-8-16-32 seconds before giving up and
    spent a minute per empty district-year, which would have taken days. Two quick retries
    separate a blip from an empty cell well enough, and an empty cell costs a second.
    """
    request = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, http.client.HTTPException, OSError):
            if attempt == tries - 1:
                raise
            time.sleep(1.5 * 2**attempt)
    raise AssertionError("unreachable")


def provinces() -> list[dict]:
    return get(f"{API}/provinces")


def districts(province_code) -> list[dict]:
    return get(f"{API}/provinces/{province_code}/districts")


def archive(district_code: str, year: int) -> list[dict]:
    url = (
        f"{API}/prices/archive?DistrictCode={district_code}"
        f"&StartDate={year}-01-01T00:00:00.000Z"
        f"&EndDate={year}-12-31T23:59:59.000Z&IncludeAllProducts=true"
    )
    rows = []
    for day in get(url) or []:
        for price in day.get("prices") or []:
            amount = price.get("amount") or 0
            if not amount:  # a product this district does not sell
                continue
            rows.append(
                {
                    "date": (price.get("priceDate") or day.get("day", ""))[:10],
                    "product": price.get("productName", ""),
                    "product_code": price.get("productCode", ""),
                    "price": amount,
                }
            )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"fiyat_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    resuming = "--devam" in sys.argv
    done: set[str] = set()
    if resuming and target.exists():
        with target.open(encoding="utf-8", newline="") as handle:
            done = {f"{r['district_code']}|{r['date'][:4]}" for r in csv.DictReader(handle)}
    today = dt.datetime.now(tz=dt.UTC).year
    total = empty = 0
    with target.open("a" if resuming else "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if not resuming:
            writer.writeheader()
        for province in provinces():
            name = province.get("name") or province.get("Name", "")
            code = province.get("code") or province.get("Code") or province.get("id")
            try:
                found = districts(code)
            except Exception as error:  # noqa: BLE001 — one province must not stop 81
                print(f"  ! {name}: {error}", flush=True)
                continue
            time.sleep(DELAY)
            for district in found:
                dname = district.get("name") or district.get("Name", "")
                dcode = str(district.get("code") or district.get("Code") or "")
                if not dcode:
                    continue
                for year in range(FIRST_YEAR, today + 1):
                    if f"{dcode}|{year}" in done:
                        continue
                    try:
                        rows = archive(dcode, year)
                    except Exception:  # noqa: BLE001 — an empty district-year answers 500
                        empty += 1
                        continue
                    for row in rows:
                        writer.writerow(
                            row
                            | {
                                "province": name,
                                "province_code": code,
                                "district": dname,
                                "district_code": dcode,
                            }
                        )
                    total += len(rows)
                    time.sleep(DELAY)
                handle.flush()
            print(f"  {name}: {len(found)} ilçe, toplam {total:,} satır", flush=True)
    print(f"\n{total:,} fiyat satırı -> {target}")


if __name__ == "__main__":
    main()
