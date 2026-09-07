"""Pull Endeksa's neighbourhood demography for whole provinces, headlessly.

Endeksa publishes far more per neighbourhood than TUIK does — five-year age bands,
education, marital status, SES and income, area, and where the residents were born —
and the site's own read endpoints need no login. They answer with the AES-ECB blob the
page decrypts client side, exactly like `geo/map` in fetch_endeksa_geo.py.

Three calls make a province: `geo/map` level 1 lists its districts, level 2 lists a
district's neighbourhoods with their DistrictId, and then per neighbourhood
`demography/Values` (257 fields) and `fellowcountryman` (birth province of residents).
Every neighbourhood gets the same two calls, so the result is one consistent table.

Output: raw/endeksa/demography/TR-<plate>-<countyId>.json, one file per district, each
`{DistrictId: {"geo": ..., "demography": ..., "fellow": ...}}`. A district already on
disk is skipped, so a run may be stopped and restarted.

Run:  uv run python scripts/fetch_endeksa_demography.py 16 06
"""

import base64
import json
import os
import sys
import time
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ROOT = Path(__file__).resolve().parents[1]
RAW = Path(os.environ.get("VERIATLAS_RAW", ROOT / "raw")) / "endeksa" / "demography"
CACHE = "https://app.endeksa.com"
KEY = b"3ND3KS4B4CK3ND24"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://www.endeksa.com",
    "Referer": "https://www.endeksa.com/",
}
PAUSE = 1.5


def decrypt(text):
    body = json.loads(text)
    if not isinstance(body, str):
        return body
    decryptor = Cipher(algorithms.AES(KEY), modes.ECB()).decryptor()
    padded = decryptor.update(base64.b64decode(body)) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return json.loads((unpadder.update(padded) + unpadder.finalize()).decode())


def get(client, path, **params):
    last = None
    for attempt in range(4):
        try:
            r = client.get(f"{CACHE}/{path}", params=params)
            r.raise_for_status()
            return decrypt(r.text)
        except (httpx.HTTPError, ValueError) as exc:
            last = exc
            time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"{path} {params}: {last}")


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)
    with (RAW.parent / "demography.log").open("a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


def fetch_province(plate):
    RAW.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers=HEADERS, timeout=90) as client:
        counties = [
            f["properties"]
            for f in get(client, "geo/map", cityId=plate, countryId=1, level=1, subGeometries="true")["features"]
        ]
        log(f"TR-{plate:02d}: {len(counties)} ilce")
        for county in counties:
            out_path = RAW / f"TR-{plate:02d}-{county['CountyId']}.json"
            if out_path.exists():
                continue
            time.sleep(PAUSE)
            hoods = [
                f["properties"]
                for f in get(
                    client,
                    "geo/map",
                    cityId=plate,
                    countryId=1,
                    countyId=county["CountyId"],
                    level=2,
                    subGeometries="true",
                )["features"]
            ]
            out = {}
            for hood in hoods:
                params = dict(
                    countryId=1,
                    cityId=plate,
                    countyId=county["CountyId"],
                    districtId=hood["DistrictId"],
                    level=3,
                )
                time.sleep(PAUSE)
                demography = get(client, "demography/Values", **params)
                time.sleep(PAUSE)
                fellow = get(client, "fellowcountryman", **params)
                out[str(hood["DistrictId"])] = {
                    "geo": hood,
                    "demography": demography.get("Demography"),
                    "fellow": (fellow or {}).get("FellowCountryman"),
                }
            out_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
            log(f"  {county['County']}: {len(out)} mahalle")


if __name__ == "__main__":
    for plate in sys.argv[1:] or ["16", "06"]:
        fetch_province(int(plate))
