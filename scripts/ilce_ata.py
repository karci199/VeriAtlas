"""Assign a district (ilçe) to point data by point-in-polygon.

Chain and branch scrapes carry coordinates but rarely a clean district field: an
address that says "Forum Ankara" or "212 Power Outlet" names a mall, not a place in
the area registry. Matching on text quietly loses those rows. The boundaries we
already publish for the map answer the question directly, so the same file serves
both the map and the join.

Rings come from public/geo/districts/TR-*.geojson, keyed to our own area ids. A point
outside every district is reported, never silently dropped: a store on the coastline
or a mistyped coordinate is a finding, not a blank.

Use:
    from scripts.ilce_ata import IlceAtayici
    atayici = IlceAtayici()
    atayici.ata(41.0082, 28.9784)   -> ("TR-34-019", "İstanbul", "Fatih")
"""

from __future__ import annotations

import json
import pathlib

GEO = pathlib.Path(__file__).resolve().parents[1] / "public" / "geo"
DISTRICTS = GEO / "districts"
KAPSAM = GEO / "kapsam.json"


def _halkalar(geometry: dict) -> list[list[tuple[float, float]]]:
    """Polygon and MultiPolygon alike, return the outer rings."""
    tur = geometry["type"]
    coords = geometry["coordinates"]
    if tur == "Polygon":
        return [[(float(x), float(y)) for x, y in coords[0]]]
    if tur == "MultiPolygon":
        return [[(float(x), float(y)) for x, y in p[0]] for p in coords]
    raise ValueError(f"beklenmeyen geometri: {tur}")


def _icinde(x: float, y: float, halka: list[tuple[float, float]]) -> bool:
    """Ray casting; sınırdaki nokta içeride sayılır."""
    icinde = False
    n = len(halka)
    j = n - 1
    for i in range(n):
        xi, yi = halka[i]
        xj, yj = halka[j]
        if (yi > y) != (yj > y):
            kesisim = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x <= kesisim:
                icinde = not icinde
        j = i
    return icinde


class IlceAtayici:
    def __init__(self) -> None:
        kapsam = json.loads(KAPSAM.read_text(encoding="utf-8"))
        self.il_adi = {k: v["ad"] for k, v in kapsam.items() if v["duzey"] == "il"}
        self.ilceler: list[dict] = []
        for dosya in sorted(DISTRICTS.glob("TR-*.geojson")):
            veri = json.loads(dosya.read_text(encoding="utf-8"))
            for ft in veri["features"]:
                p = ft["properties"]
                halkalar = _halkalar(ft["geometry"])
                xs = [x for h in halkalar for x, _ in h]
                ys = [y for h in halkalar for _, y in h]
                self.ilceler.append(
                    {
                        "area_id": p["area_id"],
                        "ad": p["name_tr"],
                        "il_id": p["parent_id"],
                        "il": self.il_adi.get(p["parent_id"], p["parent_id"]),
                        "bbox": (min(xs), min(ys), max(xs), max(ys)),
                        "halkalar": halkalar,
                    }
                )

    def ata(self, lat: float | str | None, lng: float | str | None):
        """(area_id, il, ilçe) ya da bulunamazsa (None, None, None)."""
        try:
            y = float(str(lat).replace(",", "."))
            x = float(str(lng).replace(",", "."))
        except (TypeError, ValueError):
            return (None, None, None)
        if not (25.0 <= x <= 45.5 and 35.5 <= y <= 42.5):
            return (None, None, None)  # Türkiye kutusunun dışı
        for d in self.ilceler:
            x0, y0, x1, y1 = d["bbox"]
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                continue
            if any(_icinde(x, y, h) for h in d["halkalar"]):
                return (d["area_id"], d["il"], d["ad"])
        return (None, None, None)


if __name__ == "__main__":
    a = IlceAtayici()
    for lat, lng, beklenen in [
        (41.0082, 28.9784, "Fatih"),
        (40.4295, 29.7194, "İznik"),
        (39.9208, 32.8541, "Çankaya"),
        (36.8969, 30.7133, "Muratpaşa"),
    ]:
        print(lat, lng, "->", a.ata(lat, lng), "| beklenen:", beklenen)
    print("ilçe sayısı:", len(a.ilceler))
