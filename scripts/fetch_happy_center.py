r"""Happy Center's stores, one page each.

The store index (`/kurumsal/kategori/magazalar/`) lists a card per store and links each
to its own page. The map on that index carries only three coordinates — it is a teaser,
not the dataset — so the stores are read from their own pages instead, where the address
sits in a `Adres :` line ending `İlçe/İl`.

There is no coordinate anywhere, so the district has to come from the address, which
`veriatlas.addresses` resolves against PTT's neighbourhood table. That is why this
fetcher saves the address whole and does not try to split it: the resolver improves, and
a dump frozen against today's parse would not benefit.

An earlier fetcher read this chain off the index cards alone
(`scripts/fetch_marketler.py`) and produced 194 rows whose district field held things
like `Kartal Gümüşpınar` and whose province was empty — a card title is not an address.
Those rows never reached the warehouse; this replaces them.

Run:  uv run python scripts/fetch_happy_center.py
Out:  C:\veri-ham\happy_center\magazalar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/happy_center")
ROOT = "https://www.happycenter.com.tr"
INDEX = f"{ROOT}/kurumsal/kategori/magazalar/"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = ["name", "slug", "address"]

#: Courtesy gap between store pages.
PAUSE = 0.7

SLUG = re.compile(r"/kurumsal/magazalar/([a-z0-9\-]+)")
TITLE = re.compile(r"<title>(.*?)</title>", re.DOTALL | re.IGNORECASE)

#: The address line, however the page spaces it: `Adres&nbsp; :&nbsp; …`.
ADDRESS = re.compile(r"Adres\s*:\s*(.+)", re.IGNORECASE)

#: What the page prints straight after the address, with no punctuation between. The
#: address has to be cut at the first of these: the store page runs
#: `… Çekmeköy/İstanbul Şube Tipi: Süpermarket Hafta içi: 09:00-21:00 …` on one line,
#: and cutting at the first `/` instead took opening hours as the place name for 45 of
#: the 80 stores — a failure that reads as "address not found" rather than as a bad cut.
STOPS = re.compile(
    r"\s*(?:Şube\s*Tipi|Mağaza\s*Bilgileri|Hafta\s*içi|Telefon|Tel\s*:|Açılış|Cumartesi|Pazar\s*:)",
    re.IGNORECASE,
)

#: 82 stores on 2026-09-20. An index that lists a handful has stopped rendering.
MINIMUM = 40


def get(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": BROWSER, "Accept-Language": "tr"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", "replace")


def clean(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def slugs() -> list[str]:
    found = sorted(set(SLUG.findall(get(INDEX))))
    if len(found) < MINIMUM:
        raise ValueError(
            f"{len(found)} mağaza bağlantısı bulundu, en az {MINIMUM} bekleniyor"
        )
    return found


def store(slug: str) -> dict[str, str] | None:
    page = get(f"{ROOT}/kurumsal/magazalar/{slug}")
    text = clean(page)
    address = ADDRESS.search(text)
    if address is None:
        return None
    # The address line runs on into whatever the page prints next, so it is cut at the
    # first label that follows rather than at a character count.
    written = STOPS.split(address.group(1))[0].strip()
    title = TITLE.search(page)
    return {
        "name": clean(title.group(1)).split("|")[0].strip() if title else slug,
        "slug": slug,
        "address": written[:200],
    }


def main() -> None:
    rows = []
    missing = []
    names = slugs()
    for index, slug in enumerate(names, 1):
        try:
            found = store(slug)
        except urllib.error.HTTPError as error:
            raise SystemExit(f"{slug}: HTTP {error.code}") from error
        if found is None:
            missing.append(slug)
        else:
            rows.append(found)
        if index % 20 == 0:
            print(f"[{index}/{len(names)}]", flush=True)
        time.sleep(PAUSE)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"magazalar_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} mağaza  adressiz {len(missing)}  -> {path}")
    if missing:
        print("adres satırı olmayanlar: " + ", ".join(missing))


if __name__ == "__main__":
    main()
