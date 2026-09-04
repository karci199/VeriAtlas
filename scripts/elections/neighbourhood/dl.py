"""Download TUIK report HTML files from ';'-separated manifest parts.

Each line is: year;secim cevresi;ilce;report-file-name (on rapory.tuik.gov.tr).
Report URLs are one-off and timestamped, so download promptly after generation.
"""

import concurrent.futures as cf
import pathlib
import re
import sys
import urllib.request

BASE = pathlib.Path(__file__).parent
OUT = BASE / "html"
OUT.mkdir(exist_ok=True)


def slug(t):
    t = t.strip().lower()
    for a, b in zip("çğıöşü", "cgiosu"):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def grab(line):
    year, cevre, ilce, fname = line.split(";")
    dest = OUT / f"{slug(year)}__{slug(cevre)}__{slug(ilce)}.html"
    if dest.exists() and dest.stat().st_size > 5000:
        return "var"
    try:
        with urllib.request.urlopen(
            "https://rapory.tuik.gov.tr/" + fname, timeout=90
        ) as r:
            data = r.read()
        if len(data) < 2000:
            return f"kucuk:{dest.name}:{len(data)}"
        dest.write_bytes(data)
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"hata:{dest.name}:{exc}"


def main(paths):
    lines = []
    for p in paths:
        lines += [
            x.strip()
            for x in pathlib.Path(p).read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
    with cf.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(grab, lines))
    bad = [r for r in res if r not in ("ok", "var")]
    print(
        f"toplam={len(lines)} ok={res.count('ok')} zaten={res.count('var')} hata={len(bad)}"
    )
    for b in bad[:15]:
        print("  ", b)


if __name__ == "__main__":
    main(sys.argv[1:] or sorted((BASE / "manifest_parts").glob("*.txt")))
