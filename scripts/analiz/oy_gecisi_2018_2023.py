"""2018 -> 2023 milletvekili oy gecisleri, mahalle duzeyinde ekolojik cikarim (Goodman)."""

import glob
import json
import re
import sys

import numpy as np
from scipy.optimize import nnls

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

T = "C:/veri/public/tiles/"


def load(v):
    out = {}
    for f in glob.glob(T + f"secim-{v}-mahalle-TR-*.json"):
        out.update(json.load(open(f, encoding="utf-8")))
    return out


a, b = load("mv2018"), load("mv2023")
ortak = sorted(set(a) & set(b))
print("mahalle: 2018", len(a), "| 2023", len(b), "| ortak", len(ortak))

R2018 = [
    ("AKP", r"^AK PART"),
    ("CHP", r"^CHP$"),
    ("HDP", r"^HDP$"),
    ("MHP", r"^MHP$"),
    ("İYİ", r"^[İI]Y[İI]"),
    ("SP", r"^SAADET"),
    ("diğer18", None),
]
R2023 = [
    ("AKP", r"^AK PART"),
    ("CHP", r"^CHP$"),
    ("YSP", r"^YE[ŞS][İI]L SOL"),
    ("MHP", r"^MHP$"),
    ("İYİ", r"^[İI]Y[İI]"),
    ("YRP", r"^YEN[İI]DEN REFAH"),
    ("ZAFER", r"^ZAFER"),
    ("diğer23", None),
]


def vec(rec, rules):
    v = rec.get("v") or {}
    tot = sum(v.values())
    out, kalan = [], tot
    for _, pat in rules:
        if pat is None:
            continue
        s = sum(n for c, n in v.items() if re.search(pat, c, re.IGNORECASE))
        out.append(s)
        kalan -= s
    out.append(max(kalan, 0))
    return out, tot


X, Y, W = [], [], []
atlanan = 0
for key in ortak:
    ra, rb = a[key], b[key]
    ka, kb = ra.get("k") or 0, rb.get("k") or 0
    if ka < 100 or kb < 100:
        atlanan += 1
        continue
    if abs(kb / ka - 1) > 0.15:
        atlanan += 1
        continue  # goc/sinir degisimi
    va, ta = vec(ra, R2018)
    vb, tb = vec(rb, R2023)
    va.append(max(ka - (ra.get("o") or 0), 0))  # katilmayan 2018
    vb.append(max(kb - (rb.get("o") or 0), 0))  # katilmayan 2023
    sa, sb = sum(va), sum(vb)
    if sa < 50 or sb < 50:
        atlanan += 1
        continue
    X.append([x / sa for x in va])
    Y.append([y / sb for y in vb])
    W.append(ka)

X = np.array(X)
Y = np.array(Y)
W = np.array(W, dtype=float)
print(
    "kullanilan mahalle:", len(X), "| atlanan:", atlanan, "| secmen:", f"{W.sum():,.0f}"
)
sw = np.sqrt(W)[:, None]
Xw, Yw = X * sw, Y * sw
rows = [n for n, _ in R2018] + ["katılmayan18"]
cols = [n for n, _ in R2023] + ["katılmayan23"]
Tm = np.zeros((len(rows), len(cols)))
for j in range(Y.shape[1]):
    coef, _ = nnls(Xw, Yw[:, j])
    Tm[:, j] = coef
Tm = Tm / Tm.sum(axis=1, keepdims=True)
print("\n2018 (satır) -> 2023 (sütun), yüzde")
print(f"{'':14}" + "".join(f"{c:>13}" for c in cols))
for i, r in enumerate(rows):
    print(f"{r:14}" + "".join(f"{100 * Tm[i, j]:13.1f}" for j in range(len(cols))))
# 2018 agirliklari (secmen icindeki pay)
w18 = (X * W[:, None]).sum(axis=0) / W.sum()
print(
    "\n2018 tabani (seçmen içinde %):",
    {rows[i]: round(100 * w18[i], 1) for i in range(len(rows))},
)
