"""Download the Banks Association of Türkiye province tables (TBB Veri Sistemi), untouched.

"İller-Bölgeler" on verisistemi.tbb.org.tr: 26 measures (deposits by type, specialised
loans, employees, ATM, POS, merchants, account counts) for every province and region,
annual, 1988 onwards. The page is a front end to one JSON endpoint, found by watching
the page's own requests (2026-09-14):

    POST /api/router   header LANG: tr
      {"route": "blgBolgelerAll"}       area keys → names, plate numbers
      {"route": "blgParametrelerAll"}   measure keys → names, unit
      {"route": "blgDegerler", "paramYillar": [...], "paramBolgeler": [...],
       "paramParametreler": [...]}      the values

The server sends an incomplete certificate chain, so verification is off for this one
public, read-only host.

Output: `$VERIATLAS_RAW/tbb/{areas,measures,values}.json`.

Run:  uv run python scripts/fetch_tbb_provinces.py
"""

from __future__ import annotations

import json
import sys

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

BASE = "https://verisistemi.tbb.org.tr"


def main() -> None:
    out = RAW / "tbb"
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        base_url=BASE, headers={"LANG": "tr"}, verify=False, timeout=600
    ) as client:

        def route(body: dict) -> list:
            r = client.post("/api/router", json=body)
            r.raise_for_status()
            return r.json()

        areas = route({"route": "blgBolgelerAll"})
        measures = route({"route": "blgParametrelerAll"})
        years = route({"route": "blgYillarAll"})
        (out / "areas.json").write_text(json.dumps(areas, ensure_ascii=False), "utf-8")
        (out / "measures.json").write_text(
            json.dumps(measures, ensure_ascii=False), "utf-8"
        )
        print("yil kaydi ornegi:", years[:2])
        year_list = sorted(
            {
                int(
                    next(v for v in y.values() if str(v).isdigit() and len(str(v)) == 4)
                )
                if isinstance(y, dict)
                else int(y)
                for y in years
            }
        )
        area_keys = sorted({a["KEY"] for a in areas})
        measure_keys = sorted({m["PARAMETRE_UK"] for m in measures})
        print(
            len(area_keys),
            "alan",
            len(measure_keys),
            "olcu",
            year_list[:1],
            year_list[-1:],
        )
        values: list[dict] = []
        # One request per year keeps each answer small; the full set is 9 MB at once.
        for year in year_list:
            part = route(
                {
                    "route": "blgDegerler",
                    "paramYillar": [year],
                    "paramBolgeler": area_keys,
                    "paramParametreler": measure_keys,
                }
            )
            values.extend(part)
            print(year, len(part))
        (out / "values.json").write_text(
            json.dumps(values, ensure_ascii=False), "utf-8"
        )
        print("toplam", len(values))


if __name__ == "__main__":
    main()
