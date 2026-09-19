r"""Four chains that publish their whole store list on one page.

Bizim Toptan, Vatan Bilgisayar, Happy Center and Onur Market each render every store into
a single page, so each is one request. None of them offers JSON; the fields are in the
markup, and each brand hides them somewhere else, which is why there is a parser per brand
rather than one clever regex:

* **Bizim Toptan** — `<li data-city="34" data-county="1447" data-name="…">`. The city is a
  plate number and the county a numeric id, both the source's own; the address is in a
  sibling `<p>`. No coordinate.
* **Vatan Bilgisayar** — `data-city`, `data-area` (the district), `data-x`, `data-y`. The
  coordinates use a **comma** as the decimal separator (`36,993773`), so they are read as
  Turkish-formatted text, not floats.
* **Happy Center** — a card per store whose title is `İlçe / Mağaza adı`; the district is
  the part before the slash and there is no separate field for it.
* **Onur Market** — the address block ends with `İlçe / İl` on its own line.

Only Vatan and Onur carry coordinates. For the other two the district comes from the
source's own label, which the adapter has to match against the registry — that is the
trade-off of a one-request source and it is recorded here rather than papered over.

Run:  uv run python scripts/fetch_marketler.py
Out:  C:\veri-ham\marketler\<marka>_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import json
import re
import time
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/marketler")
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

URLS = {
    "bizim_toptan": "https://www.bizimtoptan.com.tr/magazalar",
    "vatan": "https://www.vatanbilgisayar.com/magazalar",
    "happy_center": "https://www.happycenter.com.tr/kurumsal/magazalarimiz",
    "onur_market": "https://www.onurmarket.com/tr/magazalar",
    "gratis": "https://www.gratis.com/magazalarimiz",
    "madame_coco": "https://www.madamecoco.com/magazalar",
    "rossmann": "https://www.rossmann.com.tr/magazalar",
    "karaca": "https://www.karaca.com/magazalarimiz",
}

COLUMNS = ["name", "province", "district", "address", "lat", "lng"]


def get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": BROWSER})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", "replace")


def clean(text: str) -> str:
    return " ".join(html.unescape(text).split())


def bizim_toptan(page: str) -> list[dict]:
    rows = []
    for block in re.findall(r"<li\s+data-id=\"store[^>]*>", page):
        name = re.search(r'data-name="([^"]*)"', block)
        city = re.search(r'data-city="([^"]*)"', block)
        search = re.search(r'data-search="([^"]*)"', block)
        if not name:
            continue
        # `data-search` repeats "il, ilçe, …" in lower case; the district is its second
        # field and the only place the store's district is written out.
        parts = [p.strip() for p in clean(search.group(1)).split(",")] if search else []
        rows.append(
            {
                "name": clean(name.group(1)),
                "province": parts[0] if parts else (city.group(1) if city else ""),
                "district": parts[1] if len(parts) > 1 else "",
                "address": "",
                "lat": "",
                "lng": "",
            }
        )
    addresses = [
        clean(a) for a in re.findall(r'store-locator-item-address[^>]*>([^<]*)<', page)
    ]
    for row, address in zip(rows, addresses, strict=False):
        row["address"] = address
    return rows


def vatan(page: str) -> list[dict]:
    rows = []
    for block in re.findall(r"<a[^>]*class=\"store store-card-title[^>]*>", page):
        field = dict(re.findall(r'data-([a-zA-Z]+)="([^"]*)"', block))
        if "title" not in field:
            continue
        rows.append(
            {
                "name": clean(field.get("title", "")),
                "province": clean(field.get("city", "")),
                "district": clean(field.get("area", "")),
                "address": clean(field.get("address", "")),
                # Turkish decimal comma, straight from the attribute.
                "lat": field.get("x", "").replace(",", "."),
                "lng": field.get("y", "").replace(",", "."),
            }
        )
    return rows


def happy_center(page: str) -> list[dict]:
    titles = re.findall(r'cms-store-card-title">([^<]*)<', page)
    texts = re.findall(r'cms-content-card-text">([^<]*)<', page)
    rows = []
    for title, text in zip(titles, texts, strict=False):
        label = clean(title)
        district, _, name = label.partition("/")
        address = clean(text)
        address = address.split("Adres:", 1)[-1] if "Adres:" in address else address
        rows.append(
            {
                "name": clean(name) or label,
                "province": "",  # the card names no province; the address carries it
                "district": clean(district),
                "address": clean(address),
                "lat": "",
                "lng": "",
            }
        )
    return rows


def onur_market(page: str) -> list[dict]:
    rows = []
    for block in re.split(r'<div class="box c">', page)[1:]:
        text = clean(re.sub(r"<[^>]+>", " ", block.split("</div>")[0]))
        # "… No: 29/4 16180 Emek Osmangazi / Bursa" — the tail is district / province.
        tail = re.search(r"([A-Za-zÇĞİÖŞÜçğıöşü.\s]+)/\s*([A-Za-zÇĞİÖŞÜçğıöşü\s]+)$", text)
        rows.append(
            {
                "name": "",
                "province": clean(tail.group(2)) if tail else "",
                "district": clean(tail.group(1).split()[-1]) if tail else "",
                "address": text,
                "lat": "",
                "lng": "",
            }
        )
    names = [clean(n) for n in re.findall(r"<span>([^<]{3,60})</span>", page)]
    for row, name in zip(rows, names, strict=False):
        row["name"] = name
    return rows


def _balanced(page: str, start: int, open_char: str = "[") -> str:
    r"""The JSON array or object beginning at `start`, matched by depth.

    A regex cannot end one of these: every store carries nested objects (working hours,
    a country inside a city), so `\[.*?\]` stops at the first inner bracket.
    """
    close = "]" if open_char == "[" else "}"
    depth = 0
    for index in range(start, len(page)):
        if page[index] == open_char:
            depth += 1
        elif page[index] == close:
            depth -= 1
            if depth == 0:
                return page[start : index + 1]
    raise ValueError("kapanmayan JSON")


def madame_coco(page: str) -> list[dict]:
    start = page.index('{"count":', 0)
    data = json.loads(_balanced(page, start, "{"))
    rows = []
    for store in data["results"]:
        township = store.get("township") or {}
        city = township.get("city") or {}
        rows.append(
            {
                "name": store["name"],
                "province": city.get("name", ""),
                "district": township.get("name", ""),
                "address": store.get("address", ""),
                "lat": store.get("latitude", ""),
                "lng": store.get("longitude", ""),
            }
        )
    return rows


def gratis(page: str) -> list[dict]:
    r"""Gratis ships its stores inside a Next.js payload, escaped twice.

    The page prints `\"storeId\":\"1001\"` — the array is a string inside a script that
    pushes it, so every quote is backslashed. That is why an earlier search for
    `"latitude"` found nothing although 2.430 addresses were sitting in the body.

    The escaped text is read field by field rather than unescaped and parsed as JSON: the
    payload also carries React markers (`$`, `$L11`) that are not valid JSON, so decoding
    the whole thing fails on a store that is perfectly readable.
    """
    records = re.split(r'\\"storeId\\"', page)[1:]
    if not records:
        raise ValueError("Gratis: storeId bulunamadı — sayfa değişmiş olabilir")

    def field(text: str, name: str) -> str:
        found = re.search(r'\\"' + name + r'\\":\\"([^\\]*)\\"', text)
        return clean(found.group(1)) if found else ""

    rows = []
    for record in records:
        head = record[:1500]
        rows.append(
            {
                "name": field(head, "name"),
                "province": field(head, "city"),
                "district": field(head, "district"),
                "address": field(head, "street"),
                "lat": field(head, "lat"),
                "lng": field(head, "long"),
            }
        )
    return rows


def rossmann(page: str) -> list[dict]:
    start = page.index("[", page.index("var locations"))
    rows = []
    for store in json.loads(_balanced(page, start)):
        rows.append(
            {
                "name": store.get("store_name", ""),
                "province": store.get("city", ""),
                # The source spells it `distinct`; it means district.
                "district": store.get("distinct", ""),
                "address": store.get("address", ""),
                "lat": store.get("latitude", ""),
                "lng": store.get("longitude", ""),
            }
        )
    return rows


def karaca(page: str) -> list[dict]:
    """Karaca prints one store's JSON per card — but the JSON is not valid.

    Its `mail` field holds an anchor tag whose own quotes are left unescaped
    (`"mail":"<a href="/cdn-cgi/...">"`), so `json.loads` stops mid-record. The fields we
    need sit before it and are plain, so each is read with its own pattern instead of
    repairing a document the source itself broke.
    """
    rows = []
    for block in re.findall(r'class="store-find-change-map\d+">\{(.*?)\}</div>', page, re.DOTALL):
        text = html.unescape(block)

        def field(name: str, source: str = text) -> str:
            found = re.search(r'"' + name + r'":"?([^",]*)"?', source)
            return clean(found.group(1)) if found else ""

        rows.append(
            {
                "name": field("name"),
                "province": field("city"),
                # `state` is the district here, not a province-level field.
                "district": field("state"),
                "address": field("address"),
                "lat": field("lat"),
                "lng": field("lng"),
            }
        )
    return rows


PARSERS = {
    "bizim_toptan": bizim_toptan,
    "vatan": vatan,
    "happy_center": happy_center,
    "onur_market": onur_market,
    "gratis": gratis,
    "madame_coco": madame_coco,
    "rossmann": rossmann,
    "karaca": karaca,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.now(tz=dt.UTC).date()
    for brand, url in URLS.items():
        rows = PARSERS[brand](get(url))
        target = OUT / f"{brand}_{today:%Y-%m-%d}.csv"
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        placed = sum(1 for r in rows if r["district"])
        print(
            f"{brand:<14}{len(rows):>5} mağaza, {placed} ilçeli -> {target.name}",
            flush=True,
        )
        time.sleep(1)


if __name__ == "__main__":
    main()
