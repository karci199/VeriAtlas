"""Download the refreshed Microsoft Global Buildings tiles for Turkey (266 tiles, ~1.7 GB, the
2026-07-24 hosting, refreshed 2026-08-13) into C:/veri-ham/msbuildings_2026_08.

The hosting moved (README, 2026-07-24): dataset-links.csv now lives on bfppub.blob.core.windows.net
and the tile Urls point at bfppub.z5.web.core.windows.net. The old release (2026-02-03) stays in
C:/veri-ham/msbuildings for comparison. Resumable: an existing, non-empty file is skipped, a failed
download is retried three times, partial files are written under a temporary name.

usage: fetch_msbuildings_2026_08.py
"""

import csv
import io
import time
from pathlib import Path

import httpx

OUT = Path("C:/veri-ham/msbuildings_2026_08")
OUT.mkdir(parents=True, exist_ok=True)
LINKS = "https://bfppub.blob.core.windows.net/%24web/2026-07-24/dataset-links.csv"
links = list(csv.DictReader(io.StringIO(httpx.get(LINKS, timeout=180, follow_redirects=True).text)))
tr = [r for r in links if r["Location"] == "Turkey"]
(OUT / "dataset-links-turkey.csv").write_text("\n".join(",".join(r.values()) for r in tr), encoding="utf-8")
print("karo", len(tr), flush=True)
t0 = time.time()
with httpx.Client(timeout=600, follow_redirects=True) as cli:
    for i, r in enumerate(tr, 1):
        out = OUT / f"{r['QuadKey']}.csv.gz"
        if out.exists() and out.stat().st_size > 0:
            continue
        for attempt in range(3):
            try:
                tmp = out.with_suffix(".part")
                with cli.stream("GET", r["Url"]) as resp:
                    resp.raise_for_status()
                    with open(tmp, "wb") as fh:
                        for chunk in resp.iter_bytes(1 << 20):
                            fh.write(chunk)
                tmp.replace(out)
                break
            except Exception as e:  # noqa: BLE001
                print("  hata", r["QuadKey"], attempt + 1, e, flush=True)
                time.sleep(5)
        print(f"{i}/{len(tr)} {r['QuadKey']} {r['Size']} ({time.time() - t0:.0f} sn)", flush=True)
print("bitti", flush=True)
