"""Download TEDAŞ public lighting consumption files (2014-2026) and index them.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import html
import json
import os
import re
import subprocess
import time
import urllib.request

t = open("ted.html", encoding="utf-8").read()
pat = re.compile(
    r'(?:<a href="([^"]+)"[^>]*>\s*)?<button class="accordion-button[^>]*>\s*<div[^>]*>\s*([\d.]+)\s*</div>\s*<span[^>]*>\s*([^<]*?)\s*</span>',
    re.DOTALL,
)
top = {}
mid = {}
rows = []
for href, num, lab in pat.findall(t):
    lab = html.unescape(lab).strip()
    p = num.split(".")
    if len(p) == 1:
        top[num] = lab
    elif len(p) == 2:
        mid[num] = lab
    elif href:
        rows.append(
            dict(
                num=num,
                year=top[p[0]],
                month=mid[p[0] + "." + p[1]],
                label=lab,
                url=href,
            )
        )
D = "C:/veri-ham/tedas_aydinlatma"
for r in rows:
    fn = f"{D}/{r['url'].rsplit('/', 1)[1]}"
    r["file"] = os.path.basename(fn)
    if not os.path.exists(fn):
        req = urllib.request.Request(r["url"], headers={"User-Agent": "Mozilla/5.0"})
        open(fn, "wb").write(urllib.request.urlopen(req, timeout=60).read())
        time.sleep(0.5)
    if fn.endswith(".pdf"):
        txt = subprocess.run(
            ["pdftotext", "-layout", fn, "-"], capture_output=True
        ).stdout.decode("utf-8", "replace")
        r["text_chars"] = len(txt.strip())
        m = re.search(r"(20\d\d)/(\d+)", txt)
        r["period_in_file"] = m.group(0) if m else None
        r["kind"] = (
            "company"
            if "irket Baz" in txt
            else ("municipality" if "Belediye Baz" in txt else None)
        )
json.dump(
    rows, open(f"{D}/_index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1
)
pdf = [r for r in rows if r["file"].endswith(".pdf")]
print(
    len(rows),
    "files;",
    len(pdf),
    "pdf; no text:",
    [
        (
            r["year"],
            r["month"].encode("ascii", "replace").decode(),
            r["label"].encode("ascii", "replace").decode(),
        )
        for r in pdf
        if r["text_chars"] < 200
    ],
)
print(
    "unknown kind:",
    [(r["year"], r["num"]) for r in pdf if r["text_chars"] >= 200 and not r["kind"]],
)
