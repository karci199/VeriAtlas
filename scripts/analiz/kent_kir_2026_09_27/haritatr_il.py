"""haritatr.com district -> semt -> neighbourhood lists for one province (audit only, not a source).

The site's "semt" is the pre-2013 municipal structure: "X Merkez", each former belde, "X Köyleri".
robots.txt allows everything; 1 s between requests. Raw pages cached under C:/veri-ham/haritatr/<plate>/.

usage: haritatr_il.py 16 bursa
"""

import csv, html, re, sys, time
from pathlib import Path
import httpx

PLATE, SLUG = sys.argv[1], sys.argv[2]
RAW = Path("C:/veri-ham/haritatr") / PLATE
RAW.mkdir(parents=True, exist_ok=True)
cli = httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=60, follow_redirects=True)
LINK = re.compile(r'href="(https://www\.haritatr\.com/([^"]*?)-haritasi-([a-z])([0-9a-z]+))"[^>]*>(.*?)</a>', re.S)


def get(url, name):
    p = RAW / f"{name}.html"
    if not p.exists():
        r = cli.get(url)
        r.raise_for_status()  # an error page is not "no data"
        p.write_text(r.text, encoding="utf-8")
        time.sleep(1)
    return p.read_text(encoding="utf-8")


def links(t, kind):
    out = {}
    for m in LINK.finditer(t):
        if m.group(3) == kind:
            out[m.group(1)] = html.unescape(re.sub("<[^>]+>", "", m.group(5))).strip()
    return out


il_url = next(u for u in re.findall(r"<loc>([^<]*)</loc>", Path("C:/veri-ham/haritatr/sitemap-iller.xml").read_text(encoding="utf-8"))
              if u.endswith(f"/{SLUG}-haritasi") or re.search(rf"/{SLUG}-haritasi-[a-z]", u))
districts = links(get(il_url, "_il"), "i")
rows = []
for durl, dname in districts.items():
    semts = links(get(durl, "i_" + durl.rsplit("-", 1)[-1]), "e")
    for surl, sname in semts.items():
        nb = links(get(surl, "e_" + surl.rsplit("-", 1)[-1]), "m")
        for murl, mname in nb.items():
            rows.append(dict(district=dname, semt=sname, neighbourhood=mname.removesuffix(" Mahallesi"), url=murl))
        print(dname, "|", sname, len(nb), flush=True)
with open(RAW / "semt_mahalle.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
print("satir", len(rows))
