"""Download the CBRT housing price and rent series from EVDS3, untouched.

Six data groups, every series in each, at their published frequency:

    bie_kfe         house price index, TR + 26 NUTS-2 (grouped into 19 series), monthly
    bie_ykfe        new dwellings price index, TR, monthly
    bie_yokfend     existing dwellings price index, TR, monthly
    bie_ykke        new tenant rent index, TR + NUTS-2 groups, monthly
    bie_birimfiyat  unit price TL/m2 of valued dwellings, TR + 81 provinces, quarterly
    bie_bk          unit rent TL/m2 of valued dwellings, TR + 81 provinces, quarterly
    bie_tgfe        commercial property price index, quarterly
    bie_dfe         shop price index, quarterly
    bie_ofe         office price index, quarterly
    bie_dbfy        shop unit prices, annual
    bie_obfy        office unit prices, annual

One JSON per group under `$VERIATLAS_RAW/evds/<group>.json`: the series list as EVDS
returned it and the observations. The key goes in the `key` header (a query parameter
is refused with 403).

Run:  uv run python scripts/fetch_evds_housing.py               # the groups above
      uv run python scripts/fetch_evds_housing.py bie_tuksehir  # any other group, from 1970
"""

from __future__ import annotations

import json
import os
import sys

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW, settings

BASE = "https://evds3.tcmb.gov.tr/igmevdsms-dis"
GROUPS = (
    "bie_kfe",
    "bie_ykfe",
    "bie_yokfend",
    "bie_ykke",
    "bie_birimfiyat",
    "bie_bk",
    "bie_tgfe",
    "bie_dfe",
    "bie_ofe",
    "bie_dbfy",
    "bie_obfy",
)
START_YEAR, END_YEAR = 2000, 2026
#: EVDS answers long code lists with an error; twenty codes per request is safe.
BATCH = 20
#: Rows (periods) EVDS returns per request at most.
ROW_LIMIT = 1000


def main() -> None:
    if not settings.evds_api_key:
        raise SystemExit("EVDS_API_KEY tanimli degil")
    out = RAW / "evds"
    out.mkdir(parents=True, exist_ok=True)
    groups, start = (sys.argv[1:], 1970) if sys.argv[1:] else (GROUPS, START_YEAR)
    with httpx.Client(
        base_url=BASE, headers={"key": settings.evds_api_key}, timeout=120
    ) as client:
        for group in groups:
            try:
                fetch_group(client, out, group, start)
            except (httpx.HTTPError, ValueError, KeyError) as error:
                # One broken group must not end a pull of hundreds: named, skipped, and
                # retried by running again, since finished groups are skipped.
                print(group, "HATA:", str(error)[:200])


def fetch_group(client, out, group: str, start: int) -> None:
    # EVDS_ATLA=1: leave groups already on disk alone (the whole-catalogue pull).
    if os.environ.get("EVDS_ATLA") and (out / f"{group}.json").exists():
        return
    series = client.get(f"/serieList/type=json&code={group}")
    series.raise_for_status()
    codes = [s["SERIE_CODE"] for s in series.json()]
    by_period: dict[str, dict] = {}
    refused: list[str] = []
    chunks = [
        (codes[i : i + BATCH], start, END_YEAR) for i in range(0, len(codes), BATCH)
    ]
    while chunks:
        chunk, first, last = chunks.pop(0)
        r = client.get(
            f"/series={'-'.join(chunk)}&startDate=01-01-{first}"
            f"&endDate=31-12-{last}&type=json"
        )
        if r.status_code == 400:
            # One series EVDS lists but will not serve fails the whole chunk:
            # split it, and name the series that fail alone.
            if len(chunk) == 1:
                refused.append(chunk[0])
            else:
                chunks[:0] = [([code], first, last) for code in chunk]
            continue
        r.raise_for_status()
        part = r.json()["items"]
        if len(part) >= ROW_LIMIT:
            # EVDS cuts an answer at ROW_LIMIT rows without saying so, keeping
            # the latest: a daily series from 1970 came back as 2023-2026 only.
            if first == last:
                raise ValueError(group + ": tek yil satir sinirini asiyor")
            middle = (first + last) // 2
            chunks[:0] = [(chunk, first, middle), (chunk, middle + 1, last)]
            continue
        # Each chunk comes back over its own series' span, so chunks are merged
        # on the period label, not by position.
        for extra in part:
            by_period.setdefault(extra["Tarih"], {}).update(extra)
    items = sorted(by_period.values(), key=lambda i: int(i["UNIXTIME"]["$numberLong"]))
    payload = {
        "group": group,
        "series": series.json(),
        "refused": refused,
        "items": items,
    }
    (out / f"{group}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    print(group, len(codes), "seri", len(items), "donem", "reddedilen:", refused)


if __name__ == "__main__":
    main()
