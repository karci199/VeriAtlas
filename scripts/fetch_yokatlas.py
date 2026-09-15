"""Download the YÖK Atlas programme guide and placement nets (public API, no login).

Two POST requests with an empty filter return every row: `raw/yokatlas/kilavuz_<year>.json`
and `raw/yokatlas/netler.json`.
"""

import json
import sys

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

BASE = "https://yokatlas.yok.gov.tr/api"


def main() -> None:
    out = RAW / "yokatlas"
    out.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=300
    )
    guide = client.post(BASE + "/tercih-kilavuz/search", json={}).json()
    (out / f"kilavuz_{guide['yil']}.json").write_text(
        json.dumps(guide, ensure_ascii=False), encoding="utf-8"
    )
    nets = client.post(BASE + "/netler/search", json={}).json()
    (out / "netler.json").write_text(
        json.dumps(nets, ensure_ascii=False), encoding="utf-8"
    )
    print("kılavuz", guide["totalElements"], "netler", nets["totalElements"])


if __name__ == "__main__":
    main()
