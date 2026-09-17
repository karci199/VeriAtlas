"""Download Eurostat regional tables for Türkiye (NUTS2 regions and the country).

Dissemination API, JSON-stat 2.0, no key:
ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/<dataset>?geo=TR10&geo=TR21...
Only the geo dimension is filtered; every other dimension comes whole, so the adapter chooses
the slice and says which.

Files: C:/veri-ham/eurostat/<dataset>.json (overwritten on every run).
"""

from __future__ import annotations

import csv
from pathlib import Path

import httpx

ROOT = Path("C:/veri-ham/eurostat")
BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
DATASETS = (
    "lfst_r_lfu3rt",  # unemployment rate
    "lfst_r_lfe2emprt",  # employment rate
    "lfst_r_lfp2actrt",  # activity rate
    "lfst_r_lfu2ltu",  # long-term unemployment
    "edat_lfse_22",  # NEET rate
    "edat_lfse_16",  # early leavers from education and training
    "edat_lfse_04",  # educational attainment 25-64
    "rd_e_gerdreg",  # R&D expenditure
    "rd_p_persreg",  # R&D personnel
)


def regions() -> list[str]:
    path = Path(__file__).resolve().parents[1] / "src/veriatlas/data/nuts_tr.csv"
    with path.open(encoding="utf-8") as handle:
        return sorted({row["nuts2_id"] for row in csv.DictReader(handle)})


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    params = [("geo", code) for code in [*regions(), "TR"]]
    client = httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=180)
    for dataset in DATASETS:
        response = client.get(BASE + dataset, params=params)
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            raise ValueError(f"Eurostat {dataset}: {body['error']}")
        (ROOT / f"{dataset}.json").write_bytes(response.content)
        print(dataset, len(body.get("value", {})), "hücre", flush=True)


if __name__ == "__main__":
    main()
