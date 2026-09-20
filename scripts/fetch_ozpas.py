r"""Özpaş's stores, one page each.

`/magazalarimiz` lists a card per store and links each to its own page (`/ozpas-
supermarket-carsi`), where the address sits with the phone. The index itself carries
only the head office address, so the store pages are what has to be read.

**The index is paginated and shows six cards at a time.** `?page=N` walks it; `?sayfa=N`
and `?p=N` are accepted by the server and silently return page one, which is the trap —
a fetcher that used either would report six stores and look like it had worked. The
first run of this script did exactly that, and the chain is four times larger.

Paging stops when a page introduces no store the previous pages did not have, so a
server that keeps answering with the last page cannot spin the loop forever.

Run:  uv run python scripts/fetch_ozpas.py
Out:  C:\veri-ham\ozpas\magazalar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import re
import time
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/ozpas")
ROOT = "https://www.ozpasmarket.com"
INDEX = f"{ROOT}/magazalarimiz"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = ["name", "kind", "slug", "address"]

#: The index lists the head office among the shops (`Özpaş Genel Merkez`).
#: It is written out with its own kind rather than dropped, so a reader can
#: see what was excluded from a store count and why.
NOT_A_SHOP = re.compile(r"Genel\s*Merkez|Depo", re.IGNORECASE)
PAUSE = 0.7

CARD = re.compile(
    r'<h4 class="blog-title">\s*<a href="(/[a-z0-9\-]+)"[^>]*>(.*?)</a>', re.DOTALL
)

#: The store's own address sits in the contact row, `iletisim-satir-bilgi`. The page
#: also prints the company's head office in its footer under an `<h6>Adres</h6>`, and a
#: reader that searches the whole page for something address-shaped picks that up for
#: every store — six identical rows pointing at the Arifiye head office.
ADDRESS = re.compile(r'class="iletisim-satir-bilgi">(.*?)</div>', re.DOTALL)

#: Inline `<style>` and `<script>` are dropped before the tags are: a page's CSS is full
#: of `font-family: "Segoe UI", Roboto, …`, which survives tag-stripping and matches an
#: address pattern well enough to end up in the file — it did, in all six rows.
NOISE = re.compile(r"<(script|style)[^>]*>.*?</>", re.DOTALL | re.IGNORECASE)

#: 25 stores on 2026-09-20, six to a page. Below this the index has stopped paging.
MINIMUM = 12

#: A ceiling on the walk, so a server that answers every page with the same content
#: cannot keep it going. Five pages were enough on 2026-09-20.
MAX_PAGES = 30


def get(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": BROWSER, "Accept-Language": "tr"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", "replace")


def clean(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def listed() -> list[tuple[str, str]]:
    """Every (slug, name) across the paginated index, in order, without repeats."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for page in range(1, MAX_PAGES + 1):
        url = INDEX if page == 1 else f"{INDEX}?page={page}"
        fresh = 0
        for slug, name in CARD.findall(get(url)):
            if slug not in seen:
                seen.add(slug)
                found.append((slug, clean(name)))
                fresh += 1
        if not fresh:
            break
        time.sleep(PAUSE)
    return found


def stores() -> list[dict[str, str]]:
    found = listed()
    if len(found) < MINIMUM:
        raise ValueError(
            f"{len(found)} mağaza bağlantısı bulundu, en az {MINIMUM} bekleniyor"
        )

    rows = []
    for slug, name in found:
        page = NOISE.sub(" ", get(f"{ROOT}{slug}"))
        address = ADDRESS.search(page)
        rows.append(
            {
                "name": name,
                "kind": "merkez" if NOT_A_SHOP.search(name) else "magaza",
                "slug": slug.strip("/"),
                "address": clean(address.group(1)) if address else "",
            }
        )
        time.sleep(PAUSE)
    return rows


def main() -> None:
    rows = stores()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"magazalar_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    shops = sum(1 for row in rows if row["kind"] == "magaza")
    empty = sum(1 for row in rows if not row["address"])
    print(f"{shops} mağaza + {len(rows) - shops} merkez  adressiz {empty}  -> {path}")


if __name__ == "__main__":
    main()
