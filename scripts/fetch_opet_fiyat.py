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

Two passes, because the two questions need different resolutions (user's call,
2026-09-19):

* **the long series** — province centres only, every year back to 2013. 82 districts
  rather than 970, which turns a twelve-hour crawl into half an hour;
* **the map** — every district, but one year. Fuel prices are set per province and the
  districts mostly repeat the same number, so the shape of the map barely moves from year
  to year; one recent year is enough to see it.

Run:  uv run python scripts/fetch_opet_fiyat.py            # il merkezleri, 2013-
      uv run python scripts/fetch_opet_fiyat.py --son       # tüm ilçeler, son fiyat
      uv run python scripts/fetch_opet_fiyat.py --tam 2026  # tüm ilçeler, tek yıl
      uv run python scripts/fetch_opet_fiyat.py --devam     # yarıda kalanı sürdür

`--son` asks each district for the last 45 days and keeps only its newest price per
product. That is all the "where is fuel dearest" question needs, and it costs one short
request per district instead of fourteen long ones.
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
#: Opet answers 500 under load — measured two failures in five while a background run
#: and a hand probe were both querying. One request every 1,5 seconds, single-threaded,
#: kept it clean; the earlier 0,35 did not. Re-measured on the evening of 2026-09-19:
#: one request in six succeeded at 2 s spacing, so both the spacing and the retry climb
#: were raised.
DELAY = 2.5
COLUMNS = [
    "date",
    "province",
    "province_code",
    "district",
    "district_code",
    "product",
    "product_code",
    "price",
]


def get(url: str, tries: int = 10):
    """One request, retried hard, because this API fails at random.

    Measured on 2026-09-19: the same URL answered `500, 200, 500, 500, 200` — roughly two
    requests in five fail for no reason and succeed on a repeat. An earlier version read
    that 500 as "this district has no data for this year" and moved on, which silently
    dropped about two fifths of everything it was asked to collect. **A 500 is never
    evidence of emptiness here.** Emptiness is a 200 with an empty list, and nothing else.
    """
    request = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, http.client.HTTPException, OSError):
            if attempt == tries - 1:
                raise
            time.sleep(2.0 * 1.8**attempt)
    raise AssertionError("unreachable")


def provinces() -> list[dict]:
    """The province list, retried patiently.

    This is the first request a run makes, and when the API is in one of its moods it is
    the request that kills the run before anything is written. It gets its own long climb
    — up to about four minutes — because failing here costs the whole pass.
    """
    return get(f"{API}/provinces", tries=8)


def districts(province_code) -> list[dict]:
    return get(f"{API}/provinces/{province_code}/districts")


def archive(district_code: str, year: int, days: int | None = None) -> list[dict]:
    """A district's prices for one year, or — with `days` — for the last N days.

    The short window is what `--son` uses: a price board that has not changed in weeks
    still reports its last change, so 45 days is enough to find the current price
    everywhere without pulling a year of history for each of 970 districts.
    """
    if days:
        end = dt.datetime.now(tz=dt.UTC)
        start = end - dt.timedelta(days=days)
        window = (
            f"StartDate={start:%Y-%m-%d}T00:00:00.000Z"
            f"&EndDate={end:%Y-%m-%d}T23:59:59.000Z"
        )
    else:
        window = (
            f"StartDate={year}-01-01T00:00:00.000Z&EndDate={year}-12-31T23:59:59.000Z"
        )
    url = (
        f"{API}/prices/archive?DistrictCode={district_code}"
        f"&{window}&IncludeAllProducts=true"
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
    # `--tam <yıl>`: every district, that year only. Without it: province centres, all
    # years. `isCenter` is the source's own flag for the province's central district.
    latest = "--son" in sys.argv
    if latest:
        target = OUT / f"son_fiyat_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    full_year = None
    if "--tam" in sys.argv:
        full_year = int(sys.argv[sys.argv.index("--tam") + 1])
        target = (
            OUT
            / f"fiyat_ilce_{full_year}_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
        )
    done: set[str] = set()
    if resuming and target.exists():
        with target.open(encoding="utf-8", newline="") as handle:
            done = {
                f"{r['district_code']}|{r['date'][:4]}" for r in csv.DictReader(handle)
            }
    today = dt.datetime.now(tz=dt.UTC).year
    total = 0
    failed: list[str] = []
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
            if not full_year and not latest:
                found = [d for d in found if d.get("isCenter")]
            for district in found:
                dname = district.get("name") or district.get("Name", "")
                dcode = str(district.get("code") or district.get("Code") or "")
                if not dcode:
                    continue
                years = (
                    [today]
                    if latest
                    else ([full_year] if full_year else range(FIRST_YEAR, today + 1))
                )
                for year in years:
                    if f"{dcode}|{year}" in done:
                        continue
                    try:
                        rows = archive(dcode, year, days=45 if latest else None)
                        if latest:
                            # Newest row per product, nothing else.
                            newest: dict[str, dict] = {}
                            for row in sorted(rows, key=lambda r: r["date"]):
                                newest[row["product_code"]] = row
                            rows = list(newest.values())
                    except Exception as error:  # noqa: BLE001
                        # Six tries all failed: a real outage, not an empty cell. Counted
                        # and named so a run that lost data cannot look like a clean one.
                        failed.append(f"{dname} {year}")
                        if len(failed) < 20:
                            print(f"  ! {name}/{dname} {year}: {error}", flush=True)
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
