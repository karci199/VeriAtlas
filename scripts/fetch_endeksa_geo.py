"""Pull neighbourhood boundaries for whole provinces straight from Endeksa's geo API.

The `geo/map` endpoint needs no login: a plain GET with a browser-like Origin header
answers with the same AES-ECB-encrypted JSON string the site decrypts client side
(`encodeResponse` in the page bundle). This fetches level 1 (districts) for a province,
then level 2 (neighbourhoods) per district, decrypts, and writes
raw/endeksa/geo/TR-<plate>.json as `{<CountyId>: <geo/map response>}` — the shape
scripts/export_endeksa_geo.py reads — then runs the export.

Politeness: one request at a time per worker with a short pause; a few workers in
parallel across provinces. Failures on a district are retried, then reported; a province
with any missing district is not written.

Run:  uv run python scripts/fetch_endeksa_geo.py 66 67 ...        # plates
      uv run python scripts/fetch_endeksa_geo.py --missing           # every plate without neighbourhood files
"""

import base64
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "endeksa" / "geo"
API = "https://app.endeksa.com/geo/map"
KEY = b"3ND3KS4B4CK3ND24"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://www.endeksa.com",
    "Referer": "https://www.endeksa.com/",
}
PAUSE = 2.5
WORKERS = 1


def decrypt(text: str) -> dict:
    body = json.loads(text)
    if not isinstance(body, str):
        return body
    decryptor = Cipher(algorithms.AES(KEY), modes.ECB()).decryptor()
    padded = decryptor.update(base64.b64decode(body)) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return json.loads((unpadder.update(padded) + unpadder.finalize()).decode())


def get(client: httpx.Client, **params) -> dict:
    last = None
    for attempt in range(4):
        try:
            r = client.get(API, params=params)
            r.raise_for_status()
            return decrypt(r.text)
        except (httpx.HTTPError, ValueError) as exc:
            last = exc
            time.sleep(30 * (attempt + 1))
    raise RuntimeError(f"{params}: {last}")


def fetch_province(plate: int) -> str:
    out_path = RAW / f"TR-{plate:02d}.json"
    with httpx.Client(headers=HEADERS, timeout=90) as client:
        level1 = get(client, cityId=plate, countryId=1, level=1, subGeometries="true")
        counties = [f["properties"]["CountyId"] for f in level1["features"]]
        out = {}
        for county_id in counties:
            time.sleep(PAUSE)
            out[str(county_id)] = get(
                client,
                cityId=plate,
                countryId=1,
                countyId=county_id,
                level=2,
                subGeometries="true",
            )
    RAW.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    polygons = sum(len(g.get("features") or []) for g in out.values())
    return f"TR-{plate:02d}: {len(out)} counties, {polygons} polygons"


def main(argv: list[str]) -> None:
    if argv == ["--missing"]:
        out = ROOT / "public" / "geo" / "neighbourhoods"
        have = {f.name[:5] for f in out.glob("TR-*.geojson")}
        plates = [p for p in range(1, 82) if f"TR-{p:02d}" not in have]
    else:
        plates = [int(a) for a in argv]
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(fetch_province, p): p for p in plates}
        for future, plate in futures.items():
            try:
                print(future.result(), flush=True)
            except Exception as exc:  # noqa: BLE001 — report and carry on
                print(f"TR-{plate:02d}: FAILED {exc}", flush=True)
                continue
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "export_endeksa_geo.py"),
                    f"TR-{plate:02d}",
                ],
                check=True,
            )


if __name__ == "__main__":
    main(sys.argv[1:])
