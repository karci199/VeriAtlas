"""Yearly Türkiye public lighting kWh and TL from company-level files (pdfplumber column positions).

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import collections
import json
import re

import openpyxl
import pdfplumber
import xlrd

D = "C:/veri-ham/tedas_aydinlatma"
rows = json.load(open(f"{D}/_index.json", encoding="utf-8"))
num = lambda s: float(s.replace(".", "").replace(",", "."))
res = collections.defaultdict(list)
for r in rows:
    f = f"{D}/{r['file']}"
    if f.endswith(".pdf"):
        if r.get("kind") != "company":
            continue
        with pdfplumber.open(f) as pdf:
            w = [x for p in pdf.pages for x in p.extract_words()]
        per = [x["text"] for x in w if re.fullmatch(r"20\d\d/\d+", x["text"])][0]
        g = [x for x in w if x["text"] == "Genel"]
        if not g:
            continue
        vals = [
            x
            for x in w
            if abs(x["top"] - g[0]["top"]) < 4
            and re.fullmatch(r"[\d.]+,\d+", x["text"])
        ]
        vals.sort(key=lambda x: x["x0"])
        v = [num(x["text"]) for x in vals]
        if len(v) < 7:
            print(
                "SHORT",
                per,
                r["label"].encode("ascii", "replace").decode(),
                len(v),
                [x["text"] for x in w if abs(x["top"] - g[0]["top"]) < 15][:20],
            )
            continue
        res[per].append((v[0], v[1], v[5], v[6], len(v), r["label"]))
    else:
        if f.endswith(".xls"):
            ws = xlrd.open_workbook(f).sheet_by_index(0)
            title = ws.name
            it = (ws.row_values(i) for i in range(ws.nrows))
        else:
            wb = openpyxl.load_workbook(f, data_only=True, read_only=True)
            ws = wb.worksheets[0]
            title = ws.title
            it = ws.iter_rows(values_only=True)
        if "Sirket" not in title:
            continue
        k = t = e = b = 0
        per = None
        for row in it:
            if (
                row
                and len(row) > 8
                and isinstance(row[1], str)
                and re.match(r"20\d\d/\d+", row[1])
                and isinstance(row[2], (int, float))
                and "Toplam" not in str(row[0])
            ):
                k += row[2]
                t += row[3] or 0
                e += row[7] or 0
                b += row[8] or 0
                per = row[1]
        if per:
            res[per].append((k, t, e, b, 0, r["label"]))
json.dump(res, open("tedas_company_v2.json", "w"), ensure_ascii=False)
Y = collections.defaultdict(lambda: [0, 0, 0, 0, []])
for per, lst in res.items():
    best = max(lst, key=lambda x: x[0])
    if len(lst) > 1:
        print(
            "dup",
            per,
            [
                (round(x[0] / 1e6), x[5].encode("ascii", "replace").decode())
                for x in lst
            ],
        )
    y, m = map(int, per.split("/"))
    a = Y[y]
    for i in range(4):
        a[i] += best[i]
    a[4].append(m)
for y in sorted(Y):
    k, t, e, b, ms = Y[y]
    miss = sorted(set(range(1, 13)) - set(ms))
    print(
        y,
        len(ms),
        "ay eksik:",
        miss,
        f"{k / 1e9:.2f} TWh fatura {t / 1e9:.2f} mlrTL esas {e / 1e9:.2f} bakanlik {b / 1e9:.2f} ({b / e * 100 if e else 0:.0f}%) {t / k if k else 0:.3f} TL/kWh",
    )
