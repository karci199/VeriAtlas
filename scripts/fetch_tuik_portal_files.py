r"""Download the files the TÜİK portal catalogue points at.

`scripts/fetch_tuik_portal.py` saves the catalogue; every second row carries a download
link of the form `/api/tr/data/downloads?t=<kind>&p=<token>`. This walks those links and
saves what comes back to `C:\veri-ham\tuik_portal\dosya\<type>\`.

Three things the endpoint does that a naive loop would get wrong:

* It answers 200 with a small HTML page when it is being hit too fast. This is throttling,
  not a dead link: the same token, asked for on its own a minute later, hands over a
  104 KB spreadsheet. A first run at five requests a second got 78 files out of 2.262 and
  called the rest broken. So an HTML answer is retried with a growing wait, and only a
  token that fails every attempt is written to `basarisiz.csv`.
* The real file name is in `Content-Disposition`, mangled (`Giri_imin ana faaliyet...`),
  so the saved name is built from the catalogue title instead and the suffix from the
  content type.
* The connection is dropped every few hundred requests; each download is retried.

Already-saved files are skipped, so a broken run resumes.
"""

from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path

import httpx

OUT = Path("C:/veri-ham/tuik_portal")
FILES = OUT / "dosya"
BASE = "https://veriportali.tuik.gov.tr"
TYPES = ("tablo", "yayin", "rapor", "metaveri", "bulten")
SUFFIX = {
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "text/csv": ".csv",
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Referer": BASE + "/",
}


def safe(title: str) -> str:
    name = re.sub(r"[^0-9A-Za-zÇĞİÖŞÜçğıöşü ._-]+", "", title).strip()
    return re.sub(r"\s+", " ", name)[:110] or "adsiz"


def catalogue() -> list[tuple[str, dict]]:
    rows: list[tuple[str, dict]] = []
    for kind in TYPES:
        folder = OUT / kind
        for path in sorted(folder.glob("page_*.json")):
            for row in json.loads(path.read_text(encoding="utf-8")):
                if "/api/tr/data/downloads" in row.get("url", ""):
                    rows.append((kind, row))
    return rows


def main() -> None:
    entries = catalogue()
    print(f"{len(entries)} indirilebilir kayıt", flush=True)
    failures: list[list[str]] = []
    saved = skipped = 0
    with httpx.Client(
        timeout=120, verify=False, follow_redirects=True, headers=HEADERS
    ) as client:
        client.get(BASE + "/")
        for index, (kind, row) in enumerate(entries, 1):
            folder = FILES / kind
            folder.mkdir(parents=True, exist_ok=True)
            stem = f"{index:05d}_{safe(row['title'])}"
            if list(folder.glob(stem + ".*")):
                skipped += 1
                continue
            answer = None
            suffix = None
            for attempt in range(5):
                try:
                    answer = client.get(BASE + row["url"])
                except httpx.HTTPError as problem:
                    if attempt == 4:
                        failures.append([kind, row["title"], type(problem).__name__])
                        answer = None
                        break
                    time.sleep(5 * (attempt + 1))
                    continue
                header = answer.headers.get("content-type", "").split(";")[0].strip()
                suffix = SUFFIX.get(header)
                if suffix is not None and len(answer.content) >= 2000:
                    break
                suffix = None
                if attempt == 4:
                    failures.append([kind, row["title"], header or "boş"])
                    break
                time.sleep(3 * (attempt + 1))  # throttled, not missing
            if answer is None or suffix is None:
                continue
            (folder / (stem + suffix)).write_bytes(answer.content)
            saved += 1
            if saved % 100 == 0:
                print(f"  {saved} dosya ({index}/{len(entries)})", flush=True)
            time.sleep(1.2)
    if failures:
        with (OUT / "basarisiz.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["tip", "baslik", "sebep"])
            writer.writerows(failures)
    print(f"bitti: {saved} dosya, {skipped} atlandı, {len(failures)} başarısız")


if __name__ == "__main__":
    main()
