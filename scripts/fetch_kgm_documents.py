"""Download the statistical KGM documents found by `crawl_kgm_site.py`, untouched.

Takes `$VERIATLAS_RAW/kgm/stat_documents.csv` (the statistics, traffic, publication and
annual-report pages of the site inventory) and keeps the documents that carry numbers:
accident summaries, traffic and transport yearbooks, road and bridge inventories,
maintenance costs, budget, distances, surveys, activity reports. Volume maps and technical
manuals are left out.

Output: `$VERIATLAS_RAW/kgm/pdf/<page>/<file>`; files already on disk are skipped.

Run:  uv run python scripts/fetch_kgm_documents.py
"""

from __future__ import annotations

import csv
import re
import sys
import time
import warnings
from urllib.parse import unquote, urlparse

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

KEEP = re.compile(
    r"TrafikKazalariOzeti|TrafikveUlasimBilgileri|Yayinlar/(Yayinlar|Anket|BesYillik)"
    r"|Istatistikler/|Uzakliklar|FaaliyetRaporu|InsanKaynaklari"
)


def main() -> None:
    warnings.filterwarnings("ignore")
    base = RAW / "kgm"
    with (base / "stat_documents.csv").open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if KEEP.search(r["page"] or "")]
    print(len(rows), "belge")
    with httpx.Client(
        timeout=300,
        verify=False,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    ) as client:
        for row in rows:
            name = unquote(urlparse(row["url"]).path.rsplit("/", 1)[-1])
            target = base / "pdf" / row["page"].replace("/", "_") / name
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            response = client.get(row["url"])
            if response.status_code != 200:
                print("HATA", response.status_code, row["url"])
                continue
            target.write_bytes(response.content)
            print(
                len(response.content) // 1024,
                "KB",
                target.relative_to(base),
                flush=True,
            )
            time.sleep(0.5)


if __name__ == "__main__":
    main()
