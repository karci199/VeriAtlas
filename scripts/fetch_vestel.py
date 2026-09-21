r"""Vestel's sales points and authorised services, province by province.

Vestel sells through dealers rather than through its own shops, so this is a different
kind of network from BİM or ŞOK: the sign says Vestel, the company behind it is a local
one — the first Ankara record is titled `GÖKTAŞLAR İÇ DIŞ TİCARET ... KIZLARPINARI`. That
is the dealer's own trade name, and it is kept as published rather than tidied into
"Vestel Kızlarpınarı".

The store finder is a jQuery page and its endpoint is written in the page itself, in the
`storeAndServices({...})` call that starts the map:

    POST vestel.com.tr/lookup/offlinestores    {cityID: <plaka>, districtID: ""}
    POST vestel.com.tr/lookup/technicalservice {cityID: <plaka>, districtID: ""}

An empty district is the whole province — the dropdown narrows, it does not gate. There
is no "all provinces" value: `cityID=0` answers `{"Success":true,"Result":[]}`, which is
an empty answer to a valid question and not an error, so the sweep is 81 requests.

Both endpoints answer the same record shape, with `Lat`/`Long` and the dealer's own
`ILCE`. The coordinate is what gets used downstream; `ILCE` is written to the file beside
it so a later pass can check one against the other.

**Two networks, two files.** A shop that sells washing machines and a workshop that
repairs them are not the same count and are not added together: `magazalar_*.csv` and
`servisler_*.csv`.

robots.txt allows it: Vestel disallows `/api/`, `/cart/`, `/checkout/` and search, and
`/lookup/` is none of those.

Run:  uv run python scripts/fetch_vestel.py
Out:  C:\veri-ham\vestel\magazalar_<YYYY-MM-DD>.csv
      C:\veri-ham\vestel\servisler_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import sys
import time

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

OUT = RAW / "vestel"
ENDPOINTS = {
    "magazalar": "https://www.vestel.com.tr/lookup/offlinestores",
    "servisler": "https://www.vestel.com.tr/lookup/technicalservice",
}
UA = "ClaudeBot/1.0 (+https://claude.com/claudebot)"
#: Between requests. Vestel showed no rate limit at this pace; the lesson from Domino's
#: is that the threshold is never known in advance, and 81 requests is small enough that
#: going slowly costs nothing.
DELAY = 0.4
COLUMNS = ["id", "ad", "il", "plaka", "ilce", "semt", "adres", "telefon", "lat", "lng"]


def rows_for(client: httpx.Client, url: str, plate: int) -> list[dict]:
    answer = client.post(url, data={"cityID": plate, "districtID": ""})
    answer.raise_for_status()
    payload = answer.json()
    if not payload.get("Success"):
        raise SystemExit(
            f"{plate}: {payload.get('Message') or payload.get('Exception')}"
        )
    return payload.get("Result") or []


def sweep(client: httpx.Client, url: str) -> list[dict]:
    seen: set[int] = set()
    out: list[dict] = []
    empty: list[int] = []
    for plate in range(1, 82):
        found = rows_for(client, url, plate)
        if not found:
            empty.append(plate)
        for record in found:
            # The same dealer can answer for two provinces if the source files it twice;
            # counting it twice would inflate a number nobody re-counts by hand.
            if record["ID"] in seen:
                continue
            seen.add(record["ID"])
            out.append(
                {
                    "id": record["ID"],
                    "ad": record.get("MAGAZATITLE", ""),
                    "il": record.get("IL", ""),
                    "plaka": record.get("PLAKA", ""),
                    "ilce": record.get("ILCE", ""),
                    "semt": record.get("SEMT") or "",
                    "adres": record.get("ADRES", ""),
                    "telefon": record.get("MAGAZATEL", ""),
                    "lat": record.get("Lat") or "",
                    "lng": record.get("Long") or "",
                }
            )
        time.sleep(DELAY)
    if empty:
        # Not an error on its own — but a province with no Vestel dealer at all would be
        # news, so it is printed rather than passed over.
        print(f"  kayit dondurmeyen plakalar: {empty}")
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(tz=dt.UTC).date().isoformat()
    headers = {"User-Agent": UA, "X-Requested-With": "XMLHttpRequest"}
    with httpx.Client(headers=headers, timeout=60, follow_redirects=True) as client:
        for name, url in ENDPOINTS.items():
            print(f"{name}...", flush=True)
            rows = sweep(client, url)
            without = sum(1 for row in rows if not row["lat"] or not row["lng"])
            path = OUT / f"{name}_{stamp}.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
            provinces = {row["il"] for row in rows if row["il"]}
            print(
                f"  {len(rows)} kayit, {len(provinces)} il, koordinatsiz {without}: {path}"
            )


if __name__ == "__main__":
    main()
