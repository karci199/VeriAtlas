r"""Vodafone's dealer network, one request per province.

`/bayi` lists a page per province (`/bayi/adana`, `/bayi/agri`, ...) and each of those
renders **every** dealer in that province server-side — no paging, no JSON endpoint, no
location permission. The province slugs are read off `/bayi` rather than generated from
our own province names, because they are the site's own spelling and it folds Turkish
letters its own way (`afyonkarahisar`, `agri`, `k-maras`).

Each dealer is one `<div class="... js-store" data-lat data-long ...>`, and everything
needed is in that element or the block it opens:

* `data-lat` / `data-long` — a real coordinate per dealer, so the district comes from the
  boundary the point falls in and never from a label;
* the `<h2 class="d-name">` — the dealer's registered company name, not a branch number;
* the location image's `alt` — `İlçe/İl`, which is the source's own district label and is
  kept as `source_district` for checking the coordinate against, never as the answer;
* `<div class="d-address">` — the street address;
* the `tel:` link — the dealer's phone.

The page also prints its own count ("Adana'da 193 adet"), which is what the parser
verifies each province against: a page that renders half its dealers still looks like a
valid page, and only the printed count catches that.

`robots.txt` names ClaudeBot explicitly and answers `Allow: /`, disallowing only the
number-porting flow; `/bayi/*` is not restricted (checked 2026-09-20).

Run:  uv run python scripts/fetch_vodafone.py
Out:  C:\veri-ham\vodafone\bayiler_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/vodafone")
ROOT = "https://www.vodafone.com.tr"
INDEX = f"{ROOT}/bayi"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = [
    "name",
    "province",
    "district",
    "source_district",
    "address",
    "phone",
    "lat",
    "lng",
]

#: Courtesy gap between province pages.
PAUSE = 1.0

#: Türkiye has 81 provinces and the index lists one page each. Fewer means the index
#: stopped rendering part of itself, which must fail rather than produce a short list.
PROVINCES = 81

#: The page is split on the dealer divs rather than matched with a lookahead: the last
#: dealer on a page is followed by whatever the footer happens to be that week, and a
#: lookahead anchored on that silently drops it — 192 of Adana's 193 on the first run.
SPLIT = re.compile(r'(?=<div class="[^"]*js-store")')
STORE = re.compile(
    r'<div class="[^"]*js-store"[^>]*data-lat="([^"]*)"[^>]*data-long="([^"]*)"'
)


def coordinate(lat: str, lng: str) -> tuple[str, str]:
    """The pair as written, or a blank pair when the source did not write numbers.

    One Gaziantep dealer carries `data-lat="37.0780278,37" data-long="4286978"`: a
    comma-decimal longitude that broke across the two attributes at the source. The
    halves read back into 37,0780278 / 37,4286978 by eye, and that is exactly why they
    are not — a fetcher that repairs what it guesses the source meant will repair a
    genuinely wrong coordinate the same way, with nobody seeing it. The dealer stays so
    the page's own count still matches; the coordinate is left empty and the adapter
    drops the row as unplaced, where it is counted out loud.
    """
    try:
        float(lat), float(lng)
    except ValueError:
        return "", ""
    return lat, lng


NAME = re.compile(r'<h2 class="d-name">\s*(.*?)\s*</h2>', re.DOTALL)
PLACE = re.compile(r'<img[^>]*class="mr-2"[^>]*alt="([^"]*?/[^"]*?)"', re.DOTALL)
ADDRESS = re.compile(r'<div class="d-address[^"]*">.*?<span>(.*?)</span>', re.DOTALL)
PHONE = re.compile(r'href="tel:(\d+)"')
COUNT = re.compile(r'id="js-selected-store-count"[^>]*>\s*([\d.]+)\s*<')
SLUG = re.compile(r'href="/bayi/([a-z0-9\-]+)"')


def get(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": BROWSER, "Accept-Language": "tr"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", "replace")


def clean(text: str) -> str:
    """Markup out, entities decoded, runs of whitespace folded to one space."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text))).strip()


#: `/bayi/engelsiz-magazalar` sits among the province links but is a filter across all of
#: them, not a province. Following it would count every accessible dealer a second time.
NOT_A_PROVINCE = {"engelsiz-magazalar"}


def slugs() -> list[str]:
    """The province page slugs, in the index's own spelling."""
    found = sorted(set(SLUG.findall(get(INDEX))) - NOT_A_PROVINCE)
    if len(found) != PROVINCES:
        raise ValueError(f"{len(found)} il sayfası bulundu, {PROVINCES} bekleniyor")
    return found


def dealers(slug: str) -> list[dict[str, str]]:
    page = get(f"{INDEX}/{slug}")
    rows = []
    for block in SPLIT.split(page):
        head = STORE.match(block)
        if head is None:
            continue
        lat, lng = coordinate(head.group(1), head.group(2))
        name = NAME.search(block)
        place = PLACE.search(block)
        address = ADDRESS.search(block)
        phone = PHONE.search(block)
        district, _, province = (place.group(1) if place else "").partition("/")
        rows.append(
            {
                "name": clean(name.group(1)) if name else "",
                "province": clean(province),
                # Left empty on purpose: the district is the adapter's job, decided by
                # the coordinate. What the page says is kept beside it, not in it.
                "district": "",
                "source_district": clean(district),
                "address": clean(address.group(1)) if address else "",
                "phone": phone.group(1) if phone else "",
                "lat": lat,
                "lng": lng,
            }
        )
    stated = COUNT.search(page)
    if stated:
        expected = int(stated.group(1).replace(".", ""))
        if len(rows) != expected:
            raise ValueError(f"{slug}: sayfa {expected} bayi diyor, {len(rows)} okundu")
    elif not rows:
        raise ValueError(f"{slug}: ne bayi ne sayı bulundu; sayfa değişmiş olabilir")
    return rows


def main() -> None:
    rows: list[dict[str, str]] = []
    names = slugs()
    for index, slug in enumerate(names, 1):
        try:
            found = dealers(slug)
        except urllib.error.HTTPError as error:
            raise SystemExit(f"{slug}: HTTP {error.code}") from error
        rows.extend(found)
        print(f"[{index:2}/{len(names)}] {slug:20} {len(found):4} bayi", flush=True)
        time.sleep(PAUSE)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"bayiler_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} bayi  {len({r['province'] for r in rows})} il  -> {path}")


if __name__ == "__main__":
    sys.exit(main())
