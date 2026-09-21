r"""Türk Telekom's offices and dealers, from the endpoint its store map calls.

The map page draws clusters and nothing readable, but its own inline script names the
call: `POST _layouts/15/TTWebsite/Partners/Ajax.aspx/GetPartnersAll` with a body of
`{"IsCorporate": true|false}`. Nothing else is accepted — an empty body answers 500, and
so does every other parameter name tried, which is why the payload was read out of the
page rather than guessed.

**Two calls, because the network is two networks.** `IsCorporate: false` returns the
consumer side (871 rows on 2026-09-20) and `true` the business side (906). They overlap
in neither id nor purpose and are kept apart by an `audience` column.

**Seven kinds on the consumer side, and they are not seven kinds of shop.** The response
carries `PType` per row:

| PType | 2026-09-20 | what it is |
|---|---|---|
| TTM Şube | 417 | a dealer's branch |
| TTM | 182 | a dealer's main shop |
| TT Ofis | 121 | Türk Telekom's own office |
| TT Mini Ofis | 79 | a smaller one |
| TTMM Ofis | 30 | mobile-only office |
| TTMM Mini Ofis | 25 | smaller again |
| EDM | 17 | electronic transaction point |

Adding them gives a number that answers no question, the same trap Vodafone's store
finder sets by listing payment points beside phone shops. The kind is carried on every
row and the adapter chooses.

`CoordinateX` is the **latitude** and `CoordinateY` the longitude (41.07 / 28.90 is
İstanbul, not the Indian Ocean). The names invite the opposite reading, so they are
mapped here once and never passed through raw.

Run:  uv run python scripts/fetch_turk_telekom.py
Out:  C:\veri-ham\turk_telekom\bayiler_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/turk_telekom")
ENDPOINT = (
    "https://www.turktelekom.com.tr/_layouts/15/TTWebsite/Partners/Ajax.aspx/"
    "GetPartnersAll"
)
PAGE = "https://www.turktelekom.com.tr/destek/iletisim/telekom-ofis-ve-magazalar"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = [
    "name",
    "partner_id",
    "audience",
    "kind",
    "province",
    "source_district",
    "street",
    "phone",
    "lat",
    "lng",
]

#: 1.777 rows over the two calls on 2026-09-20.
MINIMUM = 800


def partners(corporate: bool) -> list[dict]:
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps({"IsCorporate": corporate}).encode(),
        headers={
            "User-Agent": BROWSER,
            "Content-Type": "application/json",
            "Referer": PAGE,
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["d"]["Data"]


def rows() -> list[dict[str, str]]:
    out = []
    for corporate, audience in ((False, "bireysel"), (True, "kurumsal")):
        for item in partners(corporate):
            out.append(
                {
                    "name": (item.get("CommercialName") or "").strip(),
                    "partner_id": str(item.get("PartnerID") or ""),
                    "audience": audience,
                    "kind": (item.get("PType") or "").strip(),
                    "province": (item.get("City") or "").strip(),
                    "source_district": (item.get("District") or "").strip(),
                    "street": (item.get("Street") or "").strip(),
                    "phone": str(item.get("ContactTel") or ""),
                    # X is latitude, Y is longitude. See the module docstring.
                    "lat": item.get("CoordinateX"),
                    "lng": item.get("CoordinateY"),
                }
            )
    if len(out) < MINIMUM:
        raise ValueError(f"yalnız {len(out)} kayıt döndü, en az {MINIMUM} bekleniyor")
    return out


def main() -> None:
    found = rows()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"bayiler_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(found)
    kinds = {row["kind"] for row in found}
    print(f"{len(found)} kayıt  {len(kinds)} tür  -> {path}")


if __name__ == "__main__":
    main()
