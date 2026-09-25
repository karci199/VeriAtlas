r"""Health facilities and schools from the Ministry of Health code server (SKRS).

SKRS (skrs.saglik.gov.tr) is the reference server every health information system in the
country reads its codes from. Two of its lists are registers of places:

* **Health facilities** — every institution that has a ministry institution code: hospitals,
  family health centres (ASM), family medicine units (AHB), health posts, 112 stations,
  private clinics, laboratories, opticians. Current: most rows were touched in 2023-2026.
* **Educational institutions** — MEB schools with their MEB institution code, NVİ district
  code and school type. Loaded once: every row is dated 01.01.2017, so this is a **2017
  snapshot** and must be labelled as one (schools opened since are missing, closed ones
  still read "Aktif").

Both answer one POST per province:

    POST /Anasayfa/KurumIslemleriDetay/482        ilKodu=<plate>&ilceKodu=-1&Id=482
    POST /Anasayfa/EgitimKurumIslemleriDetay/482  ilKodu=<plate>&ilceKodu=-1&Id=482

The answer is an HTML fragment with a DataTables table; all rows come in one piece. The
education list is linked from the site's own UI; the health-facility endpoint is not linked
anywhere and was found by analogy with it. robots.txt is empty.

The education list gives districts only as NVİ codes, so the district names are read from
the site's own address feed, `POST /Anasayfa/GetAdresKodlari seviye=2&kod=<plate>`.

Rows of self-employed practitioners (muayenehane, psychologist, dietitian) carry a person's
name. The raw file keeps them as received; only counts go into the warehouse.

A province that comes back with no rows stops the run: an empty table is a failed request
until proven otherwise, never "no facilities".

Run:  uv run python scripts/fetch_skrs_institutions.py
Out:  C:\veri-ham\skrs\saglik_tesisleri_<YYYY-MM-DD>.csv
      C:\veri-ham\skrs\egitim_kurumlari_<YYYY-MM-DD>.csv
      C:\veri-ham\skrs\ilce_kodlari.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import sys
import time
from html.parser import HTMLParser

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

OUT = RAW / "skrs"
BASE = "https://skrs.saglik.gov.tr"
UA = "ClaudeBot/1.0 (+https://claude.com/claudebot)"
DELAY = 1.0
LISTS = {
    "saglik_tesisleri": "/Anasayfa/KurumIslemleriDetay/482",
    "egitim_kurumlari": "/Anasayfa/EgitimKurumIslemleriDetay/482",
}


class Table(HTMLParser):
    """Collects header cells and body rows of every table in the fragment."""

    def __init__(self) -> None:
        super().__init__()
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        self._cell: list[str] | None = None
        self._row: list[str] | None = None
        self._in_body = False

    def handle_starttag(self, tag, attrs):
        if tag == "tbody":
            self._in_body = True
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "tbody":
            self._in_body = False
        elif tag in ("td", "th") and self._cell is not None:
            text = " ".join("".join(self._cell).split())
            if tag == "th":
                self.headers.append(text)
            elif self._row is not None:
                self._row.append(text)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._in_body and self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def fetch_list(
    client: httpx.Client, path: str, plate: int
) -> tuple[list[str], list[list[str]]]:
    answer = client.post(BASE + path, data={"ilKodu": plate, "ilceKodu": -1, "Id": 482})
    answer.raise_for_status()
    if "/Hata/" in str(answer.url):
        raise SystemExit(f"{path} il {plate}: hata sayfasına yönlendi")
    table = Table()
    table.feed(answer.text)
    # The fragment also holds the code system's own metadata table (two-cell rows);
    # only rows as wide as the data header are records.
    rows = [r for r in table.rows if len(r) == len(table.headers)]
    return table.headers, rows


def district_codes(client: httpx.Client, plate: int) -> list[tuple[str, str]]:
    answer = client.post(
        BASE + "/Anasayfa/GetAdresKodlari", data={"seviye": 2, "kod": plate}
    )
    answer.raise_for_status()
    table = OptionList()
    table.feed(answer.text)
    return [(code, name) for code, name in table.options if code != "-1"]


class OptionList(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.options: list[tuple[str, str]] = []
        self._value: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "option":
            self._value = dict(attrs).get("value", "").strip()

    def handle_data(self, data):
        if self._value is not None and data.strip():
            self.options.append((self._value, data.strip()))
            self._value = None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.now(tz=dt.UTC).date().isoformat()
    headers = {
        "User-Agent": UA,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE + "/",
    }
    with httpx.Client(headers=headers, timeout=300, follow_redirects=True) as client:
        client.get(BASE + "/")  # session cookie

        with open(OUT / "ilce_kodlari.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["il_kodu", "ilce_kodu", "ilce_adi"])
            for plate in range(1, 82):
                found = district_codes(client, plate)
                if not found:
                    raise SystemExit(f"il {plate}: ilçe listesi boş")
                writer.writerows((plate, code, name) for code, name in found)
                time.sleep(DELAY / 4)
        print("ilçe kodları yazıldı", flush=True)

        for name, path in LISTS.items():
            target = OUT / f"{name}_{today}.csv"
            header_written: list[str] | None = None
            total = 0
            with open(target, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for plate in range(1, 82):
                    columns, rows = fetch_list(client, path, plate)
                    if not rows:
                        raise SystemExit(f"{name} il {plate}: tablo boş geldi")
                    if header_written is None:
                        header_written = columns
                        writer.writerow(["sorgu_il_kodu", *columns])
                    elif columns != header_written:
                        raise SystemExit(
                            f"{name} il {plate}: sütunlar değişti {columns}"
                        )
                    writer.writerows([plate, *row] for row in rows)
                    total += len(rows)
                    print(f"  {name} il {plate:02d}: {len(rows)}", flush=True)
                    time.sleep(DELAY)
            print(f"{name}: {total} satır -> {target}", flush=True)


if __name__ == "__main__":
    main()
