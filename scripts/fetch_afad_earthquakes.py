"""Download AFAD's earthquake catalogue, one JSON file per year.

deprem.afad.gov.tr/apiv2/event/filter redirects to servisnet.afad.gov.tr/apigateway; no key.
Each event carries date, magnitude and type, depth, and the province, district and
neighbourhood AFAD assigns. Months are fetched one by one so a busy year (2023) is never cut
by a response limit; a month that returns exactly as many rows as the previous largest month is
not treated specially, but the per-month counts are printed.

Files: C:/veri-ham/afad/deprem-<year>.json (existing years are kept, except the current one).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import httpx

ROOT = Path("C:/veri-ham/afad")
URL = "https://servisnet.afad.gov.tr/apigateway/deprem/apiv2/event/filter"
FIRST, LAST = 1900, 2025


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"}, timeout=180, verify=False
    )
    for year in range(FIRST, LAST + 1):
        target = ROOT / f"deprem-{year}.json"
        if target.exists():
            continue
        events = []
        for month in range(1, 13):
            start = dt.date(year, month, 1)
            end = dt.date(year + (month == 12), month % 12 + 1, 1)
            response = client.get(
                URL,
                params={
                    "start": f"{start}T00:00:00",
                    "end": f"{end}T00:00:00",
                    "format": "json",
                },
            )
            response.raise_for_status()
            events.extend(response.json())
        ids = [e["eventID"] for e in events]
        if len(ids) != len(set(ids)):
            raise ValueError(f"AFAD {year}: aynı olay iki kez")
        target.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
        if events:
            print(year, len(events), flush=True)


if __name__ == "__main__":
    main()
