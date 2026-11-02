"""Candidate and elected-candidate profiles of the local elections (Mahalli İdareler).

The same TÜİK application as `fetch_secim_profil.py`, behind `menuyerel.zul`. Local
profile pages exist for the 2009, 2014, 2019 and 2024 elections and for four offices
(provincial council, metropolitan mayor, mayor, municipal council). The candidate page
crosses two of Yaş grubu / Eğitim durumu / Medeni durum / Siyasi parti; one whole-country
report per office, year and pair, answered at the province level for all provinces at once.

Output: `<data root>/secim/profil_yerel/<page>/<year>__<office>__<var1>__<var2>.html`

Run:  uv run python scripts/fetch_yerel_profil.py aday
      uv run python scripts/fetch_yerel_profil.py kazanan
"""

from __future__ import annotations

import os
import pathlib
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from fetch_secim_profil import slug
from zk_client import ZK

HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
OUT = HAM / "secim" / "profil_yerel"

PAGES = {"aday": "yereladay.zul", "kazanan": "yereladaykazanan.zul"}
OFFICES = [
    "Belediye başkanlığı",
    "Belediye meclisi üyeliği",
    "Büyükşehir belediye başkanlığı",
    "İl genel meclisi üyeliği",
]
YEARS = ["2024 seçimi", "2019 seçimi", "2014 seçimi", "2009 seçimi"]
VARS = ["Yaş grubu", "Eğitim durumu", "Medeni durum", "Siyasi parti / Bağımsız"]
SECOND = "2'nci değişken istiyor musunuz?"
ALL_PROVINCES = "&lt;&lt; Tüm iller &gt;&gt;"


def pairs() -> list[tuple[str, str]]:
    return [(a, b) for i, a in enumerate(VARS) for b in VARS[i + 1 :]]


def dest(page: str, year: str, office: str, pair: tuple[str, str]) -> pathlib.Path:
    name = f"{slug(year)}__{slug(office)}__{slug(pair[0])}__{slug(pair[1])}.html"
    return OUT / page / name


def fetch_one(page: str, year: str, office: str, pair: tuple[str, str]) -> None:
    z = ZK(PAGES[page], timeout=300)
    z.pick("Mahalli İdareler Seçimi:", office, exact=True)
    z.check(year)
    z.check(pair[0])
    z.check(SECOND)
    z.pick("2 inci değişkenler:", pair[1], exact=True)
    z.check("İl")
    z.pick("İl Seçimi:", ALL_PROVINCES, exact=True)
    z.click("Raporu Oluştur")
    if not z.redirect:
        raise RuntimeError("no report url")
    data = urllib.request.urlopen(
        z.redirect.replace("http://", "https://"), timeout=300
    ).read()
    if len(data) < 2000:
        raise RuntimeError(f"small report {len(data)}")
    path = dest(page, year, office, pair)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main(page: str, only: str | None = None) -> None:
    for year in YEARS:
        for office in OFFICES:
            for pair in pairs():
                if only and only != "all" and slug(only) not in slug(year + office):
                    continue
                if dest(page, year, office, pair).exists():
                    continue
                try:
                    fetch_one(page, year, office, pair)
                    print("ok", year, office, pair, flush=True)
                except Exception as error:  # noqa: BLE001 - log and carry on
                    print("HATA", year, office, pair, str(error)[:80], flush=True)
                time.sleep(1.0)


if __name__ == "__main__":
    main(
        sys.argv[1] if len(sys.argv) > 1 else "aday",
        sys.argv[2] if len(sys.argv) > 2 else None,
    )
