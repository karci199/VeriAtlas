"""Download every Microsoft Global Buildings tile for Turkey (266 tiles, ~1.7 GB, release
2026-02-03) into C:/veri-ham/msbuildings. Resumable: existing files are skipped, a failed
download is retried three times, partial files are written under a temporary name.

usage: fetch_msbuildings.py
"""

import csv, io, time
from pathlib import Path
import httpx

OUT = Path("C:/veri-ham/msbuildings")
OUT.mkdir(parents=True, exist_ok=True)
links = list(csv.DictReader(io.StringIO(httpx.get("https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv", timeout=120).text)))
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
                print(f"{i}/{len(tr)} {r['QuadKey']} {out.stat().st_size // 1024} KB ({time.time() - t0:.0f} sn)", flush=True)
                break
            except Exception as exc:  # noqa: BLE001
                print(f"{r['QuadKey']} deneme {attempt + 1} hata: {exc}", flush=True)
                time.sleep(10)
print("bitti", round(time.time() - t0), "sn")
