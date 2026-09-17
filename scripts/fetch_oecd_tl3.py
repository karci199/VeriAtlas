r"""Download OECD regional statistics at TL3 (= the 81 provinces) for Türkiye.

sdmx.oecd.org answers SDMX 2.1 REST without a key. A data URL is
`data/<agency>,<dataflow>,<version>/<key>`, where the key names one field per dimension of
the dataflow's structure, in order, and an empty field means "all". The first three
dimensions of every regional dataflow are FREQ, TERRITORIAL_LEVEL and REF_AREA, so the key
here is `A.TL3.<the 81 province codes>` followed by an empty field per remaining dimension
— a key of the wrong width comes back 403, not 400.

The province codes are NUTS-3 (TR100 Istanbul, TR211 Tekirdag), the same codes as
`src/veriatlas/data/nuts_tr.csv`, so no name matching is needed.

OECD throttles hard: a burst of requests earns 429 for minutes afterwards, so this asks for
one dataflow at a time, waits between them and backs off when refused. Each answer is saved
whole to `C:\veri-ham\oecd_tl3\<dataflow>.csv` and existing files are not fetched again.

Projections are not fetched (user decision, 2026-09-17): the repository keeps measurements.

Run:  uv run python scripts/fetch_oecd_tl3.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

API = "https://sdmx.oecd.org/public/rest/"
OUT = Path("C:/veri-ham/oecd_tl3")
AGENCY = "OECD.CFE.EDS"
PAUSE = 30
STRUCTURE = {"Accept": "application/vnd.sdmx.structure+json;version=1.0"}

#: dataflow -> version. Measurements only; DF_CLIM_PROJ and the other projection flows are
#: left out on purpose.
FLOWS = {
    "DSD_REG_CLIM@DF_AIR_TEMP": "2.5",
    "DSD_REG_CLIM@DF_PRECIPITATION": "2.4",
    "DSD_REG_CLIM@DF_DEGREE_DAYS": "2.4",
    "DSD_REG_CLIM@DF_GHG": "2.4",
    "DSD_REG_DEMO@DF_LIFE_EXP": "2.4",
    "DSD_REG_ECO@DF_TRAD": "2.4",
    "DSD_REG_DEMO@DF_MIGR_FLOW": "2.4",
    # Not yet known to hold TL3 rows for Türkiye — the answer settles it.
    "DSD_REG_ENE@DF_ENE_CONSUMPTION": "2.5",
    "DSD_REG_ENE@DF_PROD_ELEC": "2.5",
    "DSD_REG_ENV@DF_AIR_POLLUT": "3.0",
    "DSD_REG_ENV@DF_WASTE": "3.0",
    "DSD_REG_HEALTH@DF_CARE": "2.5",
    "DSD_REG_HEALTH@DF_STATUS": "2.5",
    "DSD_REG_HEALTH@DF_RISK": "2.5",
    "DSD_REG_LAB@DF_RATES": "2.4",
    "DSD_REG_LAB@DF_LEVELS": "2.4",
    "DSD_REG_SOC@DF_BROADBAND": "2.4",
    "DSD_REG_SOC@DF_HOUSING": "2.4",
    "DSD_REG_SOC@DF_SAFETY": "2.4",
    "DSD_REG_SOC@DF_VEH": "2.4",
    "DSD_REG_SOC@DF_VOTER": "2.4",
    "DSD_REG_TOUR@DF_TOUR_CAP": "2.4",
    "DSD_REG_TOUR@DF_TOUR_NIGHT": "2.4",
    "DSD_REG_INNOV@DF_PAT": "2.6",
    "DSD_REG_INNOV@DF_RD_GERD": "2.6",
    "DSD_REG_MIGRANT@DF_MIGR_STOCK": "2.4",
}

client = httpx.Client(
    timeout=300, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}
)


def get(url: str, **kwargs) -> httpx.Response:
    """A refused request is waited out, not retried at once."""
    for attempt in range(5):
        response = client.get(url, **kwargs)
        if response.status_code != 429:
            return response
        wait = 60 * (attempt + 1)
        print(f"   429, {wait} sn bekleniyor", flush=True)
        time.sleep(wait)
    return response


def provinces() -> list[str]:
    """The 81 TL3 codes for Türkiye, from the regional codelist: five characters, minus
    TRZZZ, the extra-regio code that belongs to no province."""
    path = OUT / "cl_regional_tr.json"
    if path.exists():
        codes = json.loads(path.read_text(encoding="utf-8"))
    else:
        body = get(API + "codelist/OECD/CL_REGIONAL/2.0", headers=STRUCTURE).json()
        codes = [
            {"id": c["id"], "name": c["name"]}
            for c in body["data"]["codelists"][0]["codes"]
            if c["id"].startswith("TR")
        ]
        path.write_text(json.dumps(codes, ensure_ascii=False), encoding="utf-8")
    return [c["id"] for c in codes if len(c["id"]) == 5 and c["id"] != "TRZZZ"]


def width(dataflow: str) -> int:
    """How many dimensions the dataflow's structure has, so the key can be built."""
    dsd = dataflow.split("@")[0]
    path = OUT / f"dims_{dsd}.txt"
    if path.exists():
        return int(path.read_text())
    body = get(
        API + f"datastructure/{AGENCY}/{dsd}/latest",
        params={"references": "none"},
        headers=STRUCTURE,
    ).json()
    dimensions = body["data"]["dataStructures"][0]["dataStructureComponents"]
    count = len(dimensions["dimensionList"]["dimensions"])
    path.write_text(str(count))
    time.sleep(5)
    return count


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    areas = "+".join(provinces())
    print(f"{len(provinces())} il kodu", flush=True)
    for dataflow, version in FLOWS.items():
        target = OUT / f"{dataflow.replace('@', '_')}.csv"
        if target.exists():
            print(f"{dataflow:34s} var", flush=True)
            continue
        key = ".".join(["A", "TL3", areas] + [""] * (width(dataflow) - 3))
        response = get(
            f"{API}data/{AGENCY},{dataflow},{version}/{key}",
            params={"format": "csvfile"},
        )
        if response.status_code == 404 or (
            response.status_code == 200 and not response.text.strip()
        ):
            (OUT / f"{dataflow.replace('@', '_')}.yok").write_text(
                str(response.status_code)
            )
            print(f"{dataflow:34s} TL3 verisi yok ({response.status_code})", flush=True)
        elif response.status_code != 200:
            print(
                f"{dataflow:34s} HATA {response.status_code}",
                file=sys.stderr,
                flush=True,
            )
        else:
            target.write_bytes(response.content)
            lines = response.text.count("\n")
            print(
                f"{dataflow:34s} {lines:8d} satır  {len(response.content) / 1e6:.1f} MB",
                flush=True,
            )
        time.sleep(PAUSE)


if __name__ == "__main__":
    main()
