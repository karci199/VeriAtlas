r"""Download BDDK FinTürk provincial banking tables (December of each year).

www.bddk.org.tr/BultenFinturk answers a form post, `tr/Home/VeriGetir`, with JSON: column names
and one row per province for a table, a period and a bank group. Seven tables (loans, deposits,
retail banking, selected sectoral loans, ratios, branches and per-capita figures, gold), seven
groups (sector total, deposit, development and investment, participation, foreign, state,
domestic private), periods 2007-12 to 2025-12. Quarterly periods exist; only December is taken. Two combinations the
source does not hold are skipped: gold before 2015, and deposits of development and investment
banks (they take none).

Writes `C:\veri-ham\bddk\finturk\<table>-<group>-<year>.json`; existing files are kept.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

URL = "https://www.bddk.org.tr/BultenFinturk/tr/Home/VeriGetir"
OUT = Path("C:/veri-ham/bddk/finturk")
TABLES = range(1, 8)
GROUPS = (10001, 10002, 10003, 10004, 10005, 10006, 10007)
YEARS = range(2007, 2026)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"},
        timeout=120,
        verify=False,
    )
    for table in TABLES:
        for group in GROUPS:
            for year in YEARS:
                if table == 7 and year < 2015:
                    continue  # gold is published from 2015
                if table == 2 and group == 10003:
                    continue  # development and investment banks take no deposits
                target = OUT / f"{table}-{group}-{year}.json"
                if target.exists():
                    continue
                form = {
                    "tabloNo": str(table),
                    "donem": f"{year}-12",
                    "tarafList[0]": str(group),
                    "sehirList[0]": "HEPSİ",
                }
                for attempt in range(3):
                    try:
                        answer = client.post(URL, data=form).raise_for_status().json()
                        break
                    except (httpx.HTTPError, ValueError):
                        time.sleep(5 * (attempt + 1))
                else:
                    print("HATA", table, group, year, flush=True)
                    continue
                target.write_text(
                    json.dumps(answer, ensure_ascii=False), encoding="utf-8"
                )
            print(table, group, flush=True)


if __name__ == "__main__":
    main()
