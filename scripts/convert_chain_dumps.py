r"""Turn store-finder dumps that are not yet CSV into the `lat,lng[,area_id]` files that
`adapters/chain_stores.py` reads.

Two shared shop platforms answer the same way for every chain built on them:

*   **Akinon** — `https://<host>/address/stores/`, paged JSON (`count`, `next`, `results`).
    Each store names its `township` (district) and that township's `city` and `country`.
    Atasay lists shops abroad under the same endpoint; they are dropped by country code.
*   **Ticimax** — `https://<host>/api/Store/GetStoriesLite?CountryID=-1&PageSize=1000`,
    one JSON (`magazalar`), with `il` and `ilce` names. Coordinates may use a decimal comma.

A store with no coordinate keeps the district its own record names, resolved against the
registry (`areas.resolve_district`), so a gap in the map pin does not drop it silently.

Three dumps are single files saved earlier: Simit Sarayı and HD İskender JSON, and
Köfteci Yusuf's branch page, which answers a bot check in an automated browser and was
saved by hand from an ordinary one on 2026-09-23 (308 branches, 43 provinces, as the page
itself states). Its cards read name, province, opening hours, …, phone, and a Google
Maps link whose `destination=` carries the point.

Run:  uv run python scripts/convert_chain_dumps.py
"""

from __future__ import annotations

import csv
import html
import json
import re
import sys

sys.path.insert(0, "src")

from veriatlas.areas import resolve_district
from veriatlas.config import RAW

PERAKENDE = RAW / "perakende"
AKINON = ["atasay", "flormar", "mudo", "intersport", "chakra"]
TICIMAX = ["englishhome", "avva"]


def _num(value) -> str:
    text = str(value or "").strip().replace(",", ".")
    try:
        return text if float(text) else ""
    except ValueError:
        return ""


def _title(name: str) -> str:
    """Turkish-aware title case; `str.title` turns 'İZMİR' into 'İzmi̇r'."""
    words = name.strip().replace("I", "ı").replace("İ", "i").lower().split()
    return " ".join(
        w[:1].replace("i", "İ").replace("ı", "I").upper() + w[1:] for w in words
    )


def _write(path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, ["name", "lat", "lng", "area_id"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:28} {len(rows):5} satır")


def _row(name: str, lat, lng, province: str, district: str) -> dict:
    lat, lng = _num(lat), _num(lng)
    area = "" if lat and lng else resolve_district(_title(province), _title(district))
    return {"name": name, "lat": lat, "lng": lng, "area_id": area}


def akinon(brand: str) -> None:
    stores = json.loads((PERAKENDE / "akinon" / f"{brand}.json").read_text("utf-8"))
    rows = []
    for s in stores:
        town = s.get("township") or {}
        city = town.get("city") or {}
        if (city.get("country") or {}).get("code", "").lower() != "tr":
            continue
        rows.append(
            _row(s["name"], s["latitude"], s["longitude"], city["name"], town["name"])
        )
    _write(PERAKENDE / "akinon" / f"{brand}.csv", rows)


def ticimax(brand: str) -> None:
    doc = json.loads((PERAKENDE / "ticimax" / f"{brand}.json").read_text("utf-8"))
    rows = [
        _row(s["tanim"], s["latitude"], s["longitude"], s["il"], s["ilce"])
        for s in doc["magazalar"]
        if (s.get("ulke") or "Türkiye").lower() in {"türkiye", "turkiye"}
    ]
    _write(PERAKENDE / "ticimax" / f"{brand}.csv", rows)


def simple(name: str, key: str, lat: str, lng: str, label: str) -> None:
    doc = json.loads((PERAKENDE / f"{name}.json").read_text("utf-8"))
    rows = [
        {"name": s[label], "lat": _num(s[lat]), "lng": _num(s[lng]), "area_id": ""}
        for s in doc[key]
    ]
    _write(PERAKENDE / f"{name}.csv", rows)


def kofteci_yusuf() -> None:
    folder = PERAKENDE / "kofteciyusuf"
    text = (folder / "subelerimiz_2026-09-23.html").read_text("utf-8")
    text = re.sub(r"<(script|style)\b.*?</\1>", "", text, flags=re.DOTALL)
    text = re.sub(
        r"<a[^>]*destination=(-?[\d.]+),(-?[\d.]+)[^>]*>", r"<x>@@\1,\2@@<x>", text
    )
    tokens = [html.unescape(t).strip() for t in re.split(r"<[^>]*>", text)]
    tokens = [t for t in tokens if t]
    hours = re.compile(r"(7/24 Açık|\d\d:\d\d ?- ?\d\d:\d\d|Kapalı.*|Açık.*)")
    rows = []
    for i, token in enumerate(tokens):
        if not token.startswith("@@"):
            continue
        h = max(k for k in range(i - 8, i) if hours.fullmatch(tokens[k]))
        lat, lng = token.strip("@").split(",")
        rows.append({"name": tokens[h - 2], "lat": lat, "lng": lng, "area_id": ""})
    if len(rows) != 308:
        raise SystemExit(f"Köfteci Yusuf: {len(rows)} şube, sayfa 308 diyor")
    _write(folder / "kofteciyusuf.csv", rows)


def teknosa() -> None:
    """Teknosa's finder (`/magaza-bul`) sits behind Cloudflare and its robots.txt answers
    403, so it was never fetched; the page was saved by hand from an ordinary browser on
    2026-09-23. It says "136 mağaza bulundu" and holds 136 cards: name, address, phone,
    hours, then a Google Maps link with the point."""
    folder = PERAKENDE / "teknosa"
    text = (folder / "magaza_bul_2026-09-23.htm").read_text("utf-8", errors="replace")
    text = re.sub(r"<(script|style)\b.*?</\1>", "", text, flags=re.DOTALL)
    text = re.sub(r'<a[^>]*destination=([^"&]+)[^>]*>', r"<x>@@\1@@<x>", text)
    tokens = [html.unescape(t).strip() for t in re.split(r"<[^>]*>", text)]
    tokens = [t for t in tokens if t]
    rows = []
    for i, token in enumerate(tokens):
        if token.startswith("@@"):
            lat, lng = token.strip("@").split(",")
            rows.append({"name": tokens[i - 4], "lat": lat, "lng": lng, "area_id": ""})
    if len(rows) != 136:
        raise SystemExit(f"Teknosa: {len(rows)} mağaza, sayfa 136 diyor")
    _write(folder / "teknosa.csv", rows)


def main() -> None:
    for brand in AKINON:
        akinon(brand)
    for brand in TICIMAX:
        ticimax(brand)
    simple("simitsarayi_magaza", "magazalar", "latitude", "longitude", "name")
    simple("hdiskender_restoran", "restoranlar", "lat", "lng", "ad")
    kofteci_yusuf()
    teknosa()


if __name__ == "__main__":
    main()
