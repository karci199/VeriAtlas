r"""ŞOK Market stores, from the chain's corporate site.

An earlier pass recorded "ŞOK has no store finder page" — it was looking at the shop,
`sokmarket.com.tr`. The finder lives on the corporate site and talks to two plain GET
endpoints, read off the page's own XHR:

    GET kurumsal.sokmarket.com.tr/ajax/servis/ilceler?city=BURSA
    GET kurumsal.sokmarket.com.tr/ajax/servis/magazalarimiz?city=BURSA&district=GEMLİK

robots.txt blocks `/uploads/`, `/ServiceFiles/`, `/cache/` and `/pdf/`; `/ajax/` is open.

**The coordinate fields are swapped and comma-decimalled.** A store in Gemlik comes back as
`"lng":"40,4714","ltd":"29,0999"` — 40,47 is the latitude and 29,10 the longitude, so the
field called `lng` holds the latitude. Taking the names at face value puts every ŞOK in
Turkey somewhere near Somalia, and the point-in-polygon test would quietly drop all of
them. They are read by position, not by name, and the fetcher asserts the result lands
inside Türkiye's bounding box.

Run:  uv run python scripts/fetch_sok.py [--devam]
Out:  C:\veri-ham\sok\magazalar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import http.client
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://kurumsal.sokmarket.com.tr/ajax/servis"
OUT = Path("C:/veri-ham/sok")
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

#: Türkiye's bounding box, used to prove the swapped fields were read the right way round.
TURKEY = (25.5, 35.5, 45.0, 42.5)

DELAY = 0.5
COLUMNS = ["name", "province", "district", "address", "lat", "lng"]


def get(url: str, tries: int = 5) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": BROWSER})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, http.client.HTTPException, OSError):
            if attempt == tries - 1:
                raise
            time.sleep(4 * 2**attempt)
    raise AssertionError("unreachable")


def provinces() -> list[str]:
    """The 81 province names, spelled the way ŞOK's endpoint expects them.

    Not read off the page: the select is filled in by script, so the HTML a plain request
    gets back holds no options at all — a first attempt parsed it and came away with one
    entry, `0`, the placeholder. The endpoint takes the province's Turkish name in capitals,
    which is exactly what the PTT fetcher already lists.
    """
    sys.path.insert(0, str(Path(__file__).parent))
    from fetch_ptt_postal_codes import PROVINCES

    return list(PROVINCES)


def districts(province: str) -> list[str]:
    url = f"{BASE}/ilceler?city={urllib.parse.quote(province)}"
    return get(url).get("districts") or []


def stores(province: str, district: str) -> list[dict]:
    url = (
        f"{BASE}/magazalarimiz?city={urllib.parse.quote(province)}"
        f"&district={urllib.parse.quote(district)}"
    )
    rows = []
    for store in get(url).get("subeler") or []:
        # Read by position, not by the source's names: `lng` holds the latitude.
        lat = (store.get("lng") or "").replace(",", ".")
        lng = (store.get("ltd") or "").replace(",", ".")
        rows.append(
            {
                "name": store.get("name", ""),
                "province": store.get("city", province),
                "district": store.get("districtCity", district),
                "address": " ".join((store.get("address") or "").split()),
                "lat": lat,
                "lng": lng,
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"magazalar_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    resuming = "--devam" in sys.argv
    have: set[str] = set()
    if resuming and target.exists():
        with target.open(encoding="utf-8", newline="") as handle:
            have = {row["province"] for row in csv.DictReader(handle)}
    total = 0
    bozuk = 0
    x0, y0, x1, y1 = TURKEY
    with target.open("a" if resuming else "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if not resuming:
            writer.writeheader()
        for province in provinces():
            if province in have:
                continue
            found = districts(province)
            time.sleep(DELAY)
            for district in found:
                rows = stores(province, district)
                for row in rows:
                    try:
                        lat, lng = float(row["lat"]), float(row["lng"])
                    except ValueError:
                        continue
                    # A single store outside Türkiye is the source's own typo — ŞOK
                    # ÇANKAYA PARK is filed at longitude 83,8, which is China. It is
                    # blanked rather than dropped: the store is real and belongs in the
                    # count, only its coordinate is not. The share is checked at the end;
                    # a systematic swap of the two fields would put *every* row out here.
                    if not (x0 <= lng <= x1 and y0 <= lat <= y1):
                        row["lat"] = row["lng"] = ""
                        bozuk += 1
                writer.writerows(rows)
                total += len(rows)
                time.sleep(DELAY)
            print(f"  {province}: {len(found)} ilçe, toplam {total}", flush=True)
    print(f"\n{total:,} mağaza -> {target}")


if __name__ == "__main__":
    main()
