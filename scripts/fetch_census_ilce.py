"""Fetch every census village-level table of chosen districts, all variables, 1985-2000.

The country-wide queue is days of work and the server keeps dropping sessions; a single
district is a few dozen reports. Years that fail to open a session are retried.

Run:  python scripts/fetch_census_ilce.py Bursa:İznik Ankara:Kalecik
"""

from __future__ import annotations

import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import fetch_census_districts as census

YEARS = [1985, 1990, 2000]
VARIABLES = [
    "Beşerli Yaş Grubu",
    "0-14,15-64,65+",
    "Onarlı Yaş Grubu",
    "Eğitim Durumu",
    "Okuryazarlık",
    "Medeni Durum",
    "Cinsiyet",
    "Canlı Doğan ve Yaşayan Çocuk",
    "Canlı Doğan Çocuk Sayısına Göre Kadın Nüfus",
]

if __name__ == "__main__":
    only = [tuple(a.split(":", 1)) for a in sys.argv[1:]]
    for year in YEARS:
        for attempt in range(1, 9):
            try:
                census.fetch_villages(year, VARIABLES, only)
                break
            except Exception as error:  # noqa: BLE001
                census.log(f"   ADIM HATASI {year} ({attempt}/8): {error}")
                time.sleep(min(600, 60 * attempt))
