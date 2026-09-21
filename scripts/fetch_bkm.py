r"""BKM's monthly card spending by merchant sector, and the same split for e-commerce.

What BKM adds to the warehouse is the **sector**, not the geography. The province-level
card numbers are already here and from a better source: TBB publishes POS terminals, ATMs
and card-accepting merchants per province, 2010-2025 (`bank_pos_terminals`, `bank_atms`,
`bank_merchants`), and EVDS carries BKM's own national index and the weekly spending
series (`card_payment_index`, `card_spending_weekly`). BKM publishes nothing by province.

What is not in the warehouse is which *trade* the money is spent in, and that is what
these two pages hold, monthly since 2017:

    GET bkm.com.tr/secilen-aya-ait-sektorel-gelisim/?filter_year=&filter_month=&List=Listele
    GET bkm.com.tr/internetten-yapilan-kartli-odemelerin-secilen-aya-ait-sektorel-gelisimi/

Each is one HTML table: merchant group × (transaction count, amount) × (credit, debit).
Amounts are published in million TL and are written out in TL here — the unit belongs to
the number, not to a column heading somebody has to remember.

**The two tables do not have the same shape, and assuming they did is the trap here.**
The first has four numbers per sector — count and amount, credit and debit. The second has
**twelve**, in two overlapping blocks: the domestic cards' use at home and abroad
(`Yurtiçi / Yurtdışı / Toplam`) and everyone's use at domestic merchants (`Yerli Kart /
Yabancı Kart / Toplam`), each of those for counts and again for amounts. `Yurtiçi` and
`Yerli Kart` are the same number appearing twice, once in each block. Reading the second
table with the first one's four columns produced an 831-billion-lira car rental month
before the shapes were separated. Each page therefore declares its own columns and the
row length is checked against them.

**The two pages are not a whole and a part of it.** The second counts card payments made
over the internet; the first counts everything. Subtracting one from the other to get
"in-store" is the caller's decision and this fetcher does not make it.

Sector names are kept exactly as published, including the ones BKM writes without Turkish
letters (`BIREYSEL EMEKLILIK` beside `BENZİN VE YAKIT İSTASYONLARI`) — normalising them
here would quietly merge or split trades, and the mapping is a decision for the adapter.

Run:  uv run python scripts/fetch_bkm.py [--baslangic 2017]
Out:  C:\veri-ham\bkm\sektorel_<YYYY-MM-DD>.csv
      C:\veri-ham\bkm\sektorel_internet_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
import time

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

OUT = RAW / "bkm"
PAGES = {
    "sektorel": "https://bkm.com.tr/secilen-aya-ait-sektorel-gelisim/",
    "sektorel_internet": (
        "https://bkm.com.tr/internetten-yapilan-kartli-odemelerin-secilen-aya-ait-"
        "sektorel-gelisimi/"
    ),
}
UA = "ClaudeBot/1.0 (+https://claude.com/claudebot)"
DELAY = 0.4
#: Each page's numeric columns, in the order the table prints them, read off the two
#: header rows. `tutar_` columns are published in million TL, `adet_` are plain counts.
FIELDS = {
    "sektorel": ["adet_kredi", "adet_banka", "tutar_kredi", "tutar_banka"],
    "sektorel_internet": [
        "adet_yerli_yurtici",
        "adet_yerli_yurtdisi",
        "adet_yerli_toplam",
        "adet_yurtici_yerli_kart",
        "adet_yurtici_yabanci_kart",
        "adet_yurtici_toplam",
        "tutar_yerli_yurtici",
        "tutar_yerli_yurtdisi",
        "tutar_yerli_toplam",
        "tutar_yurtici_yerli_kart",
        "tutar_yurtici_yabanci_kart",
        "tutar_yurtici_toplam",
    ],
}
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
TAG = re.compile(r"<[^>]+>")


def number(text: str) -> float | None:
    """`10.273,69` -> 10273.69. Turkish separators, both of them."""
    cleaned = text.replace(".", "").replace(",", ".").strip()
    if not cleaned or not re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
        return None
    return float(cleaned)


def table_rows(html: str) -> list[list[str]]:
    out = []
    for row in ROW.findall(html):
        cells = [
            TAG.sub("", cell).replace("&nbsp;", " ").strip()
            for cell in CELL.findall(row)
        ]
        if len(cells) >= 5 and cells[0]:
            out.append(cells)
    return out


def month(
    client: httpx.Client, url: str, year: int, index: int, fields: list[str]
) -> list[dict]:
    answer = client.get(
        url, params={"filter_year": year, "filter_month": index, "List": "Listele"}
    )
    answer.raise_for_status()
    period = f"{year}-{index:02d}"
    rows = []
    for cells in table_rows(answer.text):
        values = [number(cell) for cell in cells[1 : 1 + len(fields)]]
        # A header row parses as text in every numeric column; a real row parses as at
        # least one number. This is what keeps the two heading rows out without matching
        # on their wording, which BKM has changed before.
        if all(value is None for value in values):
            continue
        if len(cells) - 1 != len(fields):
            raise SystemExit(
                f"{period}: satırda {len(cells) - 1} sayı var, {len(fields)} bekleniyordu "
                f"({cells[0]}) — tablonun şekli değişmiş"
            )
        row = {"donem": period, "isyeri_grubu": cells[0]}
        for field, value in zip(fields, values, strict=True):
            if value is None:
                row[field] = ""
            elif field.startswith("tutar"):
                row[field] = f"{value * 1_000_000:.0f}"  # milyon TL -> TL
            else:
                row[field] = f"{value:.0f}"
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="BKM sektörel kartlı ödeme tabloları")
    parser.add_argument("--baslangic", type=int, default=2017, help="ilk yıl")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.now(tz=dt.UTC).date()
    stamp = today.isoformat()
    with httpx.Client(
        headers={"User-Agent": UA}, timeout=60, follow_redirects=True
    ) as c:
        for name, url in PAGES.items():
            fields = FIELDS[name]
            rows: list[dict] = []
            months_with_data = 0
            for year in range(args.baslangic, today.year + 1):
                for index in range(1, 13):
                    if year == today.year and index > today.month:
                        break
                    found = month(c, url, year, index, fields)
                    months_with_data += bool(found)
                    rows.extend(found)
                    time.sleep(DELAY)
                print(f"  {name} {year}: {len(rows)} satir", flush=True)
            if not rows:
                raise SystemExit(f"{name}: hic satir okunamadi")
            path = OUT / f"{name}_{stamp}.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["donem", "isyeri_grubu", *fields]
                )
                writer.writeheader()
                writer.writerows(rows)
            sectors = {row["isyeri_grubu"] for row in rows}
            print(
                f"{name}: {len(rows)} satir, {len(sectors)} isyeri grubu, "
                f"{months_with_data} ay: {path}"
            )


if __name__ == "__main__":
    main()
