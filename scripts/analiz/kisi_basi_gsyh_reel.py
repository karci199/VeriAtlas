"""GDP per capita in US dollars, Türkiye and the world, nominal and in constant dollars.

World Bank API (no key), downloaded untouched to `$VERIATLAS_RAW/worldbank/`:

    NY.GDP.PCAP.CD   GDP per capita, current US$        TUR, WLD
    FP.CPI.TOTL      Consumer price index (2010 = 100)  USA

Real series: nominal × CPI(last year) / CPI(year), i.e. constant dollars of the latest
year with a US CPI value. The US CPI is the deflator for a dollar series, whatever country
the dollars were earned in. Türkiye's ratio to the world is unit-free and needs no deflator.

Output: `docs/analiz/kisi-basi-gsyh-reel.csv`.

Run:  uv run python scripts/analiz/kisi_basi_gsyh_reel.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

API = "https://api.worldbank.org/v2/country/{country}/indicator/{code}?format=json&per_page=200"
SERIES = {
    ("TUR", "NY.GDP.PCAP.CD"): "tr_nominal",
    ("WLD", "NY.GDP.PCAP.CD"): "world_nominal",
    ("USA", "FP.CPI.TOTL"): "us_cpi",
}
OUT = Path("docs/analiz/kisi-basi-gsyh-reel.csv")


def main() -> None:
    raw = RAW / "worldbank"
    raw.mkdir(parents=True, exist_ok=True)
    values: dict[str, dict[int, float]] = {}
    with httpx.Client(timeout=120) as client:
        for (country, code), name in SERIES.items():
            response = client.get(API.format(country=country, code=code))
            response.raise_for_status()
            payload = response.json()
            if len(payload) < 2 or payload[0].get("pages", 1) != 1:
                raise ValueError(
                    f"{country} {code}: beklenmeyen cevap / birden cok sayfa"
                )
            (raw / f"{country}_{code}.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            values[name] = {
                int(row["date"]): float(row["value"])
                for row in payload[1]
                if row["value"] is not None
            }
    cpi = values["us_cpi"]
    base = max(cpi)
    years = sorted(set(values["tr_nominal"]) | set(values["world_nominal"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "yil",
                "tr_nominal_usd",
                "dunya_nominal_usd",
                f"tr_reel_usd_{base}",
                f"dunya_reel_usd_{base}",
                "tr_dunya_orani",
                "abd_tufe_2010_100",
            ]
        )
        for year in years:
            tr = values["tr_nominal"].get(year)
            world = values["world_nominal"].get(year)
            factor = cpi[base] / cpi[year] if year in cpi else None
            writer.writerow(
                [
                    year,
                    tr,
                    world,
                    round(tr * factor, 1) if tr and factor else None,
                    round(world * factor, 1) if world and factor else None,
                    round(tr / world, 4) if tr and world else None,
                    cpi.get(year),
                ]
            )
    print("yillar", years[0], "-", years[-1], "; reel baz yili", base, "->", OUT)


if __name__ == "__main__":
    main()
