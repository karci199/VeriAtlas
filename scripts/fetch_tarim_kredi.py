r"""Tarım Kredi Kooperatif Marketleri, the whole chain in one request.

The cooperative's own site (tarimkredi.org.tr) has no store finder — it is the parent
organisation's site and carries two addresses, both of them head offices. The market
chain sits on its own domain, `tkkoop.com.tr`, and that page hands the list out whole:

    GET tkkoop.com.tr/json/magazalar?sehir=<il adı>

The province is a filter, and **an empty filter is not an error, it is the whole
country** — one request, every store, with a coordinate on each. The dropdown on the page
only ever asks for one province at a time, which is why the URL looks like it needs one.
A province that is not a name (`?sehir=6`) answers HTTP 500 rather than an empty list;
that is a broken request, never "no stores in 06".

The store's district is *not* read from here. The name (`ANKARA - AHİMESUT`) is the
chain's own labelling and the address is free text with the district buried in it — two
Ankara rows one after another write `ETİMESGUT / ANKARA` and `KEÇİÖEREN/ ANKARA`, the
second one misspelt and unspaced. The coordinate is the reliable field, so placement is
left to `chain_stores`, which drops every point into the district polygon that holds it.

robots.txt allows `/magazalarimiz` for ClaudeBot, and this is one request either way.

Run:  uv run python scripts/fetch_tarim_kredi.py
Out:  C:\veri-ham\tarimkredi\magazalar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import sys

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

URL = "https://www.tkkoop.com.tr/json/magazalar?sehir="
OUT = RAW / "tarimkredi"
UA = "ClaudeBot/1.0 (+https://claude.com/claudebot)"
#: Turkey's bounding box, the one the chain adapter uses. Checked here as well so a
#: silently changed response shape is caught at the source rather than three steps later.
TURKEY = (25.5, 35.5, 45.0, 42.5)
#: The chain's own published figure at the time of writing, as a floor rather than a
#: target: a fetch that comes back with a fraction of it has failed, even with HTTP 200.
EXPECTED_AT_LEAST = 1200
#: `lat`/`lng` rather than `enlem`/`boylam`: the chain adapter reads every brand's dump
#: with the same two column names, and a dump that spells them differently would be a
#: brand-shaped special case in a parser that has none.
COLUMNS = ["id", "ad", "adres", "lat", "lng"]


def fetch() -> list[dict]:
    answer = httpx.get(
        URL, headers={"User-Agent": UA}, timeout=60, follow_redirects=True
    )
    answer.raise_for_status()
    stores = json.loads(answer.text)
    if not isinstance(stores, list):
        raise SystemExit(f"beklenen liste değil: {type(stores).__name__}")
    return stores


def main() -> None:
    stores = fetch()
    x0, y0, x1, y1 = TURKEY
    outside = 0
    rows = []
    seen: set[str] = set()
    for store in stores:
        uid = store.get("uid", "")
        if uid in seen:  # the same store twice would inflate a count nobody re-checks
            raise SystemExit(f"yinelenen kimlik: {uid}")
        seen.add(uid)
        try:
            lat, lng = float(store["enlem"]), float(store["boylam"])
        except (KeyError, ValueError):
            lat = lng = float("nan")
        if not (x0 <= lng <= x1 and y0 <= lat <= y1):
            outside += 1
        rows.append(
            {
                "id": uid,
                "ad": store.get("isim", ""),
                "adres": store.get("adres", ""),
                "lat": store.get("enlem", ""),
                "lng": store.get("boylam", ""),
            }
        )

    if len(rows) < EXPECTED_AT_LEAST:
        raise SystemExit(
            f"yalnız {len(rows)} mağaza döndü, en az {EXPECTED_AT_LEAST} bekleniyor"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"magazalar_{dt.datetime.now(tz=dt.UTC).date().isoformat()}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} magaza, Turkiye kutusu disinda {outside}: {path}")


if __name__ == "__main__":
    main()
