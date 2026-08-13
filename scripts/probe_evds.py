"""EVDS3 web servisi - calisan yapilandirmayi dogrular.

BULGU (2026-08):
  taban   : https://evds3.tcmb.gov.tr/igmevdsms-dis
  veri    : /series={KOD}&startDate=GG-AA-YYYY&endDate=GG-AA-YYYY&type=json
  anahtar : HTTP basligi olarak 'key: ...'  (sorgu parametresi CALISMIYOR -> 403)
  kategori: /categories/type=json , /categories/withDatagroups/type=json

Calistirma:  uv run python scripts/probe_evds.py
"""

import sys

import httpx

sys.path.insert(0, "src")

from veri.config import settings  # noqa: E402

BASE = "https://evds3.tcmb.gov.tr/igmevdsms-dis"
HEADERS = {"key": settings.evds_api_key}

TESTLER = [
    ("USD alis (gunluk)", "TP.DK.USD.A", "01-07-2026", "10-07-2026"),
    ("TUFE (aylik)", "TP.FG.J0", "01-01-2025", "01-07-2026"),
]

with httpx.Client(base_url=BASE, headers=HEADERS, timeout=30) as c:
    for ad, kod, bas, son in TESTLER:
        url = f"/series={kod}&startDate={bas}&endDate={son}&type=json"
        r = c.get(url)
        print(f"--- {ad}  [{kod}]  HTTP {r.status_code}")
        if r.status_code != 200:
            print("   ", r.text[:200])
            continue
        j = r.json()
        items = j.get("items", [])
        print(f"    kayit: {j.get('totalCount')}   ilk 3:")
        for it in items[:3]:
            print("     ", {k: v for k, v in it.items() if k != "UNIXTIME"})
        print()

    r = c.get("/categories/type=json")
    print(f"--- kategoriler  HTTP {r.status_code}  adet: {len(r.json())}")
