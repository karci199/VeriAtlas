"""haritatr.com district -> semt -> neighbourhood lists for every province (support signal only).

Province page suffix is the plate in hex (bursa-haritasi-s10, manisa-haritasi-s2d). One request
per second, robots.txt allows all; pages cached under C:/veri-ham/haritatr/<plate>/ so a rerun
only fetches what is missing. Output per province: <plate>/semt_mahalle.csv.

usage: haritatr_tr.py [plate ...]   (default: all 81)
"""

import csv, html, re, sys, time
from pathlib import Path
import httpx

RAW = Path("C:/veri-ham/haritatr")
cli = httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=60, follow_redirects=True)
LINK = re.compile(r'href="(https://www\.haritatr\.com/([^"]*?)-haritasi-([a-z])([0-9a-z]+))"[^>]*>(.*?)</a>', re.S)
iller = {int(m.group(2), 16): m.group(1) for m in re.finditer(r"<loc>(https://www\.haritatr\.com/[a-z-]+-haritasi-s([0-9a-f]+))</loc>",
                                                              (RAW / "sitemap-iller.xml").read_text(encoding="utf-8"))}
plates = [int(p) for p in sys.argv[1:]] or sorted(iller)


def get(folder, url, name):
    p = folder / f"{name}.html"
    if not p.exists():
        r = cli.get(url)
        r.raise_for_status()
        p.write_text(r.text, encoding="utf-8")
        time.sleep(1)
    return p.read_text(encoding="utf-8")


def links(t, kind):
    out = {}
    for m in LINK.finditer(t):
        if m.group(3) == kind:
            out[m.group(1)] = html.unescape(re.sub("<[^>]+>", "", m.group(5))).strip()
    return out


t0 = time.time()
for plate in plates:
    folder = RAW / f"{plate:02d}"
    folder.mkdir(exist_ok=True)
    if (folder / "semt_mahalle.csv").exists():
        continue
    rows = []
    for durl, dname in links(get(folder, iller[plate], "_il"), "i").items():
        for surl, sname in links(get(folder, durl, "i_" + durl.rsplit("-", 1)[-1]), "e").items():
            for murl, mname in links(get(folder, surl, "e_" + surl.rsplit("-", 1)[-1]), "m").items():
                rows.append(dict(district=dname, semt=sname, neighbourhood=mname.removesuffix(" Mahallesi"), url=murl))
    with open(folder / "semt_mahalle.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["district", "semt", "neighbourhood", "url"])
        w.writeheader(); w.writerows(rows)
    print(f"il {plate:02d}: {len(rows)} satır ({time.time() - t0:.0f} sn)", flush=True)
print("bitti")
