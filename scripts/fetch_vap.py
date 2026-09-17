r"""Download MKK VAP (Veri Analiz Platformu) portfolio value by province, December 2005-2025.

vap.org.tr embeds a MicroStrategy dossier ("İl") from mobil.vap.org.tr. Its REST API logs in as
the public user; a dossier instance created with a month filter on the "Ay" selector returns the
map visualisation's rows: every province and its portfolio value (million TL). The investor count
sits behind an object-replacement selector that the instance filter does not accept, and the
count visualisation holds the top ten provinces only: counts are not taken.

Writes `C:\veri-ham\vap\portfolio-<year>.json`; existing files are kept.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

API = "https://mobil.vap.org.tr/MicroStrategyLibrary/api"
PROJECT = "0DDECAD844A1A9163420D5A4A08847F1"
DOSSIER = "DA8C76BD408C384CF0AB16AF927E6205"
CHAPTER = "K36"
MONTH_SELECTOR = "WCCEC3F6AA9C44BBCABE69A122E0247A4"
MONTH_ATTRIBUTE = "531030FD40245ECAEBAEE3BCB4A52C26"
MAP = "K42CBD7D142E6F61F2F08E38A96946815"
OUT = Path("C:/veri-ham/vap")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=120,
        verify=False,
    )
    login = client.post(
        API + "/auth/login", json={"username": "public", "password": "", "loginMode": 1}
    )
    headers = {
        "X-MSTR-AuthToken": login.headers["x-mstr-authtoken"],
        "X-MSTR-ProjectID": PROJECT,
    }
    for year in range(2005, 2026):
        target = OUT / f"portfolio-{year}.json"
        if target.exists():
            continue
        body = {
            "filters": [
                {
                    "key": MONTH_SELECTOR,
                    "selections": [{"id": f"h{year}12;{MONTH_ATTRIBUTE}"}],
                }
            ]
        }
        instance = (
            client.post(
                API + f"/dossiers/{DOSSIER}/instances", headers=headers, json=body
            )
            .raise_for_status()
            .json()["mid"]
        )
        answer = client.get(
            API
            + f"/v2/dossiers/{DOSSIER}/instances/{instance}/chapters/{CHAPTER}"
            + f"/visualizations/{MAP}",
            headers=headers,
            params={"limit": 200},
        ).raise_for_status()
        target.write_text(
            json.dumps(answer.json(), ensure_ascii=False), encoding="utf-8"
        )
        print(year, flush=True)


if __name__ == "__main__":
    main()
