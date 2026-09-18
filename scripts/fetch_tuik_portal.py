r"""TÜİK's new data portal (veriportali.tuik.gov.tr): the whole catalogue, as JSON.

`data.tuik.gov.tr` now redirects here, and the new site is a React app talking to a REST
API. Two things had to be got right, neither of them guessed:

* The WAF answers 403 to a bare request. A full browser header set (User-Agent, Origin,
  Referer, X-Requested-With) and the cookies handed out by one GET of the home page are
  enough; no account, no login.
* The search endpoint answers 404 — not 400 — when the body is missing a field, so a
  partly-right payload looks like a wrong address. The shape below was read off the app's
  own XHR, not invented:

      POST /api/tr/data/search
      {"text": "", "page": 1, "typeIds": [], "categoryIds": [], "subCategoryIds": [],
       "years": [], "levels": [], "archive": false, "autoFilter": false}

Ten results a page, `total` in the answer. Six types: 1 news bulletin, 2 tables and
charts, 3 metadata, 4 report, 5 database, 6 publication. Type 5 is the interesting one —
its rows carry the MEDAS `kn=` number of every database TÜİK publishes, which is the list
this repository's MEDAS fetcher has been working through without ever seeing it whole.

Saved page by page to `C:\veri-ham\tuik_portal\<type>\page_<n>.json`, so a broken run
resumes, and flattened into `katalog.csv` at the end.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import httpx

OUT = Path("C:/veri-ham/tuik_portal")
API = "https://veriportali.tuik.gov.tr/api/tr/data/search"
HOME = "https://veriportali.tuik.gov.tr/"
TYPES = {
    1: "bulten",
    2: "tablo",
    3: "metaveri",
    4: "rapor",
    5: "veritabani",
    6: "yayin",
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://veriportali.tuik.gov.tr",
    "Referer": HOME,
    "X-Requested-With": "XMLHttpRequest",
}


def session() -> httpx.Client:
    client = httpx.Client(
        timeout=60, verify=False, headers=HEADERS, follow_redirects=True
    )
    client.get(HOME)  # the WAF's cookies
    return client


def page(client: httpx.Client, type_id: int, number: int) -> dict:
    body = {
        "text": "",
        "page": number,
        "typeIds": [type_id],
        "categoryIds": [],
        "subCategoryIds": [],
        "years": [],
        "levels": [],
        "archive": False,
        "autoFilter": False,
    }
    for attempt in range(5):
        try:
            answer = client.post(API, json=body)
            answer.raise_for_status()
            return answer.json()["data"]
        except (httpx.HTTPError, KeyError, json.JSONDecodeError):
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def fetch() -> None:
    client = session()
    try:
        for type_id, name in TYPES.items():
            folder = OUT / name
            folder.mkdir(parents=True, exist_ok=True)
            first = page(client, type_id, 1)
            total = first["total"]
            pages = -(-total // 10)
            print(f"{name}: {total} kayıt, {pages} sayfa", flush=True)
            (folder / "page_1.json").write_text(
                json.dumps(first["data"], ensure_ascii=False), encoding="utf-8"
            )
            for number in range(2, pages + 1):
                path = folder / f"page_{number}.json"
                if path.exists():
                    continue
                rows = page(client, type_id, number)["data"]
                path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
                if number % 25 == 0:
                    print(f"  {name} {number}/{pages}", flush=True)
                time.sleep(0.2)
    finally:
        client.close()
    flatten()


def flatten() -> None:
    """One CSV of everything: type, title, date, url."""
    target = OUT / "katalog.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tip", "baslik", "tarih", "adres"])
        count = 0
        for name in TYPES.values():
            for path in sorted((OUT / name).glob("page_*.json")):
                for row in json.loads(path.read_text(encoding="utf-8")):
                    writer.writerow(
                        [
                            name,
                            row.get("title", ""),
                            row.get("date", ""),
                            row.get("url", ""),
                        ]
                    )
                    count += 1
    print(f"katalog.csv: {count} satır")


if __name__ == "__main__":
    sys.exit(fetch())
