r"""Mopaş's branches, from the Google My Maps its own site embeds.

Mopaş publishes no store list. `mopas.com.tr/magazalarimiz` is a 404 and the corporate
page names only the head office. What it does have is an embedded Google My Maps, and a
My Maps is a KML document behind a viewer: `maps/d/kml?mid=<id>&forcekml=1` hands back
every placemark with its coordinate, which is why this is a one-request fetch of 137
branches rather than a scrape of a map widget. Ziyafet's dealer list reaches the project
the same way.

Each placemark carries the branch name and a description holding the address and phone,
`<br>`-separated. The coordinate is the point itself — so the district is decided by the
boundary it falls in, like every other coordinate-bearing chain, and the `Kadıköy /
İstanbul` written in the address is never used for that.

**mopas.com.tr is not fetched here, on purpose.** Its `robots.txt` sets
`Visit-time: 0400-0845` UTC and `Crawl-delay: 10`, and this runs at whatever hour the
operator runs it. The map lives on Google's servers, is what the site itself embeds for
the public, and needs one request; nothing about the branch list requires touching the
chain's own host.

A third-party directory (`gidasanayim.com`) lists Mopaş too, with 108 branches and no
coordinates. It is not used: it is 29 branches short, the shortfall is invisible from
inside the file, and its districts are its own reading of the address rather than
Mopaş's.

Run:  uv run python scripts/fetch_mopas.py
Out:  C:\veri-ham\mopas\magazalar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import re
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/mopas")

#: The map Mopaş embeds. A My Maps id is stable; if the chain publishes a new map this
#: fetcher fetches the old one, which is why the count check below is not optional.
MAP_ID = "1Cyb34TpeBAotgXkJBnvwO1jmac1nA8zG"
KML = f"https://www.google.com/maps/d/kml?mid={MAP_ID}&forcekml=1"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = ["name", "address", "phone", "lat", "lng"]

PLACEMARK = re.compile(r"<Placemark>(.*?)</Placemark>", re.DOTALL)
NAME = re.compile(r"<name>(.*?)</name>", re.DOTALL)
DESCRIPTION = re.compile(
    r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", re.DOTALL
)
COORDINATES = re.compile(r"<coordinates>\s*([-\d.]+),([-\d.]+)", re.DOTALL)
PHONE = re.compile(r"Tel:\s*(.+)$", re.IGNORECASE)

#: 137 branches on 2026-09-20. A map that answers with a handful of placemarks has been
#: replaced or emptied, and a short list is the failure that does not look like one.
MINIMUM = 100


def clean(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def branches() -> list[dict[str, str]]:
    request = urllib.request.Request(KML, headers={"User-Agent": BROWSER})
    with urllib.request.urlopen(request, timeout=60) as response:
        document = response.read().decode("utf-8", "replace")

    rows = []
    for placemark in PLACEMARK.findall(document):
        point = COORDINATES.search(placemark)
        if point is None:
            continue
        name = NAME.search(placemark)
        described = DESCRIPTION.search(placemark)
        # The description is one CDATA block: address, `<br>`, phone.
        parts = re.split(r"<br\s*/?>", described.group(1)) if described else []
        phone = next((PHONE.search(clean(p)) for p in parts if "Tel" in p), None)
        rows.append(
            {
                "name": clean(name.group(1)) if name else "",
                "address": clean(parts[0]) if parts else "",
                "phone": phone.group(1).strip() if phone else "",
                "lat": point.group(2),
                "lng": point.group(1),
            }
        )
    if len(rows) < MINIMUM:
        raise ValueError(f"yalnız {len(rows)} şube okundu, en az {MINIMUM} bekleniyor")
    return rows


def main() -> None:
    rows = branches()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"magazalar_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} şube  -> {path}")


if __name__ == "__main__":
    main()
