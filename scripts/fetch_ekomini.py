r"""Ekomini's stores, read off the map its own page draws.

`/magazalar` renders no store list — it renders a Google Map and then writes one
`map.addMarker({...})` call per store straight into the page's script. There are 2.177 of
them and 2.176 are stores; the odd one out is the visitor's own position, a marker the
page adds from the browser's geolocation with `lat: position.coords.latitude` and the
title `Sizin Konumunuz`. It is dropped by requiring a numeric coordinate, which the
placeholder does not have.

Each marker carries an `infoWindow` whose content is a small HTML block: store name,
`İLÇE/İL`, phone, and a link to the store's own page. The district label is saved, but as
`source_district` — the coordinate is what places the store, like every other chain with
a point.

Ekomini is a franchise network and its store names show it (`CADDE BÜFE 3`,
`EKOMİNİ HASAN DİNDAR`): the sign over the door is often the operator's. That matters
for reading the count, not for collecting it — these are Ekomini-supplied stores whether
or not they carry the brand in their name.

Run:  uv run python scripts/fetch_ekomini.py
Out:  C:\veri-ham\ekomini\magazalar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import re
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/ekomini")
PAGE = "https://ekomini.com.tr/magazalar"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = ["name", "province", "source_district", "phone", "lat", "lng"]

MARKER = re.compile(r"addMarker\(\s*\{(.*?)\}\s*\)\s*;", re.DOTALL)
LAT = re.compile(r"lat:\s*([-\d.]+)\s*,")
LNG = re.compile(r"lng:\s*([-\d.]+)\s*,")
TITLE = re.compile(r"title:\s*'([^']*)'")
CONTENT = re.compile(r"content:\s*'(.*?)'\s*\n", re.DOTALL)

#: 2.176 stores on 2026-09-20. A page that draws a handful of markers has stopped
#: writing them, which looks exactly like a small chain from the outside.
MINIMUM = 1000


def clean(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "|", text)).split())


def stores() -> list[dict[str, str]]:
    request = urllib.request.Request(
        PAGE, headers={"User-Agent": BROWSER, "Accept-Language": "tr"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        page = response.read().decode("utf-8", "replace")

    rows = []
    for marker in MARKER.findall(page):
        lat, lng = LAT.search(marker), LNG.search(marker)
        title = TITLE.search(marker)
        # The visitor's own marker has `position.coords.latitude` where a number
        # belongs, so it fails here and never reaches the file.
        if not (lat and lng and title):
            continue
        content = CONTENT.search(marker)
        parts = clean(content.group(1)).split("|") if content else []
        # name | İLÇE/İL | phone | link text
        place = next((p for p in parts if "/" in p and "http" not in p), "")
        district, _, province = place.partition("/")
        phone = next(
            (p for p in parts if re.fullmatch(r"[\d()\s-]{7,}", p.strip())), ""
        )
        rows.append(
            {
                "name": title.group(1).strip(),
                "province": province.strip(),
                "source_district": district.strip(),
                "phone": phone.strip(),
                "lat": lat.group(1),
                "lng": lng.group(1),
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
    provinces = {row["province"] for row in rows if row["province"]}
    print(f"{len(rows)} mağaza  {len(provinces)} il  -> {path}")


if __name__ == "__main__":
    main()
