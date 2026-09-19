r"""Provincial Health Directorate sites: the hospital list each province publishes.

The Ministry's yearbook counts hospitals per province and stops there — `moh_hospitals`
and its nineteen siblings have no district breakdown, and the district is exactly what a
reader wants ("is there a hospital in this district at all"). The 81 provincial
directorates each run the Ministry's own CMS at `<il>ism.saglik.gov.tr`, and each links
its hospitals one by one, by name.

Two passes, because the two questions are different:

1. **Discovery** — every province's home page is read and the links whose slug carries
   `hastane` are kept, with the text the site prints for them. This is cheap (81 requests)
   and it is what tells us how many hospitals a site claims.
2. **Address** — each hospital's own page is fetched for the address, which is the only
   field that names the district reliably. A name like `Ayaş Şehit Mehmet Çifçi Devlet
   Hastanesi` happens to carry its district, but `Ankara Bilkent Şehir Hastanesi` does not,
   and guessing from the name is how a city hospital ends up in the wrong district.

Both passes are written to CSV and neither is joined to the registry here — the matching
is the adapter's job, and it has to be, because the same hospital can be listed under a
district that was split after it opened.

Run:  uv run python scripts/fetch_ism_hospitals.py          # keşif
      uv run python scripts/fetch_ism_hospitals.py --adres  # sayfa sayfa adres
Out:  C:\veri-ham\ism\hastaneler_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import http.client
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path("C:/veri-ham/ism")
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

#: The CMS's own link shape: `/TR-219382/ankara-bilkent-sehir-hastanesi.html`.
PAGE = re.compile(r'href="(/TR-\d+/([a-z0-9-]+)\.html)"')
#: An address line on a hospital's page; the CMS has no address field, it is prose.
ADDRESS = re.compile(
    r"(?:Adres|ADRES)\s*[:\-]?\s*</?[^>]*>?\s*([^<]{20,200})", re.IGNORECASE
)

DELAY = 0.4

#: Province -> the subdomain. Türkçe karakterler alan adında düşürülüyor.
SLUG = str.maketrans("çğıöşüâî", "cgiosuai")


def host(province: str) -> str:
    slug = province.lower().replace("i̇", "i").translate(SLUG).replace(" ", "")
    return f"https://{slug}ism.saglik.gov.tr"


def get(url: str, tries: int = 4) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": BROWSER})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            if error.code in (404, 403):
                return ""
            if attempt == tries - 1:
                raise
            time.sleep(4 * 2**attempt)
        except (urllib.error.URLError, http.client.HTTPException, OSError):
            if attempt == tries - 1:
                return ""  # a directorate whose site is down is not our error
            time.sleep(4 * 2**attempt)
    return ""


def hospitals(province: str) -> list[dict]:
    """The hospital pages a province's site links from its home page."""
    base = host(province)
    page = get(base + "/")
    found: dict[str, str] = {}
    for path, slug in PAGE.findall(page):
        if "hastane" not in slug:
            continue
        # A "birim" page is the directorate's own department, not a hospital.
        if "birim" in slug or "baskanligi" in slug or "hizmetleri" in slug:
            continue
        found[path] = slug
    return [
        {"province": province, "path": path, "slug": slug, "url": base + path}
        for path, slug in sorted(found.items())
    ]


def address(url: str) -> str:
    page = get(url)
    match = ADDRESS.search(page)
    return " ".join(match.group(1).split()) if match else ""


def main() -> None:
    sys.path.insert(0, str(Path(__file__).parent))
    from fetch_ptt_postal_codes import PROVINCES

    OUT.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.now(tz=dt.UTC).date()
    target = OUT / f"hastaneler_{today:%Y-%m-%d}.csv"

    if "--adres" not in sys.argv:
        rows: list[dict] = []
        for province in PROVINCES:
            found = hospitals(province)
            rows.extend(found)
            print(f"  {province}: {len(found)} hastane sayfası", flush=True)
            time.sleep(DELAY)
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["province", "path", "slug", "url", "address"]
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row | {"address": ""})
        print(f"\n{len(rows):,} hastane sayfası -> {target}")
        return

    with target.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    filled = 0
    for row in rows:
        if row["address"]:
            continue
        row["address"] = address(row["url"])
        filled += bool(row["address"])
        time.sleep(DELAY)
        if filled % 50 == 0 and row["address"]:
            print(f"  {filled} adres", flush=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["province", "path", "slug", "url", "address"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n{filled:,}/{len(rows):,} adres bulundu -> {target}")


if __name__ == "__main__":
    main()
