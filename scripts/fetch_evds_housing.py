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

Run:  uv run python scripts/fetch_evds_housing.py
"""

from __future__ import annotations

import json
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
START, END = "01-01-2000", "31-12-2026"
#: EVDS answers long code lists with an error; twenty codes per request is safe.
BATCH = 20


def main() -> None:
    if not settings.evds_api_key:
        raise SystemExit("EVDS_API_KEY tanimli degil")
    out = RAW / "evds"
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        base_url=BASE, headers={"key": settings.evds_api_key}, timeout=120
    ) as client:
        for group in GROUPS:
            series = client.get(f"/serieList/type=json&code={group}")
            series.raise_for_status()
            codes = [s["SERIE_CODE"] for s in series.json()]
            items: list[dict] = []
            refused: list[str] = []
            chunks = [codes[i : i + BATCH] for i in range(0, len(codes), BATCH)]
            while chunks:
                chunk = chunks.pop(0)
                r = client.get(
                    f"/series={'-'.join(chunk)}&startDate={START}&endDate={END}&type=json"
                )
                if r.status_code == 400:
                    # One series EVDS lists but will not serve fails the whole chunk:
                    # split it, and name the series that fail alone.
                    if len(chunk) == 1:
                        refused.append(chunk[0])
                    else:
                        chunks[:0] = [[code] for code in chunk]
                    continue
                r.raise_for_status()
                part = r.json()["items"]
                if not items:
                    items = part
                else:
                    if len(part) != len(items):
                        raise ValueError(group + ": parcalarin donem sayisi farkli")
                    for whole, extra in zip(items, part, strict=True):
                        if whole["Tarih"] != extra["Tarih"]:
                            raise ValueError(group + ": parcalarin tarihleri farkli")
                        whole.update(extra)
            payload = {
                "group": group,
                "series": series.json(),
                "refused": refused,
                "items": items,
            }
            (out / f"{group}.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            print(
                group, len(codes), "seri", len(items), "donem", "reddedilen:", refused
            )


if __name__ == "__main__":
    main()
