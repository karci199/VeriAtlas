r"""Download TOBB's public industry tables by province and district (sanayi.org.tr).

The "Sanayi Veri Tabanı" pages call one endpoint, `POST api/svt/invokeService`, with
`{"params": {...}, "lazyLoadingEvent": {...}, "methodName": name}`. Without logging in
these methods answer (province ids from `GET api/ils`, the plate number; -1 = Türkiye):

- `anaFaaliyetlereGoreUreticiDagilimi` (ilId): producers and staff by main activity
  (two-digit sector) — each firm once, under its main activity.
- `ilPersonelAraliklariDagilimByIlId` (ilId): producers by sector and staff-size band.
- `ilceGenelDurumuKodlananUrun` (ilId): products made in the province, with the number
  of capacity reports naming each.
- `ilGenelDurumuIlceDuzeyindeDagilim` (ilId, kod): producers per district, for all
  activities (kod null) and for each two-digit sector. The answer also carries district
  polygons; only the counts (`dist`) are kept.
- the same four with the `yabanciSermaye` prefix: foreign-capital producers only.

Capacity per product and province comes from `fetch_tobb_capacity.py`.

Writes `C:\veri-ham\tobb\kapasite\tablo\<method>\<il>[-<kod>].json`; existing files are
skipped, so the same command resumes. Progress goes to stdout.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

FOLDER = Path("C:/veri-ham/tobb/kapasite")
BASE = "https://sanayi.org.tr/"
PAUSE = 0.5
PAGE = {"first": 0, "rows": 100000, "sortOrder": 1, "sortField": None, "auto": False}
PER_PROVINCE = [
    "anaFaaliyetlereGoreUreticiDagilimi",
    "ilPersonelAraliklariDagilimByIlId",
    "ilceGenelDurumuKodlananUrun",
    "yabanciSermayeGenelDurumuKodlananUrun",
    "yabanciSermayeIlceGenelDurumuKodlananUrun",
]
DISTRICTS = [
    "ilGenelDurumuIlceDuzeyindeDagilim",
    "yabanciSermayeIlGenelDurumuIlceDuzeyindeDagilim",
]


def cached_get(client: httpx.Client, url: str, name: str) -> list[dict]:
    path = FOLDER / name
    if not path.exists():
        r = client.get(BASE + url)
        r.raise_for_status()
        path.write_text(r.text, encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def invoke(client: httpx.Client, method: str, params: dict):
    body = {"params": params, "lazyLoadingEvent": PAGE, "methodName": method}
    for attempt in range(4):
        try:
            r = client.post(BASE + "api/svt/invokeService", json=body)
            if r.status_code in (404, 500):
                return {"error": r.status_code, "detail": r.text[:300]}
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            print(
                f"{time.strftime('%H:%M:%S')} retry {method} {params}: {e}", flush=True
            )
            time.sleep(10 * (attempt + 1))
    return None


def main() -> None:
    with httpx.Client(timeout=120, headers={"User-Agent": "Mozilla/5.0"}) as client:
        provinces = [-1] + sorted(
            p["id"] for p in cached_get(client, "api/ils?size=2000", "iller.json")
        )
        sectors = sorted(
            s["kodu"]
            for s in cached_get(
                client, "apiv2/sektor-kodus?size=2000", "sektor-kodlari.json"
            )
        )
        jobs = [(m, p, None) for m in PER_PROVINCE for p in provinces]
        jobs += [
            (m, p, k)
            for m in DISTRICTS
            for k in [None, *sectors]
            for p in provinces
            if p > 0
        ]
        print(f"{len(jobs)} queries", flush=True)
        new = failed = 0
        for i, (method, province, code) in enumerate(jobs, 1):
            target = (
                FOLDER
                / "tablo"
                / method
                / f"{province}{'' if code is None else '-' + code}.json"
            )
            if not target.exists():
                params = {"ilId": province, "ilceId": -1, "kod": code, "urunKodu": code}
                answer = invoke(client, method, params)
                if answer is None:
                    failed += 1
                else:
                    if isinstance(answer, dict) and "dist" in answer:
                        answer = answer["dist"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(
                        json.dumps(answer, ensure_ascii=False), encoding="utf-8"
                    )
                    new += 1
                time.sleep(PAUSE)
            if i % 50 == 0:
                print(
                    f"{time.strftime('%H:%M:%S')} {i}/{len(jobs)} new {new} failed {failed}",
                    flush=True,
                )
        print(
            f"{time.strftime('%H:%M:%S')} finished: new {new}, failed {failed}",
            flush=True,
        )


if __name__ == "__main__":
    main()
