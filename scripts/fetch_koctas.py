r"""Koçtaş stores, province by province, off the store finder's own form target.

The finder page is a shell, but the form on it is a plain GET and says where it points:

    <form id="koctasStoreFinderForm" action="/store-finder/findPOSByCity" method="get">

    GET koctas.com.tr/store-finder/findPOSByCity?addressCity=<plaka>

The parameter name is `addressCity`, not `city` — `?city=06` answers **HTTP 400**, which
is a rejected request and not an empty province. The answer is JSON (an SAP Commerce
`pointOfServices` payload) with `geoPoint.latitude` / `.longitude` on every store.

There is no all-provinces call, so the sweep is 81 requests. A province with no Koçtaş is
an ordinary empty list and is counted as such — the chain has around 60 stores, so most
provinces genuinely have none, and that is the answer to the question rather than a gap.

**Two fields here look informative and are not.**

`storeContent` says `"Mağazamız geçici olarak kapalıdır."` on 58 of the 134 stores —
including Ankara Eryaman, Ankamall and Panora, which are the chain's flagships. Every one
of those records also says `storeOpenStatus: OPEN`. The sentence is boilerplate sitting in
a content field, not a closure flag; reading it as one would have marked 43% of the chain
closed. `storeOpenStatus` is what gets written out.

`address.addressTown` is the source's own district and it is **wrong often enough to be
useless**: Ankamall AVM, which stands in Yenimahalle, is filed under `HAMAMÖZÜ` with the
town code `K0503` — Amasya's plate. Gordion AVM, in Çankaya, is filed under `HAYMANA`. The
field is written to the file as published, but the district downstream comes from the
coordinate, as it does for every other chain.

robots.txt allows it: Koçtaş disallows carts, orders, search and offer endpoints, and
`/store-finder/` is none of them.

Run:  uv run python scripts/fetch_koctas.py
Out:  C:\veri-ham\koctas\magazalar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import sys
import time

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

URL = "https://www.koctas.com.tr/store-finder/findPOSByCity"
OUT = RAW / "koctas"
UA = "ClaudeBot/1.0 (+https://claude.com/claudebot)"
DELAY = 0.4
#: `KOCTAS_STORE` is the big-box store, `KOCTAS_FIX` the small neighbourhood format. Two
#: different things under one sign, so the type travels with the row.
COLUMNS = [
    "id",
    "ad",
    "tur",
    "durum",
    "il",
    "kaynak_ilce",
    "adres",
    "telefon",
    "lat",
    "lng",
]


def stores_in(client: httpx.Client, plate: str) -> list[dict]:
    answer = client.get(URL, params={"addressCity": plate})
    answer.raise_for_status()
    payload = answer.json()
    # The endpoint answers with a bare list. Earlier SAP versions wrap it in an object,
    # and both shapes are accepted rather than one being assumed: a renamed key and an
    # empty province look identical from outside, and only one of them is an answer.
    if isinstance(payload, list):
        return payload
    for key in ("pointOfServices", "stores", "data"):
        if isinstance(payload.get(key), list):
            return payload[key]
    raise SystemExit(f"{plate}: yanıtta mağaza listesi yok ({sorted(payload)[:8]})")


def named(value: object) -> str:
    """`{"code": "06", "name": "ANKARA"}` -> `ANKARA`; anything else -> as published."""
    if isinstance(value, dict):
        return value.get("name") or ""
    return value or ""


def row_of(store: dict) -> dict:
    point = store.get("geoPoint") or {}
    address = store.get("address") or {}
    return {
        "id": store.get("name", ""),
        "ad": store.get("displayName", ""),
        "tur": store.get("storeType", ""),
        "durum": store.get("storeOpenStatus", ""),
        "il": named(address.get("addressCity")),
        "kaynak_ilce": named(address.get("addressTown")),
        "adres": address.get("line1", ""),
        "telefon": address.get("phone", ""),
        "lat": point.get("latitude", ""),
        "lng": point.get("longitude", ""),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    seen: set[str] = set()
    with_stores = 0
    with httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=True) as c:
        for plate in range(1, 82):
            found = stores_in(c, f"{plate:02d}")
            with_stores += bool(found)
            for store in found:
                row = row_of(store)
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                rows.append(row)
            time.sleep(DELAY)

    if not rows:
        raise SystemExit("hiç mağaza dönmedi")
    path = OUT / f"magazalar_{dt.datetime.now(tz=dt.UTC).date().isoformat()}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    open_now = sum(1 for row in rows if row["durum"] == "OPEN")
    fix = sum(1 for row in rows if row["tur"] == "KOCTAS_FIX")
    without = sum(1 for row in rows if not row["lat"])
    print(
        f"{len(rows)} magaza ({open_now} acik, {fix} Fix), {with_stores} ilde, "
        f"koordinatsiz {without}: {path}"
    )


if __name__ == "__main__":
    main()
