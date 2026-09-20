r"""Domino's Pizza branches, crawled through the chain's own province and district pages.

Domino's publishes a page per province (`/subeler/<il>`) that links a page per district
(`/subeler/<il>/<ilce>`), and the district page carries every branch in it. There is no
JSON endpoint and none is needed: the district page ships the branches it is about to draw
inside a `<script id="__districtStores_INITIAL_STATE__" type="application/json">` block,
with name, address and coordinate per branch. That block is read rather than the rendered
HTML — the same page prints the coordinate a second time inside a "Haritada Göster" link,
and counting those would double every branch that happens to be listed twice.

The province and district names come from the chain's own URL slugs and are kept as such —
the adapter places branches by coordinate, so a slug that folds `ç/ş/ı` away costs nothing
here. That is also why the district page is crawled rather than the province page: the
province page shows no branches, only the district links.

robots.txt allows this; it only blocks tracking parameters (`?utm_source` and friends).

Run:  uv run python scripts/fetch_dominos.py
Out:  C:\veri-ham\dominos\subeler_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://www.dominos.com.tr"
OUT = Path("C:/veri-ham/dominos")

BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

#: `/subeler/istanbul` on the index, `/subeler/bolu/merkez` on a province page.
PROVINCE_LINK = re.compile(r'"(/subeler/([a-z0-9-]+))"')
DISTRICT_LINK = re.compile(r'"(/subeler/[a-z0-9-]+/([a-z0-9-]+))"')
#: The district page's own state blob, which is the branch list it renders from.
STATE = re.compile(
    r'<script id="__districtStores_INITIAL_STATE__" type="application/json">(.*?)</script>',
    re.DOTALL,
)

#: The site rate-limits: a 0,3 second gap ran into HTTP 429 after 26 provinces, and the
#: retry then hit it four times in a row and gave up. Slower, with a longer climb.
DELAY = 0.8

#: Province names come back in the chain's spelling ("Bolu"), the crawl uses its slugs
#: ("bolu"); `--devam` compares the two, so it folds the Turkish letters the same way.
SLUG = str.maketrans("çğıöşüâî", "cgiosuai")


def slug(name: str) -> str:
    return name.lower().replace("i̇", "i").translate(SLUG).replace(" ", "-")



def get(url: str, tries: int = 6) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": BROWSER})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            if error.code == 404:  # a slug the index lists but the site no longer serves
                return ""
            if attempt == tries - 1:
                raise
            time.sleep(5 * 2**attempt)
        except (urllib.error.URLError, http.client.HTTPException, OSError):
            if attempt == tries - 1:
                raise
            time.sleep(5 * 2**attempt)
    raise AssertionError("unreachable")


def provinces() -> list[str]:
    page = get(f"{BASE}/subeler")
    return sorted({slug for _, slug in PROVINCE_LINK.findall(page)})


def districts(province: str) -> list[str]:
    page = get(f"{BASE}/subeler/{province}")
    return sorted({slug for _, slug in DISTRICT_LINK.findall(page)})


def branches(province: str, district: str) -> list[dict]:
    page = get(f"{BASE}/subeler/{province}/{district}")
    found = STATE.search(page)
    if not found:
        return []
    state = json.loads(found.group(1))
    return [
        {
            "name": store["storeName"],
            # The state's own `city` and `district` are objects, not strings — their
            # `name` is the chain's spelling, the slug is ours.
            "province": (state.get("city") or {}).get("name") or province,
            "district": (state.get("district") or {}).get("name") or district,
            "address": store.get("storeAddress", ""),
            "lat": store["latitude"],
            "lng": store["longitude"],
        }
        for store in state.get("result") or []
    ]


def done(target: Path) -> set[str]:
    """Province names already written, so `--devam` can pick up after a 429."""
    if not target.exists():
        return set()
    with target.open(encoding="utf-8", newline="") as handle:
        return {row["province"] for row in csv.DictReader(handle)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"subeler_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    resuming = "--devam" in sys.argv
    # The file stores the chain's own province spelling, the crawl walks slugs, so the
    # comparison folds both to a slug rather than trusting the two to look alike.
    have = {slug(name) for name in done(target)} if resuming else set()
    found = [p for p in provinces() if p not in have]
    print(f"{len(found)} il", flush=True)
    total = 0
    # The header goes on an empty file, not on a run without `--devam`. Those are not the
    # same thing: a resumed run whose previous attempt died on a different day writes a
    # *new* dated file, and the old rule left that file headerless — which the chain
    # adapter reads as a first row of data with the column names missing.
    started_empty = not target.exists() or target.stat().st_size == 0
    with target.open("a" if resuming else "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["name", "province", "district", "address", "lat", "lng"]
        )
        if started_empty or not resuming:
            writer.writeheader()
        for province in found:
            towns = districts(province)
            time.sleep(DELAY)
            for district in towns:
                rows = branches(province, district)
                writer.writerows(rows)
                total += len(rows)
                time.sleep(DELAY)
            print(f"  {province}: {len(towns)} ilçe, toplam {total}", flush=True)
    print(f"\n{total:,} şube -> {target}")


if __name__ == "__main__":
    main()
