r"""A101's store list, swept out of a "nearest stores" endpoint with a quadtree.

A101 is the one large chain with no list page at all: `/magazalarimiz` is 404 and
`/en-yakin-magazalar` draws whatever the *browser's* location is near. Writing
`?lat=&lng=` into that URL does nothing — the page keeps the parameter in its own
router state and still asks the browser. That is where an earlier session stopped.

The page itself does not hold the data either. It calls a separate host:

    GET rio.a101.com.tr/dbmk89vnr/CALL/StoreContentManager/nearestStores/default
        ?__culture=tr-TR&__platform=web&__isbase64=true
        &data=<base64 of {"geoHash": "<9 char geohash>"}>

So the location is an argument after all, just encoded twice: geohashed, then base64'd.
The host sits outside Cloudflare — plain urllib works, no browser, no location spoofing.

The answer is always the **nearest 20 stores**, with no radius limit: asked from an empty
stretch of Kırıkkale it still returns 20, the farthest 49 km away. That shapes the sweep.
A query at point P has only proven the ground within `r`, the distance of its 20th store;
beyond `r` there may be stores it never mentioned. So each cell is asked at its centre and
kept only if `r` covers the cell's half-diagonal; otherwise it is split into four and the
children are asked. Dense cities recurse, empty steppe does not.

This is why the sweep is not a fixed grid of district centres: a fixed grid cannot tell
you whether it missed anything, and A101's density spans three orders of magnitude between
Kadıköy and Tunceli. The quadtree reports its own coverage.

Resume is built in (`--devam`), per the rate-limit lesson in docs/zincir-magazalar.md:
every answered cell is appended to a log, and a resumed run skips them.

Run:  uv run python scripts/fetch_a101.py [--devam] [--gecikme 0.3]
Out:  C:\veri-ham\a101\magazalar_<YYYY-MM-DD>.csv
      C:\veri-ham\a101\hucreler.jsonl   (the sweep log, for --devam)
"""

from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, "src")

from veriatlas.config import RAW

OUT = RAW / "a101"
ENDPOINT = (
    "https://rio.a101.com.tr/dbmk89vnr/CALL/StoreContentManager/nearestStores/default"
)
UA = "ClaudeBot/1.0 (+https://claude.com/claudebot)"
#: Turkey's bounding box, the same one the chain adapters use to strip foreign branches.
TURKEY = (35.7, 42.2, 25.5, 45.1)  # lat_min, lat_max, lon_min, lon_max
#: Top-level cell, in degrees of latitude. ~22 km; everything below it is discovered.
START_STEP = 0.2
#: A cell smaller than this is not split further. 0.2 / 2**7 ≈ 170 m; below that the
#: 20-store answer is saturated (20 stores inside 170 m does not happen in Turkey) and
#: recursion would only be a way of hammering the endpoint.
MIN_STEP = START_STEP / 2**7
#: The endpoint's page size. A shorter answer means the neighbourhood was exhausted.
PAGE = 20
COLUMNS = ["id", "ad", "il", "ilce", "plaka", "adres", "enlem", "boylam"]


def geohash(lat: float, lon: float, precision: int = 9) -> str:
    """Geohash the way the site's own client does it: interleaved bits, base32."""
    digits = "0123456789bcdefghjkmnpqrstuvwxyz"
    lat_range, lon_range = [-90.0, 90.0], [-180.0, 180.0]
    bit, char, even, out = 0, 0, True, ""
    while len(out) < precision:
        if even:
            mid = sum(lon_range) / 2
            if lon > mid:
                char, lon_range[0] = char * 2 + 1, mid
            else:
                char, lon_range[1] = char * 2, mid
        else:
            mid = sum(lat_range) / 2
            if lat > mid:
                char, lat_range[0] = char * 2 + 1, mid
            else:
                char, lat_range[1] = char * 2, mid
        even = not even
        if bit < 4:
            bit += 1
        else:
            out, bit, char = out + digits[char], 0, 0
    return out


def ask(lat: float, lon: float, tries: int = 5) -> list[dict]:
    data = base64.b64encode(
        json.dumps({"geoHash": geohash(lat, lon)}).encode()
    ).decode()
    url = (
        f"{ENDPOINT}?__culture=tr-TR&__platform=web"
        f"&data={urllib.parse.quote(data)}&__isbase64=true"
    )
    for attempt in range(tries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=40) as answer:
                return json.load(answer).get("stores", [])
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as problem:
            # A rate limit is not "no stores here" — a swallowed error would quietly leave
            # a hole in the sweep that nothing downstream could see.
            if attempt == tries - 1:
                raise SystemExit(f"{lat:.4f},{lon:.4f} okunamadı: {problem}") from None
            time.sleep(5 * 2**attempt)
    return []


def half_diagonal_m(lat: float, step: float) -> float:
    """Metres from a cell's centre to its corner."""
    dy = step * 111_320 / 2
    dx = step * 111_320 * math.cos(math.radians(lat)) / 2
    return math.hypot(dx, dy)


def initial_queue() -> list[tuple[float, float, float]]:
    lat_min, lat_max, lon_min, lon_max = TURKEY
    rows = int((lat_max - lat_min) / START_STEP) + 1
    cols = int((lon_max - lon_min) / START_STEP) + 1
    return [
        (lat_min + (y + 0.5) * START_STEP, lon_min + (x + 0.5) * START_STEP, START_STEP)
        for y in range(rows)
        for x in range(cols)
    ]


def sweep(args: argparse.Namespace) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    log_path = OUT / "hucreler.jsonl"

    stores: dict[str, dict] = {}
    done: set[str] = set()
    queue: list[tuple[float, float, float]] = []

    # The coarse grid is always laid down, resumed run or not. Rebuilding the queue out
    # of the log's `split` lists alone would drop every coarse cell the interrupted run
    # never got to — the sweep would finish, report a number, and be quietly short.
    queue = initial_queue()
    if args.devam and log_path.exists():
        with log_path.open(encoding="utf-8") as log:
            for line in log:
                cell = json.loads(line)
                done.add(cell["key"])
                for store in cell["stores"]:
                    stores[store["id"]] = store
                queue.extend(tuple(child) for child in cell["split"])
    queue = [c for c in queue if f"{c[0]:.5f},{c[1]:.5f},{c[2]:.5f}" not in done]
    print(
        f"{len(done)} hücre okunmuş · {len(stores)} mağaza · {len(queue)} hücre kuyrukta",
        flush=True,
    )

    log = log_path.open("a", encoding="utf-8")
    asked = 0
    started = time.monotonic()
    while queue:
        lat, lon, step = queue.pop()
        key = f"{lat:.5f},{lon:.5f},{step:.5f}"
        if key in done:
            continue
        found = ask(lat, lon)
        asked += 1
        done.add(key)
        for store in found:
            stores[store["id"]] = store

        # Proven radius: the farthest store the answer mentioned. An answer shorter than a
        # full page is the whole neighbourhood, so nothing is hidden behind it.
        split: list[tuple[float, float, float]] = []
        if len(found) >= PAGE:
            reach = max(store.get("distance", 0) for store in found)
            if reach < half_diagonal_m(lat, step) and step / 2 >= MIN_STEP:
                quarter, child = step / 4, step / 2
                split = [
                    (lat + dy * quarter, lon + dx * quarter, child)
                    for dy in (-1, 1)
                    for dx in (-1, 1)
                ]
                queue.extend(split)
        log.write(json.dumps({"key": key, "stores": found, "split": split}) + "\n")
        log.flush()

        if asked % 100 == 0:
            rate = asked / (time.monotonic() - started)
            print(
                f"{asked} sorgu · {len(stores)} mağaza · kuyruk {len(queue)}"
                f" · {rate:.1f} sorgu/sn",
                flush=True,
            )
        time.sleep(args.gecikme)
    log.close()

    stamp = dt.datetime.now(tz=dt.UTC).date().isoformat()
    csv_path = OUT / f"magazalar_{stamp}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for store in sorted(stores.values(), key=lambda s: s["id"]):
            writer.writerow(
                [
                    store.get("id", ""),
                    store.get("name", ""),
                    store.get("city", ""),
                    store.get("townShip", ""),
                    store.get("plateCode", ""),
                    store.get("address", ""),
                    store.get("lat", ""),
                    store.get("lng", ""),
                ]
            )
    provinces = {s.get("city") for s in stores.values() if s.get("city")}
    print(f"{len(stores)} mağaza · {len(provinces)} il · {asked} sorgu → {csv_path}")
    if len(provinces) < 81:
        print(f"UYARI: 81 il beklenirken {len(provinces)} il görüldü", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="A101 mağazaları — ızgara taraması")
    parser.add_argument(
        "--devam", action="store_true", help="yarım kalan taramayı sürdür"
    )
    parser.add_argument(
        "--gecikme", type=float, default=0.3, help="istekler arası saniye"
    )
    sweep(parser.parse_args())


if __name__ == "__main__":
    main()
