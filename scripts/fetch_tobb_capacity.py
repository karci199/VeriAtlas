r"""Download TOBB's industrial capacity by province for every PRODCOM product.

sanayi.org.tr ("Sanayi Bilgi Sistemi", TOBB) is an Angular/JHipster app. Its public
"Sanayi Veri Tabanı" pages read two endpoints without logging in:

- `GET apiv2/prodcom-kodus?size=2000&page=N` — the product code list (4,673 codes,
  paged; `X-Total-Count` gives the total), each with its unit, CPA, NACE and sector.
- `POST api/svt/illere-gore-kapasite-bilgileri` with `{"params": {"urunKodu": code}}` —
  one row per province: registered producers, staff by type (engineer, technician,
  foreman, worker, clerical) and capacity in the product's unit. Capacity is "*" where
  a province has three or fewer producers (withheld by TOBB, not zero). An empty list
  means no registered producer anywhere.

The figures are a snapshot of the capacity reports currently valid, not a yearly series.

Writes `C:\veri-ham\tobb\kapasite\urun\<code>.json` and the code list beside it;
already downloaded codes are skipped, so the same command resumes. Progress goes to
stdout (one line per 100 codes) so a detached run can be followed from its log.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

FOLDER = Path("C:/veri-ham/tobb/kapasite")
BASE = "https://sanayi.org.tr/"
CAPACITY = BASE + "api/svt/illere-gore-kapasite-bilgileri"
PAUSE = 0.5


def code_list(client: httpx.Client) -> list[dict]:
    path = FOLDER / "prodcom-kodlari.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    codes: list[dict] = []
    page = 0
    while True:
        r = client.get(
            BASE + "apiv2/prodcom-kodus",
            params={"size": 2000, "page": page, "sort": "id,asc"},
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        codes += batch
        page += 1
    total = int(r.headers.get("X-Total-Count", len(codes)))
    if len(codes) != total:
        sys.exit(f"code list: {len(codes)} read, {total} announced")
    path.write_text(json.dumps(codes, ensure_ascii=False), encoding="utf-8")
    return codes


def main() -> None:
    out = FOLDER / "urun"
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0"}) as client:
        codes = sorted({c["kodu"] for c in code_list(client)})
        print(f"{len(codes)} codes", flush=True)
        done = errors = 0
        for i, code in enumerate(codes, 1):
            target = out / f"{code}.json"
            if not target.exists():
                for attempt in range(4):
                    try:
                        r = client.post(CAPACITY, json={"params": {"urunKodu": code}})
                        r.raise_for_status()
                        rows = r.json()
                        if not isinstance(rows, list):
                            raise ValueError(f"not a list: {str(rows)[:100]}")
                        target.write_text(
                            json.dumps(rows, ensure_ascii=False), encoding="utf-8"
                        )
                        done += 1
                        break
                    except (httpx.HTTPError, ValueError) as e:
                        print(
                            f"{time.strftime('%H:%M:%S')} retry {code}: {e}", flush=True
                        )
                        time.sleep(10 * (attempt + 1))
                else:
                    errors += 1
                time.sleep(PAUSE)
            if i % 100 == 0:
                print(
                    f"{time.strftime('%H:%M:%S')} {i}/{len(codes)} new {done} failed {errors}",
                    flush=True,
                )
        print(
            f"{time.strftime('%H:%M:%S')} finished: new {done}, failed {errors}",
            flush=True,
        )


if __name__ == "__main__":
    main()
