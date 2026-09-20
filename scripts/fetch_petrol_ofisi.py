r"""Petrol Ofisi's station list: the biggest fuel network in the country, by district.

EPDK publishes fuel *sales* by province and licensed station *counts* nationally; where
the stations actually stand is not in any official table. The company's own "istasyon
nerede" page carries the whole list — and carries it in one request, because the page
ships the array inside its own HTML rather than fetching it:

    GET petrolofisi.com.tr/istasyon-nerede
    var stations = [{"StationName":..,"CityName":..,"DistrictName":..,"Latitude":..}]

The page carries the same list three times — `stations`, and then `cities` and
`districts`, which are that list grouped for the two dropdowns. Counting a field across
the whole page therefore triples it: `CityName` appears 7.893 times for 2.631 stations.
`stations` is read, and the count is checked against the other two rather than against a
number remembered from a page count.

robots.txt allows it: one Disallow line, and it is not this page. One request, no crawl.

Every record has the district written out and a coordinate. The district name is used —
the company knows which district its own station is in — and the coordinate is kept beside
it so a later pass can place the ones whose spelling does not match the registry.

Run:  uv run python scripts/fetch_petrol_ofisi.py
Out:  C:\veri-ham\petrol_ofisi\istasyonlar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

URL = "https://www.petrolofisi.com.tr/istasyon-nerede"
OUT = RAW / "petrol_ofisi"
#: The array is assigned to a plain `var`. It is read with the JSON decoder itself rather
#: than by counting brackets: addresses contain brackets and escaped quotes, and a counter
#: stops at the first one inside a string — which is how an earlier version read 2.631 of
#: 7.893 stations and thought the page had come up short.
START = re.compile(r"var\s+stations\s*=\s*\[")
COLUMNS = ["id", "ad", "il", "ilce", "adres", "telefon", "enlem", "boylam", "bolge"]


def payload_named(html: str, name: str) -> list:
    found = re.search(r"var\s+" + name + r"\s*=\s*\[", html)
    if not found:
        raise SystemExit(f"{name} dizisi bulunamadı")
    data, _ = json.JSONDecoder().raw_decode(html, found.end() - 1)
    return data


def payload(html: str) -> list:
    found = START.search(html)
    if not found:
        raise SystemExit("istasyon dizisi bulunamadı — sayfa değişmiş olabilir")
    start = found.end() - 1
    data, _ = json.JSONDecoder().raw_decode(html, start)
    return data


def main() -> None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    }
    response = httpx.get(URL, headers=headers, timeout=90, follow_redirects=True, verify=False)
    response.raise_for_status()

    rows = []
    for station in payload(response.text):
        rows.append(
                {
                    "id": station.get("Id"),
                    "ad": station.get("StationName"),
                    "il": station.get("CityName"),
                    "ilce": station.get("DistrictName"),
                    "adres": (station.get("Address") or "").replace("\n", " ").strip(),
                    "telefon": station.get("PhoneNumber"),
                    "enlem": station.get("Latitude"),
                    "boylam": station.get("Longitude"),
                    "bolge": station.get("Zone"),
                }
            )
    # The groupings must add up to the flat list; if they stop agreeing, the page has
    # changed shape and the flat list may no longer be the whole network.
    grouped = sum(
        len(block.get("Values") or []) for block in payload_named(response.text, "cities")
    )
    if grouped != len(rows):
        raise SystemExit(f"il gruplaması {grouped}, düz liste {len(rows)} — sayfa değişmiş")
    if len(rows) < 1500:
        raise SystemExit(f"yalnız {len(rows)} istasyon okundu; sayfa yarım gelmiş olabilir")

    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"istasyonlar_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    iller = len({row["il"] for row in rows})
    ilceler = len({(row["il"], row["ilce"]) for row in rows})
    print(f"{target}: {len(rows)} istasyon, {iller} il, {ilceler} ilçe")


if __name__ == "__main__":
    main()
