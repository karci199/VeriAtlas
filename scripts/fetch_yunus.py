r"""Yunus Market's branch list, in one request.

`/magazalarimiz` renders nothing useful, but `/Subeler/Liste` — the fragment that page
loads into itself — is a plain HTML table with one row per branch: province, branch
name, address, phone, fax. No JSON, no paging, no key.

**The district is not in it.** The province column is the only administrative field, and
the address names the place the way Ankara talks: `Batıkent`, `Eryaman`, `Çayyolu`,
`Dikimevi`. Those are semt, not districts, and no register lists them. This script does
not try to resolve them — it saves the province and the address verbatim, and
`veriatlas.addresses.district_from_address` does the resolving, through PTT's
neighbourhood table. Keeping the two apart matters here: the resolver improves over time
and the dump must not be frozen against the version that happened to run today.

The chain is small and concentrated — 92 branches on 2026-09-20, 70 of them in Ankara,
the rest across six neighbouring provinces. It is a regional chain and the count should
never be read as national coverage.

Run:  uv run python scripts/fetch_yunus.py
Out:  C:\veri-ham\yunus\subeler_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import re
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/yunus")
PAGE = "https://www.yunusmarket.com.tr/magazalarimiz"
LIST = "https://www.yunusmarket.com.tr/Subeler/Liste"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COLUMNS = ["name", "province", "address", "phone"]

ROW = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)

#: The header row has `<th>` and no `<td>`, so it drops out by itself; this is the floor
#: for the rest. The chain had 92 branches on 2026-09-20 and a table that renders a
#: handful of rows is a broken page, not a shrunken chain.
MINIMUM = 40


def clean(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def branches() -> list[dict[str, str]]:
    request = urllib.request.Request(
        LIST, headers={"User-Agent": BROWSER, "Referer": PAGE, "Accept-Language": "tr"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        page = response.read().decode("utf-8", "replace")

    rows = []
    for row in ROW.findall(page):
        cells = [clean(cell) for cell in CELL.findall(row)]
        if len(cells) < 3:
            continue
        rows.append(
            {
                "name": cells[1],
                "province": cells[0],
                "address": cells[2],
                "phone": cells[3] if len(cells) > 3 else "",
            }
        )
    if len(rows) < MINIMUM:
        raise ValueError(f"yalnız {len(rows)} şube okundu, en az {MINIMUM} bekleniyor")
    return rows


def main() -> None:
    rows = branches()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"subeler_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    provinces = {row["province"] for row in rows}
    print(f"{len(rows)} şube  {len(provinces)} il  -> {path}")


if __name__ == "__main__":
    main()
