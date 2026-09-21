r"""KFC Türkiye's restaurants, read out of the page's own Next.js payload.

The restaurant page looks like a map that fetches: "Harita yükleniyor…" is the only thing
on screen without JavaScript, and watching the network while it loads shows no request for
a restaurant list at all. The list is already there — inside the streamed RSC payload, as
a string, with every quote escaped:

    self.__next_f.push([1,"5:[\"$\",\"$L12\",null,{\"initialRestaurants\":[{\"id\":503,…

This is the same shape Gratis turned out to have, and the same lesson applies: looking at
the *picture* of the page and concluding "the data is not here" is not enough; the field
name has to be searched for in the raw body, in its escaped spelling.

Each record carries `lat`, `lng`, `city`, `district` and an `active` flag. Everything is
written out, inactive restaurants included and flagged rather than dropped — a chain's own
"temporarily closed" bookkeeping is not this fetcher's call to make, and Koçtaş showed
what happens when such a field is trusted without checking it.

**What comes back is 41 restaurants in 6 provinces, and that is the whole site.** The
page's own province filter offers exactly those six — Ankara, Bursa, Gaziantep, İstanbul,
İzmir, İzmit — so this is not a first page or a nearest-N cut; asking with a different
`?lat=/?city=` returns the same 41. The brand is generally reported to run several times
that many restaurants in Türkiye, so the file is **kept as raw and deliberately not wired
into `chain_restaurants`**: a count that is visibly short of its own brand would be read
as "KFC is absent from 75 provinces", which is a claim about the country rather than
about this page. What the gap is — franchisees with their own sites, a half-migrated
list — is not something this fetcher can find out, and guessing is worse than waiting.

`robots.txt` answers 404: the site publishes no restrictions at all, which is permission
by the standard's own rule. One request, no crawl.

Run:  uv run python scripts/fetch_kfc.py
Out:  C:\veri-ham\kfc\restoranlar_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

URL = "https://www.kfcturkiye.com/restoranlar"
OUT = RAW / "kfc"
UA = "ClaudeBot/1.0 (+https://claude.com/claudebot)"
#: The payload is a JS string literal, so the array is escaped inside it.
START = re.compile(r'\\"initialRestaurants\\":')
COLUMNS = ["id", "ad", "il", "ilce", "adres", "lat", "lng", "acik"]


def restaurants(body: str) -> list[dict]:
    found = START.search(body)
    if not found:
        raise SystemExit("initialRestaurants bulunamadı — sayfanın şekli değişmiş")
    # The whole push() argument is one JS string. Decoding it as JSON turns the escaped
    # quotes back into real ones; only then is the array itself readable. Counting
    # brackets instead would stop at the first `]` inside an address.
    line_start = body.rindex('push([1,"', 0, found.start()) + len("push([1,")
    line_end = body.index('"])', line_start) + 1
    inner = json.loads(body[line_start:line_end])
    marker = '"initialRestaurants":'
    at = inner.index(marker) + len(marker)
    data, _ = json.JSONDecoder().raw_decode(inner, at)
    if not isinstance(data, list):
        raise SystemExit(f"beklenen liste değil: {type(data).__name__}")
    return data


def main() -> None:
    answer = httpx.get(
        URL, headers={"User-Agent": UA}, timeout=60, follow_redirects=True
    )
    answer.raise_for_status()
    found = restaurants(answer.text)

    rows = []
    seen: set[int] = set()
    for store in found:
        if store["id"] in seen:
            raise SystemExit(f"yinelenen kimlik: {store['id']}")
        seen.add(store["id"])
        rows.append(
            {
                "id": store.get("id", ""),
                "ad": store.get("name", ""),
                "il": store.get("city", ""),
                "ilce": store.get("district", ""),
                "adres": store.get("address", ""),
                "lat": store.get("lat", ""),
                "lng": store.get("lng", ""),
                "acik": int(bool(store.get("active"))),
            }
        )

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"restoranlar_{dt.datetime.now(tz=dt.UTC).date().isoformat()}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    closed = sum(1 for row in rows if not row["acik"])
    print(
        f"{len(rows)} restoran, {len({r['il'] for r in rows})} il, "
        f"kapali isaretli {closed}: {path}"
    )


if __name__ == "__main__":
    main()
